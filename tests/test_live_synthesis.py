"""Opt-in Gemini compatibility check: one count + one generation, never new searches."""

import os
import sqlite3
from pathlib import Path
from uuid import UUID

import pytest

from synapse.service import ResearchService
from synapse.synthesis import GeminiSynthesis


@pytest.mark.live
def test_authorized_gemini_synthesis_over_saved_sources() -> None:
    if os.environ.get("SYNAPSE_SYNTHESIS_SMOKE") != "1":
        pytest.skip("Requires explicit authorization and SYNAPSE_SYNTHESIS_SMOKE=1")
    if os.environ.get("SYNAPSE_GEMINI_FREE_TIER") != "1":
        pytest.fail("Confirm the Gemini project uses free-tier quota before verification")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        pytest.fail("Configure a replacement Gemini key locally; never paste it into chat")
    directory = Path(os.environ.get("SYNAPSE_SYNTHESIS_DATA_DIR", "data/synapse-sc-smoke"))
    original = Path("data/synapse-sb-smoke/synapse.sqlite3").resolve()
    database = directory / "synapse.sqlite3"
    assert database.resolve() != original, "Smoke verification must copy, not mutate S-B evidence"
    if not database.exists():
        assert original.is_file(), "A saved S-B smoke database is required; do not search again"
        directory.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"file:{original}?mode=ro", uri=True) as source:
            with sqlite3.connect(database) as copy:
                source.backup(copy)
    adapter = GeminiSynthesis(key)
    run_id = UUID("34fd52bc-e189-45a0-869e-e7010bc20c92")
    with ResearchService(directory, synthesis=adapter, synthesis_enabled=True) as service:
        service.submit_synthesis(run_id, "sc-gemini-smoke-v1")
        snapshot = service.wait(run_id, timeout=130)
        print(
            f"Gemini smoke: {snapshot.run.id} state={snapshot.run.state} error={snapshot.run.error}"
        )
        assert snapshot.run.state == "report_ready"
        assert snapshot.report and snapshot.synthesis and snapshot.critique is None
        print("Verified model:", snapshot.run.model_id, "usage:", snapshot.synthesis.model_dump())
        exports = service.export_run(run_id)
    with ResearchService(directory) as reopened:
        assert reopened.export_run(run_id) == exports
