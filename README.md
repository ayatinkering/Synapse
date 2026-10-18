# Synapse

An inspectable research pipeline: **discovery → analysis → synthesis → critique**.
S-A runs entirely on authored synthetic fixtures. It makes no search/model calls,
needs no credentials, and does **not** answer arbitrary research questions.

Choose the AST-versus-embedding comparison or the sparse-evidence scenario, inspect
saved source snapshots and exact evidence excerpts, reopen runs, and download
Markdown/JSON bundles. Critique scores and findings are predetermined demonstrations,
not model evaluations or evidence of research quality.

## Setup and launch

Install Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/),
then run from the repository root:

```bash
uv sync --locked
uv run --no-sync streamlit run src/synapse/ui/app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit (normally `http://127.0.0.1:8501`).
Setup downloads locked dependencies; the fixture workflow itself needs no external
services. Usage telemetry is disabled in the project Streamlit configuration.

Default data lives under ignored `data/synapse/`. To use a separate local directory:

```bash
SYNAPSE_DATA_DIR=/tmp/synapse-demo uv run --no-sync streamlit run src/synapse/ui/app.py --server.address 127.0.0.1
```

Only one application process may own a data directory, and only one run may be
queued/running at once. Reruns do not resubmit jobs. On process restart, unfinished
runs are marked interrupted; their completed stage outputs remain inspectable.
Cancellation takes effect at stage boundaries. There is no automatic resume.

## Inspect and export

- Preview the fixed question, queries, and limits, then press **Start offline run**.
- Report: inspect the report and select a claim to see its exact evidence.
- Sources & Evidence: open snapshots, source failures, hashes, and truncation/date labels.
- Critique: inspect all five rubric scores and claim-linked predetermined findings.
- Run Details: inspect configuration, typed discovery output, and ordered events.
- Download Markdown or JSON after completion, cancellation, failure, or an evidence gap.
  Incomplete exports are labeled and do not invent missing stages.

The run ID in the page URL reopens the saved run after browser refresh. The sidebar
also lists saved runs. SQLite is authoritative; missing derived source/report files
are regenerated on export. A different preview scenario does not change the saved
run currently being inspected.

## Python service

```python
from pathlib import Path
from synapse.service import ResearchService

with ResearchService(Path("/tmp/synapse-python-demo")) as service:
    run_id = service.submit("comparison", idempotency_key="example-1")
    snapshot = service.wait(run_id)
    markdown, json_bundle = service.export_run(run_id)
    print(snapshot.run.state)
```

Reuse a submission key to retrieve the same run. Reusing it for another scenario
is an error. `list_fixtures`, `list_runs`, `get_run`, and `cancel` provide inspection
and cancellation. Do not create a second service for data owned by a running UI.
Public service errors carry safe codes; arbitrary adapter exceptions are not exported.

## Verification

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync pytest -m 'not live'
uv build
```

CI exercises Python 3.12/3.13, including fixture execution from the built wheel in
an isolated environment outside the checkout. Tests use temporary real SQLite
stores, fixture adapters, injected clocks/barriers, subprocess restart checks,
and Streamlit AppTest. A socket guard catches accidental in-process connections;
it is not an OS sandbox and does not constrain subprocess networking.

`uv.lock` freezes dependencies; `uv.toml` keeps the cache under ignored `.uv-cache/`.
Installed skills are preserved, versioned, and excluded from owned-code lint/type
checks and package distributions. No secrets or generated run data belong in Git.

## Limits and next steps

This is single-user local software. Synthetic source independence is based only on
distinct normalized URLs and text hashes, not actual independent authorship. Matching
citations/quotes establishes integrity, not semantic support. Fixture runs can finish
before a user can press Cancel; deterministic service tests exercise cancellation.

Live search/safe fetching (S-B), model synthesis (S-C), model critique (S-D1), one
revision (S-D2), and measured evaluation (S-E) remain unimplemented. No provider
credentials, deployment, or paid calls are needed for S-A.

See [status](docs/STATUS.md), [requirements](docs/PRD.md),
[build plan](docs/BUILD_PLAN.md), [architecture](docs/ARCHITECTURE.md),
and [agent instructions](AGENTS.md).
