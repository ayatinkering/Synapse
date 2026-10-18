# Synapse

An inspectable research pipeline: **discovery → analysis → synthesis → critique**.
Offline demonstrations run entirely on authored synthetic fixtures and need no credentials.
S-B adds opt-in Tavily discovery and public HTML evidence extraction for user questions.
Live discovery stops at **sources ready**. S-C adds optional Gemini synthesis over saved
evidence, ending at **report ready**; live critique remains pending S-D1.
S-C live provider compatibility is pending; two token-count preflights failed before generation.
The bounded Tavily smoke gate passed; see STATUS for the exact result and limitations.

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
Fixture cancellation takes effect at stage boundaries. Live runs also check between
queries, retries, redirects, source/body chunks; an in-flight blocking operation may
finish before cancellation is observed. There is no automatic resume. Sources already
checkpointed survive cancellation or interrupted recovery.

## Live discovery (optional)

Keep the app local. Set `TAVILY_API_KEY` in the launch environment using your local
secret manager or a private terminal; never paste it into chat or research fields.
The application does not automatically load `.env` files. Then launch with:

```bash
SYNAPSE_ENABLE_LIVE=1 uv run --no-sync streamlit run src/synapse/ui/app.py --server.address 127.0.0.1
```

Restart after changing server-side configuration. Choose **Live discovery**, enter a
topic/question and optional subquestions/date filter, inspect the query preview, then
press **Start live discovery**. The question and up to two distinct subquestions become
queries. Date filters are requests to the provider, not verified publication dates.
Without enablement/key, preview works but live submission is disabled.

Defaults: three basic searches, five results/query, ten selected sources, 3,000 cleaned
characters/source, 2 MB/response, 15 seconds/fetch attempt, two transient retries, and
600 seconds/run. Each retry can incur provider charges. Returned credits are recorded;
missing usage is unknown and monetary cost is unavailable. Search snippets never become
fetched evidence. Excerpt selection uses term overlap, not a model or semantic judgment.

The service adds `preview_discovery(RunInput)` and `submit_discovery(input, key)` when
constructed with an enabled `TavilySearch` and optional `SafeFetcher`. Live success is
`sources_ready`; fewer than two independent sources is `insufficient_evidence`.
Both export incomplete research bundles; neither manufactures a report or critique.
Transactional SQLite migrations preserve old runs and backfill submission fingerprints;
schema v3 adds synthesis idempotency metadata.

An authorized single-query smoke gate exists separately from offline CI:

```bash
SYNAPSE_LIVE_SMOKE=1 uv run --no-sync pytest -o addopts='--strict-config --strict-markers -ra' -m live -s
```

Run that command **only after authorization** and secure `TAVILY_API_KEY` configuration.
It allows at most three potentially chargeable basic search attempts and five fetched
sources. Results persist under ignored `data/synapse-sb-smoke/`; rerunning against that
directory reopens the same submission rather than spending again. `SYNAPSE_SMOKE_DATA_DIR`
can select another directory; changing it can permit another charged run.

## Cited synthesis (S-C; live verification pending)

Use a replacement `GEMINI_API_KEY` in the server environment; never enter credentials
in research fields. The app does not load `.env` automatically. Confirm your Google
project's free-tier eligibility before setting the confirmation flag; it does not
technically prevent billing on a billed project. With the key already exported:

```bash
SYNAPSE_ENABLE_SYNTHESIS=1 SYNAPSE_GEMINI_FREE_TIER=1 uv run --no-sync streamlit run src/synapse/ui/app.py --server.address 127.0.0.1
```

Select an existing live `sources_ready` run and press **Generate cited report**.
This sends saved question/source metadata/excerpts to Google; it performs no search
or fetch. Review sensitive content before enabling it. `SYNAPSE_GEMINI_MODEL` selects
the model (default `gemini-2.5-flash-lite`). Restart after configuration changes.
Without the flags/key, saved runs remain inspectable and generation is disabled.

The service exposes `submit_synthesis(run_id, idempotency_key)` when constructed with
an enabled `GeminiSynthesis`. The same key/configuration returns the existing attempt;
a different request with that key conflicts. Each saved live run permits one synthesis
attempt, including failures; no automatic retry, fallback, or repair call occurs.

Defaults: input preflight limit 8,192 tokens, output cap 2,048, provider timeout 30 seconds,
and a new 600-second synthesis deadline. One `countTokens` request estimates the serialized
instructions/evidence/schema; generation occurs only if it fits. That estimate is not
an exact full-request billable count. Actual returned usage is checked and persisted;
excess usage fails validation after the call. Unknown usage/cost remains unknown.
Generation disables thinking and exposes no tools. Prompt `synthesis-v1` requires
structured, evidence-linked claims and limitations. Code builds citations and rejects
unknown/cross-run evidence IDs, altered quotes, model links, malformed output, and
refused/truncated responses. Citation integrity does not establish factual support.

`report_ready` exports remain **incomplete** because critique is absent. Saved evidence
survives model errors, cancellation, storage failure, and interrupted recovery.
Provider compatibility has not passed: the authorized attempts failed at token counting,
with the second returning HTTP 404 `NOT_FOUND`. The SDK-aligned contents-only preflight
is tested offline but has not been tried live. The user chose to leave this gate pending.

The opt-in check in `tests/test_live_synthesis.py` copies existing S-B evidence using
SQLite backup and verifies generation/reopen/exports without new searches. Run it only
with fresh explicit authorization, a configured key, `SYNAPSE_SYNTHESIS_SMOKE=1`, and
`SYNAPSE_GEMINI_FREE_TIER=1`. `SYNAPSE_SYNTHESIS_DATA_DIR` chooses its ignored copy;
changing directories can permit a new provider attempt. Preserve failed attempts.

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
or different normalized input/limits is an error. `list_fixtures`, `list_runs`, `get_run`, and `cancel` provide inspection
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

This is single-user local software. Source independence is based only on
distinct normalized URLs and text hashes, not actual independent authorship. Matching
citations/quotes establishes integrity, not semantic support. Fixture runs can finish
before a user can press Cancel; deterministic service tests exercise cancellation.

S-B's authorized live acceptance gate passed; evidence is tracked in STATUS.
S-C is implemented with offline verification; its live acceptance gate remains pending.
Model critique (S-D1), revision (S-D2), and measured evaluation (S-E) remain unimplemented. Public hosting requires a constrained egress service and
access review; the local fetch policy is not a deployment sandbox. PDF, compressed
responses, nonstandard ports, and access-restricted pages are unsupported.

See [status](docs/STATUS.md), [requirements](docs/PRD.md),
[build plan](docs/BUILD_PLAN.md), [architecture](docs/ARCHITECTURE.md),
and [agent instructions](AGENTS.md).
