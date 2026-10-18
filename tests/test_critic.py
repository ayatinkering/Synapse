"""Live critique observed through the approved service/export/UI boundaries."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from network_fakes import Reply
from test_synthesis import ModelWire, seed_sources

from synapse.service import ResearchService
from synapse.storage import ServiceError
from synapse.synthesis import GeminiSynthesis


class CriticWire(ModelWire):
    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Reply:
        payload = json.loads(body or b"{}")
        if url.endswith(":generateContent"):
            data = json.loads(payload["contents"][0]["parts"][0]["text"])
            if "report" in data:
                assert "tools" not in payload
                self.destinations.append((url, address))
                draft = {
                    "scores": [2, 1, 1, 2, 2],
                    "findings": [
                        {
                            "claim_id": data["report"]["claims"][0]["id"],
                            "comment": "Coverage: compare both approaches explicitly.",
                        }
                    ],
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
                            "modelVersion": "gemini-test-critic",
                            "usageMetadata": {
                                "promptTokenCount": 300,
                                "candidatesTokenCount": 80,
                                "totalTokenCount": 380,
                            },
                        }
                    ).encode()
                )
        return super().request(method, url, address, timeout, headers, body)


def seed_report(path: Path) -> UUID:
    run_id = UUID(seed_sources(path))
    adapter = GeminiSynthesis(
        "test-gemini-key", transport=ModelWire([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(path, synthesis=adapter, synthesis_enabled=True) as service:
        assert service.wait(service.submit_synthesis(run_id, "report")).run.state == "report_ready"
    return run_id


def test_saved_report_is_critiqued_once_completed_and_reopened(tmp_path: Path) -> None:
    from synapse.critic import GeminiCritic

    run_id = seed_report(tmp_path)
    wire = CriticWire([])
    critic = GeminiCritic(
        "test-gemini-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, critic=critic, critique_enabled=True) as service:
        report = service.get_run(run_id).report
        assert service.submit_critique(run_id, "critic") == run_id
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "completed"
        assert snapshot.report == report and snapshot.critique
        assert snapshot.critique.total == 8
        assert snapshot.critique.evaluator_model == "gemini-test-critic"
        assert snapshot.critique_usage and snapshot.critique_usage.output_tokens == 80
        assert service.submit_critique(run_id, "critic") == run_id
        assert len(wire.destinations) == 1
        exports = service.export_run(run_id)
        assert "INCOMPLETE" not in exports[0]
        assert "Predetermined critique" not in exports[0]
        assert "critique pending" not in exports[0].lower()
        assert "Coverage: compare both approaches explicitly." in exports[0]
        assert "critic-v1" in exports[0]
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot
        assert reopened.export_run(run_id) == exports


@pytest.mark.parametrize(
    "failure",
    [
        "score",
        "fraction",
        "boolean",
        "count",
        "unknown_claim",
        "empty",
        "oversized",
        "missing_findings",
        "extra_total",
        "malformed",
        "refusal",
        "tool",
        "quota",
        "budget",
        "usage",
        "link",
    ],
)
def test_bad_critique_preserves_the_report_and_never_completes(
    tmp_path: Path, failure: str
) -> None:
    from uuid import uuid4

    from synapse.critic import GeminiCritic

    class Broken(CriticWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            if failure == "budget" and url.endswith(":countTokens"):
                return Reply(b'{"totalTokens":8193}')
            if failure == "quota":
                return Reply(status=429)
            reply = super().request(method, url, address, timeout, headers, body)
            if not url.endswith(":generateContent"):
                return reply
            value = json.loads(reply.body)
            draft = json.loads(value["candidates"][0]["content"]["parts"][0]["text"])
            if failure in {"score", "fraction", "boolean"}:
                draft["scores"][0] = {"score": 3, "fraction": 1.5, "boolean": True}[failure]
            elif failure == "count":
                draft["scores"] = [2, 2]
            elif failure == "unknown_claim":
                draft["findings"][0]["claim_id"] = str(uuid4())
            elif failure in {"empty", "oversized", "link"}:
                draft["findings"][0]["comment"] = {
                    "empty": " ",
                    "oversized": "x" * 2001,
                    "link": "See https://invented.invalid/",
                }[failure]
            elif failure == "missing_findings":
                draft["findings"] = []
            elif failure == "extra_total":
                draft["total"] = 10
            value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(draft)
            if failure == "malformed":
                value["candidates"][0]["content"]["parts"][0]["text"] = "{bad"
            if failure == "refusal":
                value["candidates"][0]["finishReason"] = "MAX_TOKENS"
            if failure == "tool":
                value["candidates"][0]["content"]["parts"] = [{"functionCall": {"name": "search"}}]
            if failure == "usage":
                value["usageMetadata"]["candidatesTokenCount"] = 2049
            return Reply(json.dumps(value).encode())

    run_id = seed_report(tmp_path)
    critic = GeminiCritic(
        "test-gemini-key", transport=Broken([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, critic=critic, critique_enabled=True) as service:
        before = service.get_run(run_id)
        saved = service.wait(service.submit_critique(run_id, "bad"))
        assert saved.run.state == "failed" and saved.critique is None
        assert saved.report == before.report and saved.analysis == before.analysis
        assert "INCOMPLETE" in service.export_run(run_id)[0]
        assert "test-gemini-key" not in service.export_run(run_id)[1]
        assert service.submit_critique(run_id, "bad") == run_id
        with pytest.raises(ServiceError, match="INVALID_STATE"):
            service.submit_critique(run_id, "another")


def test_critique_ui_explicit_submission_and_finding_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from streamlit.testing.v1 import AppTest

    from synapse.critic import GeminiCritic
    from synapse.ui import resources

    run_id = seed_report(tmp_path)
    wire = CriticWire([])
    critic = GeminiCritic(
        "test-gemini-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, critic=critic) as service:
        monkeypatch.setattr(resources, "get_service", lambda directory: service)
        app = AppTest.from_file(
            str(Path(__file__).parents[1] / "src/synapse/ui/app.py"), default_timeout=10
        )
        app.query_params["run"] = str(run_id)
        app.run()
        assert not app.exception
        assert app.button(key=f"critique-{run_id}").disabled
        assert not wire.destinations
        service.critique_enabled = True
        app.run()
        app.button(key=f"critique-{run_id}").click().run()
        assert service.wait(run_id).run.state == "completed"
        app.run()
        assert not app.exception
        assert app.metric[0].label == "Model critique score" and app.metric[0].value == "8/10"
        assert app.selectbox(key=f"finding-{run_id}")
        assert any("C01: AST matches syntax." in item.value for item in app.text)
        assert len(app.get("download_button")) == 2
        app.run()
        assert len(wire.destinations) == 1


def test_critique_cancellation_busy_and_request_conflicts(tmp_path: Path) -> None:
    from threading import Event

    from synapse.critic import GeminiCritic

    entered, release = Event(), Event()

    class Gated(CriticWire):
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

    run_id = seed_report(tmp_path)
    critic = GeminiCritic(
        "test-gemini-key", transport=Gated([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(tmp_path, critic=critic, critique_enabled=True) as service:
        before = service.get_run(run_id)
        service.submit_critique(run_id, "one")
        try:
            assert entered.wait(5)
            assert service.submit_critique(run_id, "one") == run_id
            with pytest.raises(ServiceError, match="BUSY"):
                service.submit("comparison", "another")
            critic.config = critic.config.model_copy(update={"max_output_tokens": 128})
            with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
                service.submit_critique(run_id, "one")
            service.cancel(run_id)
        finally:
            release.set()
        saved = service.wait(run_id)
        assert saved.run.state == "cancelled" and saved.critique is None
        assert saved.report == before.report
        assert saved.critique_usage and saved.critique_usage.status == "generating"
        assert saved.critique_usage.output_tokens is None


@pytest.mark.parametrize("failure", ["deadline", "artifact"])
def test_critique_deadline_and_disk_failure_retain_saved_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from synapse.critic import GeminiCritic

    clock = [0.0]

    class Expiring(CriticWire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            reply = super().request(method, url, address, timeout, headers, body)
            if failure == "deadline" and url.endswith(":generateContent"):
                clock[0] = 601.0
            return reply

    run_id = seed_report(tmp_path)
    critic = GeminiCritic(
        "test-gemini-key", transport=Expiring([]), resolver=lambda h, t: ["93.184.216.34"]
    )
    with ResearchService(
        tmp_path, critic=critic, critique_enabled=True, clock=lambda: clock[0]
    ) as service:
        before = service.get_run(run_id)
        if failure == "artifact":

            def broken_replace(source: object, destination: object) -> None:
                raise OSError("test disk failure")

            monkeypatch.setattr("synapse.service.os.replace", broken_replace)
        saved = service.wait(service.submit_critique(run_id, "failure"))
        assert saved.run.state == "failed" and saved.report == before.report
        assert (
            saved.run.error
            and ("DEADLINE" if failure == "deadline" else "STORAGE_ERROR") in saved.run.error
        )
        monkeypatch.undo()
        assert "INCOMPLETE" in service.export_run(run_id)[0]
