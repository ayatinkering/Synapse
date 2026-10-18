from pathlib import Path

import pytest

from synapse.models import RunInput
from synapse.service import ResearchService
from synapse.storage import ServiceError


def test_live_preview_is_bounded_and_key_conflicts_are_not_scenario_only(tmp_path: Path) -> None:
    with ResearchService(tmp_path) as service:
        preview = service.preview_discovery(
            RunInput(
                topic="Retrieval",
                question="  Compare retrieval  ",
                subquestions=["Compare retrieval", "Explain AST limits", "Embedding limits"],
                date_preference="month",
            )
        )
        assert preview.queries == ["Compare retrieval", "Explain AST limits", "Embedding limits"]
        assert preview.date_preference == "month"
        assert preview.limits.max_sources == 10
        first = service.submit("comparison", "key")
        service.wait(first)
        assert service.submit("comparison", "key") == first
        with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
            service.submit("sparse", "key")


def test_live_sources_are_checkpointed_reopened_and_never_synthesized(tmp_path: Path) -> None:
    import json

    from network_fakes import Reply, Wire

    from synapse.fetch import SafeFetcher
    from synapse.search import TavilySearch

    search = TavilySearch(
        "test-only-key",
        transport=Wire(
            [
                Reply(
                    json.dumps(
                        {
                            "results": [
                                {"url": "https://one.example/paper", "title": "One"},
                                {"url": "https://two.example/paper", "title": "Two"},
                            ]
                        }
                    ).encode()
                )
            ]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    fetcher = SafeFetcher(
        transport=Wire(
            [
                Reply(
                    b"<article>AST retrieval uses syntax trees. "
                    b"Dynamic calls limit coverage.</article>"
                ),
                Reply(
                    b"<article>Embedding retrieval uses vectors. "
                    b"Similarity can miss relevance.</article>"
                ),
            ]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    input = RunInput(topic="Retrieval", question="Compare AST and embedding retrieval")
    with ResearchService(tmp_path, search=search, fetcher=fetcher, live_enabled=True) as service:
        run_id = service.submit_discovery(input, "live-key")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "sources_ready"
        assert snapshot.analysis and len(snapshot.analysis.sources) == 2
        assert snapshot.analysis.evidence[0].excerpt == "AST retrieval uses syntax trees."
        assert snapshot.report is None and snapshot.critique is None
        assert snapshot.run.model_id is None and snapshot.run.fixture_id is None
        assert service.submit_discovery(input, "live-key") == run_id
        with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
            service.submit_discovery(input.model_copy(update={"question": "Other"}), "live-key")
        markdown, bundle = service.export_run(run_id)
        assert "INCOMPLETE" in markdown and "Offline fixture" not in markdown
        assert "test-only-key" not in bundle
        assert snapshot.discovery
        assert str(snapshot.discovery.queries[0].id) in markdown
        assert "max_sources: 10" in markdown
        assert "Retrieved:" in markdown
        assert "Publication date:" in markdown
        assert json.loads(bundle)["run"]["kind"] == "live"
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot
        assert reopened.export_run(run_id) == (markdown, bundle)


def test_sa_database_migrates_without_relabeling_or_losing_submission_identity(
    tmp_path: Path,
) -> None:
    import json
    import sqlite3
    from uuid import UUID

    # Authored v1 schema and payload use no S-B model fields; do not create v1 with the new store.
    db = sqlite3.connect(tmp_path / "synapse.sqlite3")
    db.executescript("""
        CREATE TABLE runs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                           fixture_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE stage_outputs (run_id TEXT NOT NULL REFERENCES runs(id),
            stage TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id, stage));
        CREATE TABLE events (run_id TEXT NOT NULL REFERENCES runs(id), sequence INTEGER NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(run_id, sequence));
        PRAGMA user_version=1;
    """)
    payload = {
        "schema_version": 1,
        "id": "00000000-0000-0000-0000-000000000001",
        "fixture_id": "comparison",
        "input": {"topic": "Old demo", "question": "Old question"},
        "state": "insufficient_evidence",
        "created_at": "2026-10-18T00:00:00Z",
        "updated_at": "2026-10-18T00:00:00Z",
        "error": "Old gap",
    }
    db.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?)",
        (payload["id"], "legacy-key", "comparison", json.dumps(payload)),
    )
    db.commit()
    db.close()
    with ResearchService(tmp_path) as service:
        snapshot = service.get_run(UUID(str(payload["id"])))
        assert snapshot.run.kind == "fixture" and snapshot.run.input.topic == "Old demo"
        assert snapshot.run.label == "Offline fixture demonstration"
        assert "Old gap" in service.export_run(snapshot.run.id)[0]
        with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
            service.submit("comparison", "legacy-key")
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(snapshot.run.id) == snapshot


def test_cancelling_between_live_sources_preserves_first_source(tmp_path: Path) -> None:
    import json
    from threading import Event

    from network_fakes import Reply, Wire

    from synapse.fetch import SafeFetcher
    from synapse.search import TavilySearch

    entered, release = Event(), Event()

    class GatedWire(Wire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            if self.destinations:
                entered.set()
                assert release.wait(5)
            return super().request(method, url, address, timeout, headers, body)

    search = TavilySearch(
        "test-only-key",
        transport=Wire(
            [
                Reply(
                    json.dumps(
                        {
                            "results": [
                                {"url": "https://one.example/"},
                                {"url": "https://two.example/"},
                            ]
                        }
                    ).encode()
                )
            ]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    fetcher = SafeFetcher(
        transport=GatedWire([Reply(b"<p>First AST source.</p>"), Reply(b"<p>Second.</p>")]),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    with ResearchService(tmp_path, search=search, fetcher=fetcher, live_enabled=True) as service:
        run_id = service.submit_discovery(RunInput(topic="AST", question="AST retrieval"), "cancel")
        try:
            assert entered.wait(5)
            assert service.get_run(run_id).analysis
            service.cancel(run_id)
        finally:
            release.set()
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "cancelled"
        assert snapshot.analysis and len(snapshot.analysis.sources) == 1
        assert snapshot.analysis.sources[0].extracted_text == "First AST source."
        assert "First AST source." in service.export_run(run_id)[0]
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot


def test_cancelling_search_retains_inflight_attempt_without_assuming_usage(tmp_path: Path) -> None:
    from threading import Event

    from network_fakes import Reply, Wire

    from synapse.search import TavilySearch

    entered, release = Event(), Event()

    class GatedSearch(Wire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            entered.set()
            assert release.wait(5)
            return super().request(method, url, address, timeout, headers, body)

    search = TavilySearch(
        "test-only-key",
        transport=GatedSearch([Reply(b'{"results": []}')]),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    with ResearchService(tmp_path, search=search, live_enabled=True) as service:
        run_id = service.submit_discovery(
            RunInput(topic="AST", question="AST retrieval"), "search-cancel"
        )
        try:
            assert entered.wait(5)
            snapshot = service.get_run(run_id)
            assert snapshot.discovery and snapshot.discovery.queries[0].attempts
            assert snapshot.discovery.queries[0].attempts[0].credits is None
            service.cancel(run_id)
        finally:
            release.set()
        assert service.wait(run_id).run.state == "cancelled"


def test_live_query_deduplication_partial_search_failure_and_gap(tmp_path: Path) -> None:
    import json

    from network_fakes import Reply, Wire

    from synapse.fetch import SafeFetcher
    from synapse.search import TavilySearch

    wire = Wire(
        [
            Reply(
                json.dumps(
                    {"results": [{"url": "https://example.org/paper", "content": "not evidence"}]}
                ).encode()
            ),
            Reply(b'{"results": [{"url": "https://example.org:443/paper/#section"}]}'),
            Reply(b'{"results": "malformed"}'),
        ]
    )
    fetch_wire = Wire([Reply(b"<main>Fetched AST evidence.</main>")])
    search = TavilySearch("test-only-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"])
    fetcher = SafeFetcher(transport=fetch_wire, resolver=lambda h, t: ["93.184.216.34"])
    with ResearchService(tmp_path, search=search, fetcher=fetcher, live_enabled=True) as service:
        snapshot = service.wait(
            service.submit_discovery(
                RunInput(topic="AST", question="AST", subquestions=["Limits", "Evaluation"]),
                "partial",
            )
        )
        assert snapshot.run.state == "insufficient_evidence"
        assert snapshot.discovery and len(snapshot.discovery.candidates) == 1
        assert len(snapshot.discovery.candidates[0].query_ids) == 2
        assert snapshot.discovery.queries[-1].error == "SEARCH_MALFORMED"
        assert len(fetch_wire.destinations) == 1
        assert (
            snapshot.analysis and snapshot.analysis.evidence[0].excerpt == "Fetched AST evidence."
        )
        assert all(e.excerpt != "not evidence" for e in snapshot.analysis.evidence)


def test_live_auth_failure_stops_queries_and_keeps_prior_results(tmp_path: Path) -> None:
    from network_fakes import Reply, Wire

    from synapse.search import TavilySearch

    wire = Wire([Reply(b'{"results": [{"url": "https://example.org/"}]}'), Reply(status=401)])
    search = TavilySearch("test-only-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"])
    with ResearchService(tmp_path, search=search, live_enabled=True) as service:
        snapshot = service.wait(
            service.submit_discovery(
                RunInput(topic="AST", question="AST", subquestions=["Limits", "Evaluation"]), "auth"
            )
        )
        assert snapshot.run.state == "failed"
        assert snapshot.discovery and len(snapshot.discovery.queries) == 2
        assert snapshot.discovery.candidates and snapshot.analysis is None
        assert snapshot.run.error and "SEARCH_AUTH" in snapshot.run.error
        assert "test-only-key" not in service.export_run(snapshot.run.id)[1]


def test_deadline_between_live_sources_preserves_completed_source(tmp_path: Path) -> None:
    from network_fakes import Reply, Wire

    from synapse.fetch import SafeFetcher
    from synapse.search import TavilySearch

    clock = [0.0]

    class DeadlineWire(Wire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            if self.destinations:
                clock[0] = 601
            return super().request(method, url, address, timeout, headers, body)

    search = TavilySearch(
        "test-only-key",
        transport=Wire(
            [
                Reply(
                    b'{"results": ['
                    b'{"url": "https://one.example/"}, {"url": "https://two.example/"}]}'
                )
            ]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    fetcher = SafeFetcher(
        transport=DeadlineWire([Reply(b"<p>First.</p>"), Reply(b"<p>Second.</p>")]),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    with ResearchService(
        tmp_path, search=search, fetcher=fetcher, live_enabled=True, clock=lambda: clock[0]
    ) as service:
        snapshot = service.wait(
            service.submit_discovery(RunInput(topic="AST", question="AST"), "deadline")
        )
        assert snapshot.run.state == "failed"
        assert snapshot.run.error and "DEADLINE_EXCEEDED" in snapshot.run.error
        assert snapshot.analysis and len(snapshot.analysis.sources) == 1
        assert "First." in service.export_run(snapshot.run.id)[0]
