"""Synthesis behavior through the previously approved run-service/export boundary."""

import json
from pathlib import Path

import pytest
from network_fakes import Reply, Wire

from synapse.fetch import SafeFetcher
from synapse.models import RunInput
from synapse.network import ToolError
from synapse.search import TavilySearch
from synapse.service import ResearchService
from synapse.storage import ServiceError
from synapse.synthesis import GeminiSynthesis


def seed_sources(path: Path) -> str:
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
        transport=Wire(
            [Reply(b"<p>AST matches syntax.</p>"), Reply(b"<p>Embeddings match wording.</p>")]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    with ResearchService(path, search=search, fetcher=fetcher, live_enabled=True) as service:
        run_id = service.submit_discovery(
            RunInput(topic="Retrieval", question="Compare retrieval"), "seed"
        )
        assert service.wait(run_id).run.state == "sources_ready"
        return str(run_id)


class ModelWire(Wire):
    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Reply:
        assert body and headers["x-goog-api-key"] == "test-gemini-key"
        payload = json.loads(body)
        if url.endswith(":countTokens"):
            assert set(payload) == {"contents"}
            counted = json.loads(payload["contents"][0]["parts"][0]["text"])
            assert "systemInstruction" in counted
            assert "responseJsonSchema" in counted["generationConfig"]
            assert json.loads(counted["contents"][0]["parts"][0]["text"])["evidence"]
            return Reply(b'{"totalTokens": 200}')
        assert url.endswith(":generateContent") and method == "POST"
        assert "tools" not in payload and "cachedContent" not in payload
        assert payload["generationConfig"]["maxOutputTokens"] == 2048
        content = json.loads(payload["contents"][0]["parts"][0]["text"])
        evidence_id = content["evidence"][0]["id"]
        self.destinations.append((url, address))
        draft = {
            "claims": [
                {
                    "text": "AST matches syntax.",
                    "evidence_ids": [evidence_id],
                    "quote": "AST matches syntax.",
                    "section": "Findings",
                    "support_status": "cited",
                }
            ],
            "limitations": ["Saved excerpts cannot establish performance."],
        }
        return Reply(
            json.dumps(
                {
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {"parts": [{"text": json.dumps(draft)}]},
                        }
                    ],
                    "modelVersion": "gemini-test-version",
                    "usageMetadata": {
                        "promptTokenCount": 200,
                        "candidatesTokenCount": 100,
                        "totalTokenCount": 300,
                    },
                }
            ).encode()
        )


def test_saved_sources_generate_cited_report_once_and_reopen(tmp_path: Path) -> None:
    from uuid import UUID

    run_id = UUID(seed_sources(tmp_path))
    wire = ModelWire([])
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        assert service.submit_synthesis(run_id, "model-key") == run_id
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "report_ready"
        assert snapshot.report and snapshot.critique is None
        assert snapshot.report.claims[0].quote == "AST matches syntax."
        assert snapshot.synthesis and snapshot.synthesis.counted_input_tokens == 200
        assert snapshot.synthesis.output_tokens == 100
        assert snapshot.synthesis.model_version == "gemini-test-version"
        assert service.submit_synthesis(run_id, "model-key") == run_id
        assert len(wire.destinations) == 1
        markdown, bundle = service.export_run(run_id)
        assert "[E01](#e01)" in markdown and "INCOMPLETE" in markdown
        assert "test-gemini-key" not in bundle and "Offline fixture" not in markdown
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot
        assert reopened.export_run(run_id) == (markdown, bundle)


@pytest.mark.parametrize(
    "failure",
    [
        "unknown_id",
        "cross_run_id",
        "quote",
        "malformed",
        "refusal",
        "output_limit",
        "usage",
        "input_budget",
        "quota",
        "timeout",
        "tool_call",
        "empty_claim",
        "provider_error",
    ],
)
def test_invalid_or_overbudget_model_outputs_preserve_sources_and_usage(
    tmp_path: Path,
    failure: str,
) -> None:
    from uuid import UUID, uuid4

    run_id = UUID(seed_sources(tmp_path))

    foreign_id = None
    if failure == "cross_run_id":
        other_id = UUID(seed_sources(tmp_path / "other"))
        with ResearchService(tmp_path / "other") as other:
            analysis = other.get_run(other_id).analysis
            assert analysis is not None
            foreign_id = str(analysis.evidence[0].id)

    class BrokenWire(ModelWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            if failure == "input_budget" and url.endswith(":countTokens"):
                return Reply(b'{"totalTokens": 8193}')
            if failure == "quota":
                return Reply(status=429)
            if url.endswith(":generateContent") and failure == "timeout":
                raise ToolError("TIMEOUT", transient=True)
            if url.endswith(":generateContent") and failure == "provider_error":
                return Reply(b"secret-provider-error", status=500)
            reply = super().request(method, url, address, timeout, headers, body)
            if not url.endswith(":generateContent"):
                return reply
            value = json.loads(reply.body)
            if failure in {"unknown_id", "cross_run_id", "quote"}:
                draft = json.loads(value["candidates"][0]["content"]["parts"][0]["text"])
                if failure == "quote":
                    draft["claims"][0]["quote"] = "Unsupported quote"
                else:
                    draft["claims"][0]["evidence_ids"] = [foreign_id or str(uuid4())]
                value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(draft)
            elif failure == "tool_call":
                value["candidates"][0]["content"]["parts"] = [{"functionCall": {"name": "fetch"}}]
            elif failure == "empty_claim":
                draft = json.loads(value["candidates"][0]["content"]["parts"][0]["text"])
                draft["claims"][0]["text"] = " "
                value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(draft)
            elif failure == "malformed":
                value["candidates"][0]["content"]["parts"][0]["text"] = "{bad json"
            elif failure in {"refusal", "output_limit"}:
                value["candidates"][0]["finishReason"] = (
                    "SAFETY" if failure == "refusal" else "MAX_TOKENS"
                )
            elif failure == "usage":
                value["usageMetadata"]["candidatesTokenCount"] = 2049
                value["usageMetadata"]["totalTokenCount"] = 2249
            return Reply(json.dumps(value).encode())

    wire = BrokenWire([])
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        snapshot = service.wait(service.submit_synthesis(run_id, "bad"))
        assert snapshot.run.state == "failed" and snapshot.report is None
        assert snapshot.analysis and len(snapshot.analysis.sources) == 2
        assert snapshot.synthesis
        assert "INCOMPLETE" in service.export_run(run_id)[0]
        assert "test-gemini-key" not in service.export_run(run_id)[1]
        if failure == "input_budget":
            assert not wire.destinations
        elif failure not in {"quota", "timeout", "provider_error"}:
            assert snapshot.synthesis.output_tokens is not None
        assert service.submit_synthesis(run_id, "bad") == run_id
        with pytest.raises(ServiceError, match="INVALID_STATE"):
            service.submit_synthesis(run_id, "new-attempt")


def test_cancellation_during_generation_retains_count_and_unknown_usage(tmp_path: Path) -> None:
    from threading import Event
    from uuid import UUID

    entered, release = Event(), Event()

    class Gated(ModelWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            if url.endswith(":generateContent"):
                entered.set()
                assert release.wait(5)
            return super().request(method, url, address, timeout, headers, body)

    run_id = UUID(seed_sources(tmp_path))
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=Gated([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        service.submit_synthesis(run_id, "cancel")
        try:
            assert entered.wait(5)
            service.cancel(run_id)
        finally:
            release.set()
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "cancelled" and snapshot.report is None
        assert snapshot.synthesis and snapshot.synthesis.counted_input_tokens == 200
        assert snapshot.synthesis.output_tokens is None
        assert snapshot.synthesis.status == "generating"
        assert snapshot.analysis


def test_model_requests_cannot_introduce_extra_tools_or_urls(tmp_path: Path) -> None:
    from uuid import UUID

    run_id = UUID(seed_sources(tmp_path))

    class Hostile(ModelWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            response = super().request(method, url, address, timeout, headers, body)
            if url.endswith(":generateContent"):
                value = json.loads(response.body)
                draft = json.loads(value["candidates"][0]["content"]["parts"][0]["text"])
                draft["claims"][0]["text"] = "See https://invented.invalid/ for the answer."
                value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(draft)
                return Reply(json.dumps(value).encode())
            return response

    adapter = GeminiSynthesis(
        "test-gemini-key", transport=Hostile([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        snapshot = service.wait(service.submit_synthesis(run_id, "hostile"))
        assert snapshot.run.state == "failed" and snapshot.report is None


def test_report_ui_inspects_citations_and_does_not_offer_a_second_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    from streamlit.testing.v1 import AppTest

    from synapse.ui.resources import get_service

    run_id = UUID(seed_sources(tmp_path))
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=ModelWire([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        service.wait(service.submit_synthesis(run_id, "ui"))
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SYNAPSE_ENABLE_SYNTHESIS", "0")
    monkeypatch.setenv("SYNAPSE_GEMINI_MODEL", "disabled/invalid-model")
    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "src/synapse/ui/app.py"), default_timeout=10
    )
    app.query_params["run"] = str(run_id)
    app.run()
    assert not app.exception
    assert any("Report ready" in item.value for item in app.success)
    assert app.selectbox(key=f"claim-{run_id}")
    assert any("AST matches syntax." in item.value for item in app.text)
    assert not any(button.label == "Generate cited report" for button in app.button)
    assert len(app.get("download_button")) == 2
    assert any("No critique" in item.value for item in app.info)
    get_service.clear()


def test_provider_rejection_reports_safe_status_without_raw_messages(tmp_path: Path) -> None:
    from uuid import UUID

    class Rejected(ModelWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            return Reply(
                b'{"error":{"code":400,"status":"INVALID_ARGUMENT",'
                b'"message":"secret-provider-message"}}',
                status=400,
            )

    adapter = GeminiSynthesis(
        "test-gemini-key", transport=Rejected([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    run_id = UUID(seed_sources(tmp_path))
    with ResearchService(tmp_path, synthesis=adapter, synthesis_enabled=True) as service:
        snapshot = service.wait(service.submit_synthesis(run_id, "reject"))
        assert snapshot.run.error and "HTTP 400" in snapshot.run.error
        assert "INVALID_ARGUMENT" in snapshot.run.error
        assert "secret-provider-message" not in service.export_run(run_id)[1]


@pytest.mark.parametrize("failure", ["deadline", "artifact"])
def test_synthesis_failures_cannot_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from uuid import UUID

    from synapse.models import Snapshot

    run_id = UUID(seed_sources(tmp_path))
    tick = [0.0]

    class Expiring(ModelWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            response = super().request(method, url, address, timeout, headers, body)
            if url.endswith(":generateContent") and failure == "deadline":
                tick[0] = 601.0
            return response

    adapter = GeminiSynthesis(
        "test-gemini-key", transport=Expiring([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(
        tmp_path, synthesis=adapter, synthesis_enabled=True, clock=lambda: tick[0]
    ) as service:
        if failure == "artifact":

            def broken_artifacts(snapshot: Snapshot) -> None:
                raise OSError("test disk failure")

            monkeypatch.setattr(service, "_artifacts", broken_artifacts)
        snapshot = service.wait(service.submit_synthesis(run_id, "failure"))
        assert snapshot.run.state == "failed"
        assert snapshot.analysis and snapshot.discovery
        assert (
            snapshot.run.error
            and ("DEADLINE" if failure == "deadline" else "STORAGE_ERROR") in snapshot.run.error
        )
        if failure == "artifact":
            with pytest.raises(ServiceError, match="EXPORT_FAILED"):
                service.export_run(run_id)
            monkeypatch.undo()
        assert "INCOMPLETE" in service.export_run(run_id)[0]


def test_sources_ui_requires_enablement_and_explicit_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import UUID

    from streamlit.testing.v1 import AppTest

    from synapse.ui import resources

    run_id = UUID(seed_sources(tmp_path))
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    wire = ModelWire([])
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, synthesis=adapter) as service:
        monkeypatch.setattr(resources, "get_service", lambda directory: service)
        app = AppTest.from_file(
            str(Path(__file__).parents[1] / "src/synapse/ui/app.py"), default_timeout=10
        )
        app.query_params["run"] = str(run_id)
        app.run()
        assert not app.exception
        assert app.button(key=f"synthesize-{run_id}").disabled
        assert not wire.destinations
        service.synthesis_enabled = True
        app.run()
        assert not app.button(key=f"synthesize-{run_id}").disabled
        assert not wire.destinations
        app.button(key=f"synthesize-{run_id}").click().run()
        assert service.wait(run_id).run.state == "report_ready"
        app.run()
        assert not app.exception
        assert len(wire.destinations) == 1
        assert not any(button.label == "Generate cited report" for button in app.button)
