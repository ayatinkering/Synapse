"""Opt-in, potentially chargeable compatibility check. Never selected by default."""

import os
from pathlib import Path

import pytest

from synapse.models import Limits, RunInput
from synapse.search import TavilySearch
from synapse.service import ResearchService


@pytest.mark.live
def test_authorized_single_query_tavily_smoke() -> None:
    if os.environ.get("SYNAPSE_LIVE_SMOKE") != "1":
        pytest.skip("Requires explicit authorization and SYNAPSE_LIVE_SMOKE=1")
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        pytest.fail("Configure TAVILY_API_KEY securely before the authorized smoke check")
    directory = Path(os.environ.get("SYNAPSE_SMOKE_DATA_DIR", "data/synapse-sb-smoke"))
    input = RunInput(
        topic="Python AST documentation",
        question="Python ast module official documentation syntax trees",
    )
    with ResearchService(
        directory,
        search=TavilySearch(key),
        live_enabled=True,
        limits=Limits(max_queries=1, max_sources=5),
    ) as service:
        # A repeat against this directory reopens the original run; it cannot silently spend again.
        run_id = service.submit_discovery(input, "sb-live-smoke-v1")
        snapshot = service.wait(run_id, timeout=610)
        print(f"Live smoke saved: {directory.resolve()} run={run_id} state={snapshot.run.state}")
        assert snapshot.discovery and len(snapshot.discovery.queries) == 1
        assert snapshot.discovery.queries[0].status == "success"
        assert snapshot.analysis and any(s.status == "fetched" for s in snapshot.analysis.sources)
        assert snapshot.run.state == "sources_ready"
        assert snapshot.report is None and snapshot.critique is None
        original = service.export_run(run_id)
    with ResearchService(directory) as reopened:
        assert reopened.export_run(run_id) == original
