import json
from pathlib import Path

from synapse.service import ResearchService


def test_completed_fixture_reopens_and_exports_without_rerunning(tmp_path: Path) -> None:
    with ResearchService(tmp_path) as service:
        run_id = service.submit("comparison", "first")
        snapshot = service.wait(run_id)
        assert snapshot.run.state == "completed"
        assert snapshot.discovery and snapshot.analysis and snapshot.report and snapshot.critique
        markdown, bundle = service.export_run(run_id)
        assert "Offline fixture demonstration" in markdown
        assert json.loads(bundle)["run"]["id"] == str(run_id)
        assert service.submit("comparison", "first") == run_id
    with ResearchService(tmp_path) as reopened:
        assert reopened.get_run(run_id) == snapshot
        assert reopened.export_run(run_id) == (markdown, bundle)
        assert len(reopened.list_runs()) == 1


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
