"""Real LangChain loops and Gemini wire contracts, without provider/network access."""

import json
from pathlib import Path
from typing import Any

import pytest
from network_fakes import Reply, Wire

from synapse.critic import GeminiCritic
from synapse.fetch import SafeFetcher
from synapse.models import RunInput, SynthesisConfig
from synapse.search import TavilySearch
from synapse.service import ResearchService
from synapse.storage import ServiceError
from synapse.synthesis import GeminiSynthesis


class AgentWire(Wire):
    def __init__(self, decisions: list[dict[str, Any] | int], *, tokens: int = 200) -> None:
        super().__init__([])
        self.decisions = decisions[:]
        self.tokens = tokens
        self.payloads: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Reply:
        assert body is not None
        self.destinations.append((url, address))
        payload = json.loads(body)
        if url.endswith(":countTokens"):
            return Reply(json.dumps({"totalTokens": self.tokens}).encode())
        self.payloads.append(payload)
        decision = self.decisions.pop(0)
        if isinstance(decision, int):
            return Reply(status=decision)
        return Reply(
            json.dumps(
                {
                    "modelVersion": "test-gemini-version",
                    "usageMetadata": {
                        "promptTokenCount": 200,
                        "candidatesTokenCount": 20,
                        "thoughtsTokenCount": 0,
                        "totalTokenCount": 220,
                    },
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {
                                "parts": [{"text": json.dumps(decision)}],
                            },
                        }
                    ],
                }
            ).encode()
        )


def setup_service(
    path: Path,
    decisions: list[dict[str, Any] | int],
    *,
    tokens: int = 200,
) -> tuple[ResearchService, AgentWire, Wire, Wire]:
    model_wire = AgentWire(decisions, tokens=tokens)
    search_wire = Wire(
        [
            Reply(
                json.dumps(
                    {
                        "results": [
                            {"url": "https://one.example/", "title": "First"},
                            {"url": "https://two.example/", "title": "Second"},
                        ]
                    }
                ).encode()
            )
        ]
    )
    fetch_wire = Wire(
        [
            Reply(b"<article>AST matches syntax.</article>"),
            Reply(b"<main>Embeddings match wording.</main>"),
        ]
    )
    search = TavilySearch(
        "test-search-key", transport=search_wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    fetcher = SafeFetcher(transport=fetch_wire, resolver=lambda h, t: ["93.184.216.34"])
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=model_wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    return (
        ResearchService(
            path, search=search, fetcher=fetcher, discovery_model=adapter, live_enabled=True
        ),
        model_wire,
        search_wire,
        fetch_wire,
    )


INPUT = RunInput(topic="Retrieval", question="Compare AST and embedding retrieval")
SUCCESS: list[dict[str, Any] | int] = [
    {"index": 0},
    {"index": None},  # Discovery search, then finish.
    {"index": 1},
    {"index": 0},
    {"index": None},  # Analysis chooses reversed order.
]


def test_agents_choose_tools_and_full_chain_workflow_reopens(tmp_path: Path) -> None:
    from test_critic import CriticWire
    from test_synthesis import ModelWire

    service, model, search, fetch = setup_service(tmp_path, SUCCESS)
    with service:
        run_id = service.submit_discovery(INPUT, "agents")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "sources_ready", snapshot.run.error
        assert snapshot.run.workflow == "langchain"
        assert snapshot.analysis and snapshot.discovery
        assert [s.original_url for s in snapshot.analysis.sources] == [
            "https://two.example/",
            "https://one.example/",
        ]
        assert [s.display_id for s in snapshot.analysis.sources] == ["S01", "S02"]
        assert [e.display_id for e in snapshot.analysis.evidence] == ["E01", "E02"]
        assert snapshot.discovery_usage and len(snapshot.discovery_usage.calls) == 2
        assert snapshot.analysis_usage and len(snapshot.analysis_usage.calls) == 3
        assert all(c.status == "validated" for c in snapshot.analysis_usage.calls)
        assert len(search.destinations) == 1 and len(fetch.destinations) == 2
        assert not model.decisions
        before = len(model.destinations)
        assert service.submit_discovery(INPUT, "agents") == run_id
        assert len(model.destinations) == before

        service.synthesis = GeminiSynthesis(
            "test-gemini-key", transport=ModelWire([]), resolver=lambda h, t: ["93.184.216.34"]
        )
        service.synthesis_enabled = True
        service.submit_synthesis(run_id, "report")
        assert service.wait(run_id).run.state == "report_ready"
        service.critic = GeminiCritic(
            "test-gemini-key", transport=CriticWire([]), resolver=lambda h, t: ["93.184.216.34"]
        )
        service.critique_enabled = True
        service.submit_critique(run_id, "critic")
        assert service.wait(run_id).run.state == "completed"
        markdown, bundle = service.export_run(run_id)
        assert "LangChain agents" in markdown and "discovery-agent-v1" in markdown
        assert json.loads(bundle)["analysis_usage"]["calls"][0]["model_version"]
    with ResearchService(tmp_path) as reopened:
        assert reopened.export_run(run_id) == (markdown, bundle)


@pytest.mark.parametrize(
    "decisions,searches,fetches",
    [
        ([{"index": 100}], 0, 0),
        ([{"index": -1}], 0, 0),
        ([{"index": True}], 0, 0),
        ([{"index": "0"}], 0, 0),
        ([{"index": 0, "url": "http://127.0.0.1/"}], 0, 0),
        ([{"index": 0}, {"index": 0}], 1, 0),
        ([{"index": 0}, {"index": None}, {"index": 5}], 1, 0),
        ([{"index": 0}, {"index": None}, {"index": 0}, {"index": 0}], 1, 1),
    ],
)
def test_untrusted_actions_cannot_escape_catalog_or_repeat_tools(
    tmp_path: Path,
    decisions: list[dict[str, Any] | int],
    searches: int,
    fetches: int,
) -> None:
    service, _, search, fetch = setup_service(tmp_path, decisions)
    with service:
        run_id = service.submit_discovery(INPUT, "bad-action")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "failed"
        assert len(search.destinations) == searches
        assert len(fetch.destinations) == fetches
        if fetches:
            assert snapshot.analysis and len(snapshot.analysis.sources) == fetches
        assert "127.0.0.1" not in (snapshot.run.error or "")


@pytest.mark.parametrize("failure", [429, 500])
def test_model_failure_keeps_earlier_evidence_and_usage_without_retry(
    tmp_path: Path,
    failure: int,
) -> None:
    service, model, _, fetch = setup_service(
        tmp_path,
        [
            {"index": 0},
            {"index": None},
            {"index": 0},
            failure,
        ],
    )
    with service:
        run_id = service.submit_discovery(INPUT, "failure")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "failed"
        assert snapshot.analysis and len(snapshot.analysis.sources) == 1
        assert snapshot.analysis_usage and len(snapshot.analysis_usage.calls) == 2
        assert snapshot.analysis_usage.calls[-1].status == "generating"
        assert len(model.payloads) == 4 and len(fetch.destinations) == 1
        assert "test-gemini-key" not in service.export_run(run_id)[1]


def test_agent_token_budget_rejects_before_generation_or_tools(tmp_path: Path) -> None:
    service, model, search, fetch = setup_service(tmp_path, SUCCESS, tokens=8193)
    with service:
        snapshot = service.wait(service.submit_discovery(INPUT, "budget"))
        assert snapshot.run.state == "failed"
        assert not model.payloads and not search.destinations and not fetch.destinations
        assert snapshot.discovery_usage
        assert snapshot.discovery_usage.calls[0].status == "counted"


def test_changed_agent_configuration_cannot_reuse_submission_key(tmp_path: Path) -> None:
    service, _, _, _ = setup_service(tmp_path, SUCCESS)
    with service:
        service.wait(service.submit_discovery(INPUT, "same-key"))
        assert service.live is not None
        from synapse.agents import AgentDiscovery

        assert isinstance(service.live, AgentDiscovery)
        service.live.model.config = SynthesisConfig(max_input_tokens=8000)
        with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
            service.submit_discovery(INPUT, "same-key")


def test_agent_call_limit_cannot_be_bypassed_by_reinvoking_model(tmp_path: Path) -> None:
    from langsmith import tracing_context

    from synapse.agents import GeminiAgentModel
    from synapse.models import AgentUsage
    from synapse.network import WorkContext

    service, wire, _, _ = setup_service(tmp_path, [{"index": None}, {"index": None}])
    with service, tracing_context(enabled=False):
        assert service.live is not None
        from synapse.agents import AgentDiscovery

        assert isinstance(service.live, AgentDiscovery)
        model = GeminiAgentModel(
            adapter=service.live.model,
            context=WorkContext(),
            checkpoint=lambda record: None,
            usage=AgentUsage(prompt_version="discovery-agent-v1"),
            max_calls=1,
            tool_name="search_web",
            cache=False,
        )
        model.invoke("Finish")
        with pytest.raises(ServiceError, match="AGENT_BUDGET"):
            model.invoke("Try again")
        assert len(wire.payloads) == 1


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_agent_checks_cancellation_and_deadline_before_provider_calls(
    tmp_path: Path,
    stop: str,
) -> None:
    from synapse.agents import AgentDiscovery
    from synapse.models import Run
    from synapse.network import StopWork, WorkContext

    service, model, search, fetch = setup_service(tmp_path, SUCCESS)
    with service:
        assert isinstance(service.live, AgentDiscovery)
        context = WorkContext(
            cancelled=lambda: stop == "cancel",
            clock=lambda: 1.0,
            deadline=0.0 if stop == "deadline" else 10.0,
        )
        with pytest.raises(StopWork):
            service.live.discover(Run(input=INPUT), [INPUT.question], context, lambda r: None)
        assert not model.destinations and not search.destinations and not fetch.destinations


def test_search_auth_failure_stops_agents_and_retains_checkpoint(tmp_path: Path) -> None:
    service, model, search, fetch = setup_service(tmp_path, SUCCESS)
    search.replies = [Reply(status=401)]
    with service:
        snapshot = service.wait(service.submit_discovery(INPUT, "auth"))
        assert snapshot.run.state == "failed"
        assert snapshot.discovery and snapshot.discovery.queries[0].error == "SEARCH_AUTH"
        assert len(model.payloads) == 1 and not fetch.destinations


def test_agents_keep_deduplication_and_candidate_cap_across_queries(tmp_path: Path) -> None:
    service, model, search, fetch = setup_service(
        tmp_path,
        [
            {"index": 1},
            {"index": 0},
            {"index": None},
            {"index": 0},
            {"index": 1},
            {"index": None},
        ],
    )
    from synapse.models import Limits

    service.limits = Limits(max_queries=2, max_sources=2)
    search.replies.append(
        Reply(
            json.dumps(
                {
                    "results": [
                        {"url": "https://one.example/#fragment"},
                        {"url": "https://three.example/"},
                    ]
                }
            ).encode()
        )
    )
    with service:
        run_id = service.submit_discovery(
            INPUT.model_copy(
                update={
                    "subquestions": ["AST limitations"],
                }
            ),
            "dedup",
        )
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "sources_ready", snapshot.run.error
        assert snapshot.discovery and len(snapshot.discovery.candidates) == 2
        assert snapshot.discovery.queries[0].text == "AST limitations"
        assert len(snapshot.discovery.candidates[0].query_ids) == 2
        assert len(fetch.destinations) == 2 and not model.decisions


def test_tracing_environment_does_not_enable_external_research_tracing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from langsmith import get_tracing_context

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    service, model, _, _ = setup_service(tmp_path, SUCCESS)
    original_request = model.request

    def checked_request(*args: Any, **kwargs: Any) -> Reply:
        assert get_tracing_context()["enabled"] is False
        return original_request(*args, **kwargs)

    monkeypatch.setattr(model, "request", checked_request)
    with service:
        assert (
            service.wait(service.submit_discovery(INPUT, "no-tracing")).run.state == "sources_ready"
        )
