# Synapse status

Updated: 2026-10-18. Branch: `codex/synapse-live-critique`.

## Current checkpoint — S-D1 complete

Implementation/README commit: `5a0e3ec`, branch `codex/synapse-live-critique`, based on
verified S-C `b4fcbbf`. The user requested the smallest complete D1 and a clear README
using the reference repository's presentation without hackathon framing. The README
now uses an overview, badges, pipeline, quick start, inspection, limits, structure,
testing and scope; detailed verification history stays here.

Implemented one explicit `submit_critique(run_id, idempotency_key)` over a saved live
report. The critic reuses Gemini transport, token checks, usage checkpoints and the
single worker. It returns five strict scores (0–2) and bounded claim-linked findings;
application code calculates the total and validates ownership/version. Report/evidence
remain unchanged. Successful critique ends the run at `completed`; failed/cancelled
critique preserves prior outputs and remains visibly incomplete. No automatic retry,
repair, revision, new framework, dependency, SQL table or schema migration was added.
Configuration/key are persisted in run JSON under the existing transactional ownership
checks; the local run scan trades scalability for simplicity. Old optional fields
reopen compatibly. Installed skills, lockfiles, existing runs and prior work are preserved.

### Verification performed

| Command/check | Actual result |
|---|---|
| `uv sync --locked` | Passed; 54 resolved, 52 checked |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 40 files formatted |
| `uv run --no-sync mypy` | No issues in 34 files |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync pytest -m 'not live'` | 123 passed, 3 live deselected in 31.76 seconds |
| Authorized opt-in `tests/test_live_critic.py` | 1 passed in 4.89 seconds; preserved input/report, complete state, idempotency and reopened exports |
| `uv build --offline` | Wheel and source distribution built |
| Isolated wheel `/tmp/synapse-d1-wheel`, executed from `/tmp` | Critic import, identical regenerated live bundle, and four-stage fixture passed without provider calls |
| Clean Git archive `/tmp/synapse-d1-clean-checkout` | `uv sync --locked --offline` using the existing package cache passed; package version, critic import and fixture completion/export passed |
| Distribution/ignore inspection and `git diff --check` | Passed; no secrets, runtime data, skills or caches in archives; skills/dependency lockfiles unchanged |

The approved service/export/UI boundaries are reused. New checks cover completion,
report preservation/reopen, explicit credential-gated UI submission, finding inspection,
score count/bounds/types, unexpected totals, unknown claim IDs, empty/oversized comments,
missing findings on a reduced score, malformed/refused/tool/link output, quota/budgets,
usage, cancellation, busy/conflicting requests, deadline and disk failure. All earlier
fixture/discovery/synthesis checks remain. Regressions first failed for missing critique
behavior and missing critic prompt provenance in Markdown, then passed after fixes.
No acceptance check was weakened.

### Authorized live and browser result

The confirmed free-tier Gemini key was read locally without printing it. One count
and one generation succeeded; **no new Tavily or synthesis calls**. The saved S-C
report was copied with SQLite backup to ignored `data/synapse-d1-smoke/`; original
S-B/S-C stores were preserved. Run: `34fd52bc-e189-45a0-869e-e7010bc20c92`.

Evaluator/model version: `gemini-3.5-flash-lite`; prompt: `critic-v1`.
Preflight estimate: **6,366** tokens. Actual input **5,978**, output **118**, thinking
**0**, total **6,096**. Default cap remains 8,192 input / 2,048 output, 30 seconds per
request, 600 seconds per stage job, minimal thinking, no retries. Actual monetary cost
is unavailable; the free-tier flag is confirmation, not a billing control.

The model returned scores **[2, 2, 1, 1, 2]**, total **8/10**, and **one finding**.
These are model judgments from one compatibility example, not a measured quality result.
All four actual stage outputs are now present in the saved run. Its search/evidence/report
are the existing S-B/S-C results, not a new end-to-end provider run in this session.

Browser on loopback port 8506, with provider submission disabled, reopened the complete
run and showed 4/4 saved outputs. Keyboard activation opened Critique; inspected the
five scores/evaluator, finding linked to C05, and its exact E09 excerpt. Actual downloads
`~/Downloads/synapse-34fd52bc-e189-45a0-869e-e7010bc20c92 (3).md` and `(2).json` matched
SQLite report/evidence/critique/usage and full evidence IDs, with no incomplete marker.
Critic prompt provenance is present in Markdown. Screenshot: `/tmp/synapse-d1-critique.png`.
AppTest separately verified explicit submission, disabled configuration, rerun idempotency,
score labels, finding inspection, and download controls. No provider call was made in
the browser. Browser automation was slow but completed.

### Remaining limitations and next task

The first local four-stage P0 workflow is complete. Next optional milestone:
**S-D2 — one bounded revision**, followed by **S-E — measured evaluation**. Do not
start either without the user's request. Additional provider calls require relevant
authorization; reopen this saved run instead of changing smoke directories to spend.

No semantic-support/usefulness benchmark or human grounding audit was performed. A score
is not a fact check; the same model writes and critiques. Older mirrors, imperfect HTML
extraction, heuristic evidence selection and URL/hash-only independence remain limitations.
The immutable saved report can retain its original generation-time pending-critique label
inside raw JSON; run state and current UI/export status correctly show completion.
Preflight is an estimate, unknown-response usage remains unknown, cancellation is
cooperative, and failed stages do not automatically resume or retry. Local single-user
use only; no revision, PDF/OCR, scheduled research, multi-user/public-hosting readiness,
merge, deployment, force push or paid-tier switch was introduced.

Hosted CI for this increment is reported separately. Read AGENTS and this STATUS,
inspect Git status/branch/recent commits/remote, and verify relevant current behavior
before relying on this checkpoint. Temporary continuation notes:
`/tmp/synapse-session-handoff.md`.

## Historical S-C checkpoint — complete


Implementation: `4a06751`; verified completion/fixes: `6fd1b69`.
Branch: `codex/synapse-cited-synthesis`, based on S-B `07a8a56`.
User selected Gemini, confirmed a replacement local key/free-tier project, and later
requested completion of the previously pending gates. Installed skills, dependency
lockfile, original S-B evidence and all failed S-C copies are preserved. No new Tavily
search, merge, deployment, or force push was performed.

S-C explicitly synthesizes a saved live `sources_ready` run once, ending at
`report_ready` with critique absent. Structured claims, this run's evidence IDs,
exact quotes, text bounds and actual usage validate before normal success. Schema v3
persists synthesis configuration/idempotency and typed checkpoints. UI reruns cannot
resubmit an attempt; failures retain saved evidence. Markdown/JSON share full evidence
UUIDs, source IDs, report version, configuration and usage; exports remain incomplete
because S-D1 critique is not implemented.

### Final local verification

| Command/check | Actual result |
|---|---|
| `uv sync --locked` | Passed; 54 resolved, 52 checked |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 37 files formatted |
| `uv run --no-sync mypy` | No issues in 31 files |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync pytest -m 'not live'` | 102 passed, 2 live deselected in 20.35 seconds |
| Opt-in `tests/test_live_synthesis.py`, authorized bounded run | 1 passed in 4.98 seconds; reopen/export equivalence verified |
| `uv build --offline` | Wheel and source distribution built, including after final documentation changes |
| Isolated installed wheel under `/tmp/synapse-sc-wheel`, executed from `/tmp` | Copied live report reopened and regenerated identical browser exports without provider calls; bundled fixture completed |
| `git diff --check`; skill/lockfile inspection | Passed; skills and lockfiles unchanged |

Tests retain the approved service/export/UI boundaries and offline network injection.
They cover malformed/refused/truncated output, unknown/actual cross-run UUIDs, unsupported
quotes, oversized/empty claims, usage and input budgets, quota/network/provider failures,
forbidden tools/links, cancellation/deadline, artifact failure/regeneration, gated explicit
UI submission, exact evidence, downloads and reopen. Regressions failed before fixes for
the default/wire contract, missing Markdown evidence UUIDs, and the five-second header
wait overriding the configured provider budget. No application acceptance check was weakened.

### Authorized live result and browser acceptance

Run: `34fd52bc-e189-45a0-869e-e7010bc20c92`, in ignored
`data/synapse-sc-smoke-verified/` (SQLite backup of the original S-B evidence).
One preflight and one generation succeeded, with no automatic retry/search/fetch.
Model and returned model version: **`gemini-3.5-flash-lite`**; prompt: `synthesis-v1`.
Preflight estimate: **2,665** tokens; actual input: **2,257**, output: **690**, thinking:
**0**, total: **2,947**. Limits: 8,192 input / 2,048 output, minimal thinking,
30 seconds/provider attempt, 600 seconds/stage job. Monetary cost is unavailable;
free-tier eligibility is the user's confirmed project configuration, not a billing cap.

The UI on loopback port 8505 reopened that persisted report with new model calls disabled.
Verified three saved stages, report-ready/critique-pending labels, the generated C01 claim's
exact E02 excerpt/source offsets, and keyboard activation of the E02 citation anchor.
Actual browser downloads:
`~/Downloads/synapse-34fd52bc-e189-45a0-869e-e7010bc20c92 (1).md` and `.json`.
Both matched the persisted report/source/evidence IDs, exact stored evidence and usage;
critique stayed absent. Installed-wheel reopening regenerated matching exports in a
fresh temporary directory with no credentials/provider calls. Screenshot:
`/tmp/synapse-sc-live-verified.png`. Browser automation was unusually slow; no provider
calls were made through the browser.

### Preserved failures and compatibility investigation

Earlier attempts remain under ignored `data/synapse-sc-smoke*/`. Three pipeline copies
stopped at preflight on the old model; five more preserved provider configuration
rejections before the successful final copy. The original S-B database was not modified.
A fixed-word diagnostic count returned Google's explicit explanation that 2.5 Flash-Lite
is no longer available to new users, despite its presence in model metadata. The default
was updated to 3.5 Flash-Lite; no automatic fallback was introduced.

Controlled tiny probes isolated a UUID-enum schema rejection: the same report schema
was accepted when its evidence UUID enum was removed. Nullable-type and extra-property
variants still failed. The provider grammar now uses inline string IDs and omits
unsupported string-length keywords; Pydantic and run-owned evidence/quote validators
still reject invalid outputs. The current `responseFormat.text` configuration and REST
`MINIMAL` enum are used. Connection/header wait now respects the caller's budget;
the absolute watchdog and remaining run deadline remain enforced.

Three successful diagnostic generations reported totals of 12, 2,266 and 23 tokens.
An earlier 16-output-token diagnostic timed out under the old five-second transport cap;
its usage is unknown. Rejected requests also lacked usage. Do not interpret the final
successful run's usage as total session consumption or invent a monetary total. Some
error-inspection copies show `UNKNOWN` because temporary diagnostics consumed their
error bodies before the service's allowlisted status parser; raw bodies/keys were not
persisted. Diagnostic scripts live only under `/tmp` and are not runtime features.

Official contracts used: [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[REST generation configuration](https://ai.google.dev/api/generate-content),
[structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[token counting](https://ai.google.dev/api/tokens), and
[pricing](https://ai.google.dev/gemini-api/docs/pricing).

### Next task and limitations

Next incomplete milestone: **S-D1 — live critic and first complete P0 release**.
Use BUILD_PLAN/PRD to scope its scores, finding IDs, budgets and integration checks.
Additional provider calls still require relevant authorization; reuse saved evidence.
Do not rerun smoke scripts under new directories merely to reproduce this checkpoint.

S-C verifies compatibility/provenance, not semantic correctness or benchmark quality.
The saved sources include older mirrors and imperfect extraction. Free-tier flags do
not enforce billing limits. Contents-only preflight is an estimate, not an exact
billable full-request count; actual usage is checked afterward. Cancellation is
cooperative and missing responses may have unknown usage. Failed attempts do not
resume/retry automatically. Credentials are environment-only; `.env` is not autoloaded.
Live critique, revision, benchmarks, PDF ingestion and public hosting remain deferred.

Prior S-C CI [39126080199](https://github.com/ayatinkering/Synapse/actions/runs/39126080199)
passed on Python 3.12/3.13; hosted CI for this completion increment is reported separately.
Read AGENTS and STATUS, inspect Git status/branch/remote, and rerun relevant checks before
relying on this checkpoint. Temporary handoff: `/tmp/synapse-session-handoff.md`.

## Historical S-B checkpoint — complete


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

The S-A/S-B checkpoints above are historical. Current S-C progress and remaining
acceptance gates are recorded at the top of this file.
