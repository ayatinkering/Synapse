# Synapse status

Updated: 2026-10-18. Branch: `codex/synapse-offline-pipeline`.

## S-A — complete (offline fixture milestone)

The user approved curated demos and all public testing boundaries. Implemented:

- Versioned Pydantic run/query/source/evidence/claim/report/critique/event contracts.
- Two bundled synthetic scenarios, four typed fixture stages, deterministic evidence,
  citation/quote/ownership validation, source deduplication, and enforced caps.
- One background worker and process ownership lock; persisted idempotency, busy
  rejection, cooperative cancellation/deadline, interrupted recovery, safe errors.
- Real SQLite run/stage/event storage with atomic stage commits; regenerable source,
  report, and JSON artifacts. Completed and incomplete exports share their saved IDs.
- Streamlit scenario preview, history/deep links, progress/cancel, report/evidence,
  sources, critique, details, and actual download controls. Terminal runs stop polling.
- Updated package help, setup/use docs, and Python 3.12/3.13 CI with a locked-runtime
  installed-wheel fixture smoke test. Skills remain unchanged.

## Local verification evidence

Python 3.12.14, uv 0.12.12; runtime lock includes Pydantic 2.14.1,
Streamlit 1.66.0, and filelock 3.32.7.

| Command/check | Observed result |
|---|---|
| `uv sync --locked` | Locked setup succeeded |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 25 files already formatted |
| `uv run --no-sync mypy` | No issues in 19 source/test files |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync pytest -m 'not live'` | 38 passed |
| `uv build --offline` | Source distribution and wheel built |
| Isolated wheel installed in `/tmp/synapse-sa-wheel` and executed from `/tmp` | Bundled catalog loaded and all four fixture stages completed/exported |
| Archive inspection | Fixtures/UI included; skills, caches, environment, and local data excluded |
| SHA-256 preservation comparison | All 34 supplied skill files/lockfile unchanged |

Tests exercise empty/oversized input, rubric score/total constraints, exact evidence
and offsets, cross-run/unknown citations, unsupported quotes, normalized URL/content
duplicates, budgets, success/gap, busy/idempotency conflicts, cancellation/deadlines,
sanitized adapter errors, malformed report/critique output, artifact and SQLite
failures, regeneration, second-process refusal, abrupt crash recovery, and a completed
run reopened/exported in a fresh Python process. Three Streamlit AppTests cover
submission, rerun, claim inspection, download controls, deep links, gaps, invalid
links, and reselecting history after another run.

TDD evidence: contract/service/UI tests were first exercised before their modules
existed. Later regression checks reproduced URL normalization double counting,
missing failed-source IDs in Markdown, and stale recent-run selection before fixes.
The CLI expectation changed deliberately from foundation-only to offline availability.

## Browser acceptance evidence

Local app launched on `http://127.0.0.1:8501`, bound to loopback, without credentials.
The real browser started the comparison with the keyboard, showed completed stages,
opened source provenance/truncation, and inspected the five-dimension fixture critique.
Both download buttons produced files in the user's Downloads directory; the JSON
run/source/evidence identifiers and exact excerpts matched the Markdown/snapshots.
The sparse scenario displayed an evidence gap with incomplete exports. Browser refresh
reopened the same saved run without submitting another. A final server restart and
saved-run check succeeded without re-executing stages. Final downloads again matched
all source/evidence IDs, including the failed source.

Screenshot: `/tmp/synapse-offline-ui.png` (local, not committed).
Generated demo runs remain under ignored `data/synapse/`.

## GitHub and remaining publication checks

- Foundation: `09167c2`; recorded verification: `77dbc03`.
- Offline core: `cdee9d8`, pushed to `codex/synapse-offline-pipeline`.
- Foundation CI: [39118270917](https://github.com/ayatinkering/Synapse/actions/runs/39118270917).
- UI/acceptance increment: `faee139`, pushed to the same branch.
- Final implementation CI: [39120120243](https://github.com/ayatinkering/Synapse/actions/runs/39120120243), success.
  Both Python 3.12 and 3.13 jobs passed frozen setup, lint/format, strict typing,
  all 38 offline tests, builds, and the installed-wheel fixture smoke check.
- This final status-only commit records implementation evidence; it changes no code or tests.
- The empty repository's first pushed branch, `codex/synapse-foundation`, remains
  its default. No merge, default-branch setting change, deployment, or force push.

## Limits and next milestone

S-A uses synthetic snapshots and predetermined synthesis/critique, not live research.
Source independence means distinct normalized URLs/text hashes, not independent authors.
Integrity checks do not establish semantic correctness. Cancellation is cooperative;
fast fixtures may finish before a person presses Cancel. Local single-user use only;
no automatic resume, concurrent jobs, revisions, or published evaluation metrics.
The offline socket guard is a tripwire, not a process/network security sandbox.

S-B (real discovery and safe fetching) is next, but is not started. Live provider
integration and paid calls require a separately authorized milestone and credential
configuration. No OpenAI/Tavily calls, provider keys, or research claims were added.
