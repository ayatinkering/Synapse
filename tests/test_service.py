import json
import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest

from synapse.fixtures import FixtureAdapter
from synapse.models import Analysis, Critique, Discovery, Limits, Report, Run
from synapse.service import ResearchService
from synapse.storage import ServiceError


def test_completed_fixture_reopens_and_exports_without_rerunning(tmp_path: Path) -> None:
    with ResearchService(tmp_path) as service:
        run_id = service.submit("comparison", "first")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "completed"
        assert snapshot.discovery and snapshot.analysis and snapshot.report and snapshot.critique
        markdown, bundle = service.export_run(run_id)
        assert "Offline fixture demonstration" in markdown
        assert json.loads(bundle)["run"]["id"] == str(run_id)
        for source in snapshot.analysis.sources:
            assert str(source.id) in markdown
        assert service.submit("comparison", "first") == run_id
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot
        assert reopened.export_run(run_id) == (markdown, bundle)
        assert len(reopened.list_runs()) == 1
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; from uuid import UUID; "
            "from synapse.service import ResearchService; "
            "s=ResearchService(Path(sys.argv[1])); "
            "print(s.export_run(UUID(sys.argv[2]))[1]); s.close()",
            str(tmp_path),
            str(run_id),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert json.loads(result.stdout) == json.loads(bundle)


def test_sparse_fixture_is_an_exportable_gap(tmp_path: Path) -> None:
    with ResearchService(tmp_path) as service:
        run_id = service.submit("sparse", "gap")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "insufficient_evidence"
        assert snapshot.analysis is not None
        assert snapshot.report is None
        markdown, bundle = service.export_run(run_id)
        assert "INCOMPLETE" in markdown
        assert json.loads(bundle)["report"] is None


class GatedAdapter(FixtureAdapter):
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()

    def analyze(self, run: Run, discovery: Discovery) -> Analysis:
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("Test gate timed out")
        return super().analyze(run, discovery)


def test_busy_and_idempotency_while_worker_is_running(tmp_path: Path) -> None:
    adapter = GatedAdapter()
    with ResearchService(tmp_path, stages=adapter) as service:
        run_id = service.submit("comparison", "same")
        try:
            assert adapter.entered.wait(5)
            assert service.submit("comparison", "same") == run_id
            with pytest.raises(ServiceError, match="BUSY"):
                service.submit("comparison", "other")
            with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
                service.submit("sparse", "same")
            assert len(service.list_runs()) == 1
        finally:
            adapter.release.set()
        assert service.wait(run_id).run.state == "completed"


@pytest.mark.parametrize("outcome", ["cancelled", "deadline"])
def test_cancellation_and_deadline_preserve_prior_outputs(tmp_path: Path, outcome: str) -> None:
    adapter = GatedAdapter()
    clock = [0.0]
    with ResearchService(tmp_path, stages=adapter, clock=lambda: clock[0]) as service:
        run_id = service.submit("comparison", outcome)
        try:
            assert adapter.entered.wait(5)
            if outcome == "cancelled":
                service.cancel(run_id)
            else:
                clock[0] = 601
        finally:
            adapter.release.set()
        snapshot = service.wait(run_id)
        assert snapshot.run.state == ("cancelled" if outcome == "cancelled" else "failed")
        assert snapshot.discovery and snapshot.analysis and snapshot.report is None
        assert snapshot.run.error
        assert ("CANCELLED" if outcome == "cancelled" else "DEADLINE") in snapshot.run.error
        before = snapshot
        service.cancel(run_id)
        assert service.get_run(run_id) == before
        assert "INCOMPLETE" in service.export_run(run_id)[0]


def test_stage_failure_does_not_leak_adapter_errors(tmp_path: Path) -> None:
    class Broken(FixtureAdapter):
        def analyze(self, run: Run, discovery: Discovery) -> Analysis:
            raise ValueError("secret-provider-value")

    with ResearchService(tmp_path, stages=Broken()) as service:
        run_id = service.submit("comparison", "broken")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "failed" and snapshot.discovery
        assert "secret-provider-value" not in service.export_run(run_id)[1]


def test_artifact_write_failure_is_not_reported_as_completion(tmp_path: Path) -> None:
    (tmp_path / "runs").write_text("Cannot create directories here")
    with ResearchService(tmp_path) as service:
        snapshot = service.wait(service.submit("comparison", "disk"))
        assert snapshot.run.state == "failed" and snapshot.analysis
        assert snapshot.run.error and "STORAGE_ERROR" in snapshot.run.error


def test_missing_artifacts_are_rebuilt_from_sqlite(tmp_path: Path) -> None:
    with ResearchService(tmp_path) as service:
        run_id = service.submit("comparison", "rebuild")
        service.wait(run_id)
        original = service.export_run(run_id)
        (tmp_path / "runs" / str(run_id) / "bundle.json").unlink()
        assert service.export_run(run_id) == original
        assert (tmp_path / "runs" / str(run_id) / "bundle.json").exists()


def test_second_process_cannot_own_directory(tmp_path: Path) -> None:
    with ResearchService(tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from synapse.service import ResearchService; "
                "import sys; ResearchService(Path(sys.argv[1]))",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0 and "IN_USE" in result.stderr


def test_crashed_process_reopens_partial_run_without_rerunning(tmp_path: Path) -> None:
    script = """
from pathlib import Path
import os, sys
from synapse.service import ResearchService
from synapse.fixtures import FixtureAdapter
class Crash(FixtureAdapter):
    def analyze(self, run, discovery):
        os._exit(23)
service = ResearchService(Path(sys.argv[1]), stages=Crash())
service.wait(service.submit('comparison', 'crash'))
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], timeout=10)
    assert result.returncode == 23
    with ResearchService(tmp_path) as reopened:
        run = reopened.list_runs()[0]
        snapshot = reopened.get_run(run.id)
        assert run.state == "failed" and run.error and "INTERRUPTED" in run.error
        assert snapshot.discovery and snapshot.analysis is None
        assert [e.sequence for e in snapshot.events] == list(range(1, len(snapshot.events) + 1))
        assert "INCOMPLETE" in reopened.export_run(run.id)[0]


@pytest.mark.parametrize(
    "limits", [Limits(max_queries=1), Limits(results_per_query=1), Limits(max_sources=1)]
)
def test_caps_are_enforced_outside_adapter(tmp_path: Path, limits: Limits) -> None:
    with ResearchService(tmp_path, limits=limits) as service:
        snapshot = service.wait(service.submit("comparison", "budget"))
        assert snapshot.run.state == "failed" and snapshot.discovery is None


def test_sqlite_write_failure_surfaces_storage_error(tmp_path: Path) -> None:
    adapter = GatedAdapter()
    with ResearchService(tmp_path, stages=adapter) as service:
        run_id = service.submit("comparison", "unwritable-db")
        assert adapter.entered.wait(5)
        database = tmp_path / "synapse.sqlite3"
        saved = tmp_path / "saved.sqlite3"
        database.rename(saved)
        database.mkdir()
        try:
            adapter.release.set()
            with pytest.raises(ServiceError, match="STORAGE_ERROR"):
                service.wait(run_id)
        finally:
            database.rmdir()
            saved.rename(database)


@pytest.mark.parametrize("bad_stage", ["report", "critique"])
def test_malformed_outputs_cannot_complete(tmp_path: Path, bad_stage: str) -> None:
    class Malformed(FixtureAdapter):
        def synthesize(self, run: Run, analysis: Analysis) -> Report:
            report = super().synthesize(run, analysis)
            if bad_stage == "report":
                bad = report.claims[0].model_copy(update={"quote": "Invented quote"})
                return report.model_copy(update={"claims": [bad]})
            return report

        def critique(self, run: Run, report: Report) -> Critique:
            return super().critique(run, report).model_copy(update={"scores": [99]})

    with ResearchService(tmp_path, stages=Malformed()) as service:
        run_id = service.submit("comparison", bad_stage)
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "failed"
        assert snapshot.analysis and snapshot.critique is None
        assert (snapshot.report is None) == (bad_stage == "report")
        assert "INCOMPLETE" in service.export_run(run_id)[0]
