from pathlib import Path
from uuid import UUID

import pytest
from streamlit.testing.v1 import AppTest

from synapse.ui.resources import get_service

APP = str(Path(__file__).parents[1] / "src/synapse/ui/app.py")


def test_start_inspect_rerun_and_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(APP, default_timeout=10).run()
    assert not app.exception
    app.button(key="start").click().run()
    run_id = UUID(app.session_state["selected_run"])
    service = get_service(str(tmp_path))
    service.wait(run_id)
    app.run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Report",
        "Sources & Evidence",
        "Critique",
        "Run Details",
    ]
    assert "completed" in app.success[0].value
    assert app.selectbox(key=f"claim-{run_id}")
    assert len(app.get("download_button")) == 2
    app.run()
    assert len(service.list_runs()) == 1
    assert app.query_params["run"] == str(run_id)
    get_service.clear()


def test_reopen_gap_and_invalid_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    service = get_service(str(tmp_path))
    run_id = service.submit("sparse", "gap")
    service.wait(run_id)
    app = AppTest.from_file(APP, default_timeout=10)
    app.query_params["run"] = str(run_id)
    app.run()
    assert not app.exception
    assert any("EVIDENCE_GAP" in error.value for error in app.error)
    assert len(app.get("download_button")) == 2
    assert len(service.list_runs()) == 1
    app.query_params["run"] = "not-a-uuid"
    app.run()
    assert not app.exception
    assert any("Invalid run link" in error.value for error in app.error)
    get_service.clear()


def test_history_can_reselect_an_older_run_after_starting_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    service = get_service(str(tmp_path))
    first = service.submit("comparison", "first")
    service.wait(first)
    app = AppTest.from_file(APP, default_timeout=10).run()
    app.selectbox(key="history").select(str(first)).run()
    app.button(key="start").click().run()
    second = UUID(app.session_state["selected_run"])
    service.wait(second)
    app.run()
    app.selectbox(key="history").select("Choose a saved run").run()
    app.selectbox(key="history").select(str(first)).run()
    assert app.query_params["run"] == str(first)
    assert app.session_state["selected_run"] == str(first)
    assert len(service.list_runs()) == 2
    get_service.clear()
