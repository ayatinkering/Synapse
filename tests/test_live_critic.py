"""Opt-in single critique over the saved S-C report; no searches or new synthesis."""

import os
import sqlite3
from pathlib import Path
from uuid import UUID

import pytest

from synapse.critic import GeminiCritic
from synapse.service import ResearchService


@pytest.mark.live
def test_authorized_critic_completes_the_saved_four_stage_run() -> None:
    if os.environ.get("SYNAPSE_CRITIQUE_SMOKE") != "1":
        pytest.skip("Requires explicit authorization and SYNAPSE_CRITIQUE_SMOKE=1")
    if os.environ.get("SYNAPSE_GEMINI_FREE_TIER") != "1":
        pytest.fail("Confirm a free-tier Gemini project before verification")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        pytest.fail("Configure GEMINI_API_KEY locally; never paste it into chat")
    directory = Path(os.environ.get("SYNAPSE_CRITIQUE_DATA_DIR", "data/synapse-d1-smoke"))
    original = Path("data/synapse-sc-smoke-verified/synapse.sqlite3").resolve()
    database = directory / "synapse.sqlite3"
    assert database.resolve() != original, "Preserve the original S-C evidence/report"
    if not database.exists():
        assert original.is_file(), "Saved S-C report required; do not search or synthesize again"
        directory.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"file:{original}?mode=ro", uri=True) as source:
            with sqlite3.connect(database) as copy:
                source.backup(copy)
    run_id = UUID("34fd52bc-e189-45a0-869e-e7010bc20c92")
    with ResearchService(directory, critic=GeminiCritic(key), critique_enabled=True) as service:
        before = service.get_run(run_id)
        snapshot = service.wait(service.submit_critique(run_id, "d1-smoke-v1"), timeout=130)
        print("D1 smoke:", snapshot.run.state, snapshot.run.error)
        assert snapshot.run.state == "completed"
        assert snapshot.discovery == before.discovery and snapshot.analysis == before.analysis
        assert snapshot.report == before.report and snapshot.critique
        assert snapshot.critique.total == sum(snapshot.critique.scores)
        assert snapshot.critique_usage and snapshot.critique_usage.status == "validated"
        assert service.submit_critique(run_id, "d1-smoke-v1") == run_id
        print(
            "Model:",
            snapshot.critique.evaluator_model,
            "score:",
            snapshot.critique.total,
            "findings:",
            len(snapshot.critique.findings),
            "usage:",
            snapshot.critique_usage.model_dump(),
        )
        exports = service.export_run(run_id)
        assert "INCOMPLETE" not in exports[0]
    with ResearchService(directory) as reopened:
        assert reopened.export_run(run_id) == exports
