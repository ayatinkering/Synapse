# Synapse status

Updated: 2026-10-18. Branch: `codex/synapse-live-discovery`.

## Current checkpoint — S-B complete

Implementation commit: `6cbbe2148a01a60489d2254345bfa778a3f300f9`, pushed to
`origin/codex/synapse-live-discovery`. Based on S-A checkpoint `ae4142c`.
Hosted [CI 39122297374](https://github.com/ayatinkering/Synapse/actions/runs/39122297374)
succeeded on Python 3.12 and 3.13, including setup, lint, formatting, mypy, offline
tests, distributions, and an installed-wheel fixture run outside the checkout.

Implemented deterministic query preview, explicit fixture/live identity, request
fingerprints, Tavily basic search with persisted attempts/usage, pinned-IP public HTML
fetching, bounded DNS/redirects/retries/streaming, cleaned snapshots, heuristic exact
evidence, per-source SQLite checkpoints, and terminal `sources_ready`. UI previews,
source inspection, history/deep links, and incomplete Markdown/JSON exports work
without inventing synthesis or critique. Server-side key/enablement gates new live
submissions. Existing skills and lockfile were preserved.

### S-B verification performed

| Command/check | Actual result |
|---|---|
| `uv sync --locked` | Passed; 54 packages resolved, 52 checked |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 34 files formatted |
| `uv run --no-sync mypy` | No issues in 28 source/test files |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync pytest -m 'not live'` | 79 passed, 1 live test deselected |
| `uv build` and final `uv build --offline` | Source distribution and wheel built; initial sandbox registry failure was retried with network permission |
| Isolated wheel in `/tmp/synapse-sb-wheel`, script executed from `/tmp` | New adapter imports, query preview, fixture completion, and matching reopened exports passed |
| Distribution archive inspection | Adapters/UI/fixture resources included; local data, caches, environment, and skills excluded |
| Authored S-A schema test and actual original database copied to temporary storage | Both original runs and all six stage outputs preserved; original database unchanged |
| `git diff --check`; skill diff inspection | Passed; no changes to `.agents/skills` or `skills-lock.json` |

New tests cover query/response limits, ranks/snippets/usage, visible retries/backoff,
malformed responses, authentication/quota stops, duplicate normalized URLs, partial
query failures, exact cleaned evidence, truncation/date metadata, unsafe IPv4/IPv6 and
mixed DNS, redirect rebinding/downgrade/caps, unsupported MIME/encoding, denied access,
streamed/declared size caps, slow streams, TLS configuration/failure, source checkpoints,
cancellation/deadlines, and migrated/reopened exports. All S-A checks remain in place.
TLS configuration/failure tests inject the external library boundary; live TLS/provider
compatibility still needs the authorized smoke run.

TDD regressions reproduced missing preview/submission interfaces, missing in-flight
search checkpoints, duplicate trailing-slash fetches, incomplete Markdown provenance,
and stale browser history labels. Fixes passed their affected checks. Review also
kept artifact writes ahead of terminal success and escaped untrusted UI titles.

### S-B real-browser evidence

Launched on loopback `http://127.0.0.1:8502`, using isolated
`/tmp/synapse-sb-browser/` data. Verified live question preview and disabled submission
without credentials, keyboard traversal, keyboard-started fixture completion, source
provenance/exact excerpts, history selection, and actual Markdown/JSON downloads.
Downloaded run/source IDs and exact excerpts matched. A real-browser download rerun
exposed volatile history labels being sent as a run link; stable labels plus UUID
validation fixed this, and another download retained the correct run URL.

Browser fixture run: `75e5b1ff-5cd9-4ca0-a7ad-8b672d2d31a4`.
Screenshot: `/tmp/synapse-sb-browser.png`. Browser checks used synthetic fixture data,
not a Tavily result. Five AppTests additionally cover saved live-source inspection,
missing-credential submission gating, rerun/history, errors, and download controls.

### Authorized live verification

The user authorized the bounded run and configured the ignored local `.env` key.
Executed the documented opt-in live pytest check using only that variable from the
local file: **1 passed, 79 deselected in 59.20 seconds**. No key was printed or tracked.
The single query had an initial DNS timeout, then a successful search reporting
**1.0 credit**. Four sources fetched, one source failed with `NETWORK_ERROR`, and
12 exact evidence excerpts were saved. The run ended at `sources_ready`; reopening
reproduced equivalent exports without another search.

Saved run: `34fd52bc-e189-45a0-869e-e7010bc20c92`, under ignored
`data/synapse-sb-smoke/`. The UI at loopback port 8503 reopened it without enabling
new live submissions. Browser inspection showed success/failure states, capped text,
unknown dates, evidence, absent report/critique, and two saved stages. Actual browser
Markdown/JSON downloads matched the persisted run/source IDs and exact excerpts;
exports remained explicitly incomplete. Screenshot: `/tmp/synapse-sb-live.png`.
No additional provider smoke run was launched.

### Remaining limitations and next task

S-B's authorized live gate passed. Next milestone is S-C: plan cited synthesis,
model configuration, token budgets, prompts, testing boundaries, and secure credential
setup before implementing it. The completed S-B authorization is not permission for
additional charged searches or model calls. Reopen the saved smoke run instead of
changing its data directory/idempotency key and spending again.

The live result included older documentation mirrors and retained some navigation
text in legacy HTML. Sentence-based selection can split abbreviations/code filenames.
These extraction/ranking limitations are visible; this was a compatibility smoke
check, not an evaluation of relevance, currency, or research quality.

S-B selects excerpts heuristically; it does not establish semantic support. Publication
metadata can be unknown or inaccurate. Source independence is URL/hash based, not
independent authorship. HTML only; compressed responses, nonstandard ports, PDF/OCR,
model planning/synthesis/critique, cache reuse, and benchmarks are out of scope.
Cancellation is cooperative, and public hosting still requires constrained egress.
No merge, deployment, force push, or OpenAI calls were performed.

### Next-session protocol

Read [AGENTS.md](../AGENTS.md) and this file, inspect `git status --short --branch`,
recent commits and the remote, then verify actual state/relevant checks before relying
on this checkpoint. Consult [BUILD_PLAN.md](BUILD_PLAN.md), [PRD.md](PRD.md),
[ARCHITECTURE.md](ARCHITECTURE.md), and [README.md](../README.md) for existing decisions.
Temporary handoff notes: `/tmp/synapse-session-handoff.md`; they may disappear.

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
- Status checkpoint: `6442e60`; its CI also passed. The session-close update changes
  documentation only.
- The empty repository's first pushed branch, `codex/synapse-foundation`, remains
  its default. No merge, default-branch setting change, deployment, or force push.

## Limits and next milestone

S-A uses synthetic snapshots and predetermined synthesis/critique, not live research.
Source independence means distinct normalized URLs/text hashes, not independent authors.
Integrity checks do not establish semantic correctness. Cancellation is cooperative;
fast fixtures may finish before a person presses Cancel. Local single-user use only;
no automatic resume, concurrent jobs, revisions, or published evaluation metrics.
The offline socket guard is a tripwire, not a process/network security sandbox.

The S-A checkpoint above is historical. Completed S-B verification is recorded at
the top of this file. S-C remains unstarted.
