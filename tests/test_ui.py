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
    assert all("· completed ·" not in label for label in app.selectbox(key="history").options)
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


def test_live_preview_is_available_without_credentials_but_submission_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SYNAPSE_ENABLE_LIVE", raising=False)
    app = AppTest.from_file(APP, default_timeout=10).run()
    app.radio(key="mode").set_value("Live discovery").run()
    app.text_input(key="topic").set_value("Retrieval").run()
    app.text_area(key="question").set_value("Compare AST and embedding retrieval").run()
    assert not app.exception
    assert app.button(key="start").disabled
    assert any("Compare AST and embedding retrieval" in text.value for text in app.text)
    assert any("TAVILY_API_KEY" in warning.value for warning in app.warning)
    assert not get_service(str(tmp_path)).list_runs()
    get_service.clear()


def test_saved_live_sources_have_honest_labels_and_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from network_fakes import Reply, Wire

    from synapse.fetch import SafeFetcher
    from synapse.models import RunInput
    from synapse.search import TavilySearch
    from synapse.service import ResearchService

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
        transport=Wire(
            [Reply(b"<p>First AST evidence.</p>"), Reply(b"<p>Second embedding evidence.</p>")]
        ),
        resolver=lambda h, t: ["93.184.216.34"],
    )
    with ResearchService(tmp_path, search=search, fetcher=fetcher, live_enabled=True) as service:
        run_id = service.submit_discovery(RunInput(topic="AST", question="AST retrieval"), "ui")
        assert service.wait(run_id).run.state == "sources_ready"
    monkeypatch.setenv("SYNAPSE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(APP, default_timeout=10)
    app.query_params["run"] = str(run_id)
    app.run()
    assert not app.exception
    assert any("Sources ready" in item.value for item in app.success)
    assert len(app.get("download_button")) == 2
    assert any("Live discovery" in caption.value for caption in app.caption)
    assert any("First AST evidence." in item.value for item in app.text)
    assert any("No report" in item.value for item in app.info)
    assert len(get_service(str(tmp_path)).list_runs()) == 1
    get_service.clear()
