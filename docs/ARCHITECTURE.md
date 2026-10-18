# Synapse architecture

## Current implementation

S-A implements Pydantic contracts and four typed fixture adapters; deterministic
integrity validation; a SQLite-backed run service with one background thread; derived
atomic artifacts and exports; and a native Streamlit UI. S-B adds a direct Tavily adapter, pinned-IP HTTP fetching, bounded DNS resolution,
BeautifulSoup cleaning, heuristic evidence selection, and per-query/source checkpoints.
S-C adds explicit Gemini synthesis over saved evidence; the authorized live smoke gate passed.
S-D1 adds one explicit live critique and completes the four-stage local workflow.
Revision and benchmark evaluation remain unimplemented.

The fixture catalog is bundled package data. Stage outputs carry schema version 1.
SQLite uses runs, stage_outputs, and events tables (database schema version 3; transactional migrations from v1/v2).
Connections are short lived and stage/event/state writes share a transaction.
A filelock ownership lock excludes a second process. One global cached service
owns the single worker; UI reruns only read status unless Start is pressed.
Idempotency keys are persisted and another nonterminal submission is rejected.
Interrupted work is marked failed on startup, never silently resumed. Data defaults
to `data/synapse/`; `SYNAPSE_DATA_DIR` selects another local root.

Distribution: `synapse-research`; import/command: `synapse`. `src/` layout prevents
accidental import from the checkout root from substituting for an installed package.
The build backend is pinned; `uv.lock` pins the development dependency graph.

## Flow and responsibilities

Streamlit UI -> Python run service -> explicit orchestrator -> adapters/tools.
SQLite stores metadata/events; per-run artifact directories hold snapshots and
report versions. Runtime directories are ignored. Start single-user and local.

1. Discovery agent proposes at most three queries and uses the bounded search tool.
2. Analysis agent uses safe fetch/extraction tools and selects exact evidence excerpts.
3. Synthesis chain sees only the question, source metadata, and validated evidence.
4. Critic chain uses the five-dimension rubric and claim-linked findings.

These are two tool-augmented agents plus two constrained chains. Use LangChain at
the adapter/agent boundaries when needed; keep orchestration explicit. No second
workflow framework, REST service, hosted database, or distributed queue is needed
for the local first release. Add dependencies at the milestone that uses them.

Future live-integration modules: `models`, `orchestrator`, `agents/discovery`, `agents/analysis`,
`chains/synthesis`, `chains/critic`, `tools/search`, `tools/fetch`, `storage`,
`evaluation`, and `ui`. Create modules as working behavior needs them.

## State, persistence, and concurrency

`queued -> discovering -> analyzing -> synthesizing -> critiquing -> completed`.
Live discovery stops at `sources_ready` after analysis. Explicit synthesis transitions
that saved run to `synthesizing -> report_ready`; explicit critique then transitions
`critiquing -> completed`. Other terminal alternatives:
`failed`, `cancelled`, `insufficient_evidence`.

Assign a persisted run ID before submission. A bounded background worker claims
the job once; Streamlit reruns read status instead of resubmitting. Persist each
typed stage result and ordered event as work proceeds. Recover interrupted jobs
explicitly after restart; resume a saved stage only when configuration/input hashes
match. Report versions are immutable; revision adds a version within the same run.
Artifact writes should be atomic and reconciled with stored metadata to avoid
presenting a partially written report as completed.

## Provenance and validation

Persist UUIDs and short citation display IDs. Evidence offsets address the stored
cleaned-text snapshot; excerpts must match exactly. Store hashes, URLs, retrieval
time, date uncertainty, truncation, and failure states. Deduplicate normalized URLs
and identical content; duplicates cannot provide independent corroboration.

The renderer constructs references from validated mappings. Unknown evidence/source
IDs and altered quotations fail deterministic validation. Semantic claim support
requires model/human evaluation; deterministic links alone cannot prove it.

## Limits and trust boundaries

PRD defaults: 1,000 topic characters, three subquestions, three searches, five results
per query, ten fetched sources, 3,000 extracted characters per source, 15-second
fetch timeout, 2 MB response cap, two transient retries, ten-minute run deadline,
and one revision. Set and enforce a model token budget before enabling live synthesis;
the PRD does not specify its numeric default. A retry, redirect, cache, or model tool
request must not bypass limits. Reject fewer than two independent usable sources
as an evidence-gap result. Partial output is visibly incomplete.

Only public HTTP(S) HTML. Block private/loopback/link-local/metadata destinations,
revalidate redirects and DNS, cap redirects, and check MIME/streamed response size.
Public hosting requires a constrained egress/fetch service and an access review.
Untrusted page text can never authorize tools or alter budgets. Keep credentials
server-side, sanitize events/errors/exports, and track provider-reported usage.
Price estimates require explicit configured prices; otherwise show cost unavailable.

## Verification strategy

Deterministic adapters and fixtures cover the pipeline without network or keys.
Service-boundary tests cover contracts, failure preservation, persistence/restart,
citation validation, exports, cancellation, and duplicate submission. Browser checks
cover actual UI behavior/accessibility. Authorized live smoke checks establish
provider compatibility. Fixed-source evaluations and human review establish observed
research quality; mocked tests and critic scores cannot establish it.

CI currently covers package setup, lint/format, strict typing, offline tests, and
distribution installation. Python socket blocking is a test tripwire, not a security
sandbox. CI requires no provider secrets and does not publish packages or deploy.

## S-A verification and limits

Contracts, evidence validation, the run service, reopened storage, exports, and UI
submission/inspection are the approved test boundaries. Default tests cover synthetic
success/gap, idempotency/busy, cancellation/deadline, adapter and disk errors,
process ownership, crash recovery, export regeneration, and AppTest interactions.
UI status polls once per second only while a selected run is active. Terminal views
have no polling fragment. Both complete and incomplete exports are validated anew.
S-A has no automatic resumption or concurrent research jobs. The S-B boundary below
adds opt-in live discovery. S-C below adds generated reports; live critique is deferred.

## S-B live discovery boundary

Fixture runs retain their four-stage behavior and labels. Explicit live runs terminate
at `sources_ready` after two stages; report/critique fields remain null and exports
are incomplete research bundles. Mode, complete normalized input, and limits form the
persisted submission fingerprint. A changed request cannot reuse a key silently.

The deterministic preview uses the question and up to two distinct subquestions.
Tavily is fixed to its HTTPS search endpoint, basic depth, no auto parameters, answers,
or raw content. Search results preserve bounded snippets, ranks/scores and query
associations separately from fetched evidence. Each dispatched attempt is checkpointed;
started attempts without a response have unknown usage, including after interruption.
Authentication/quota errors stop discovery; other query failures retain prior results.

Fetch tools normalize public HTTP(S) URLs and reject credentials, nonstandard ports,
nonpublic/mixed DNS answers, invalid TLS, downgrade redirects, unsupported MIME/encoding,
oversized responses, and access errors. DNS has a bounded lifetime. Each retry/redirect
resolves again and connections pin an approved IP while retaining original Host/SNI and
certificate matching. HTTP transport uses no ambient proxies/cookies, automatic
redirects/retries, or decompression. A watchdog and streamed-read budget bound attempts.
One initial fetch plus two transient retries and up to three redirects per attempt are
allowed. Cancellation is cooperative; calls check the remaining run deadline.

Analysis strips script/navigation/form content, prefers article/main text, normalizes
whitespace, then caps the snapshot. Up to three exact nonoverlapping excerpts are
ranked by question-term overlap with document-order ties. This is provenance, not
semantic claim support. Date metadata is parsed only from explicit supported page
publication tags; unknown dates stay null. Every finished source/evidence checkpoint
atomically replaces the growing analysis output and appends an event. SQLite remains
authoritative, including on cancellation/restart and derived artifact failure.

Server-side live enablement and a Tavily key are required for new live submissions.
Fixtures and saved live runs remain inspectable without credentials. No provider
secret or raw provider exception body belongs in stored output. Public deployment,
model orchestration, full-text/PDF ingestion, and evaluation remain later work.

## S-C synthesis boundary

`submit_synthesis` atomically claims a live sources-ready run, preserving its UUID,
source/evidence IDs, and discovery outputs. Schema v3 adds a unique synthesis key and
configuration fingerprint; identical requests return the original attempt, conflicting
keys fail, and busy/terminal checks occur inside the transaction. One attempt per run,
including failure; no automatic retry/resume. Startup interruption handling is shared.

`GeminiSynthesis` uses the existing pinned-IP HTTPS transport to fixed Google endpoints;
model-name validation prevents URL injection. No tools, SDK, new dependencies, Tavily
calls, or model-selected URLs. Instructions treat all source/question text as untrusted.
Only question, subquestions, source metadata, and saved excerpts enter the prompt.
Structured output is bounded and parsed; application-created claim IDs and citations
must resolve to this run's exact evidence. Quotes are literal substrings. Free-form
model narrative outside claims/limitations is not rendered. Semantic support is unmeasured.

A contents-only `countTokens` call estimates serialized instructions, evidence and JSON
schema (aligned with Google's Python SDK Developer API request shape). This estimate
is not an exact full-request billable token count. Above-limit estimates prevent
inference; reported generation usage is checked afterward and can reject a report.
Default model/configuration: Gemini 3.5 Flash-Lite, 8,192 input / 2,048 output tokens,
30 seconds/request, minimal thinking, no retries. The request watchdog and overall
600-second deadline remain enforced. The authorized Gemini 3.5 Flash-Lite provider smoke gate passed.

Versioned synthesis stage checkpoints distinguish started/counting/generating/generated/
validated states and preserve returned model version and usage. A cancelled/lost response
can have unknown usage even if the provider generated tokens. Validated reports and
artifacts are saved before terminal success. Failures retain prior outputs; artifacts
are regenerable from SQLite. Errors contain static codes and allowlisted HTTP statuses,
never raw provider error bodies, headers, credentials, or tracebacks. Markdown/JSON
exports identify model, prompt, configuration, IDs, usage, and pending critique.

The cached service reads server environment enablement, free-tier confirmation, key,
and optional model ID. These flags are consent/configuration gates, not a billing cap.
No automatic `.env` loading. UI reruns cannot submit a second attempt; generating uses
an explicit labeled control. Offline tests exercise the service/export/UI seams with
injected transport; live provider verification remains a separate authorized gate.

S-C compatibility fixes: default model updated after Google's explicit new-user rejection
of 2.5 Flash-Lite; `responseFormat.text` carries an inline JSON schema and the REST
thinking enum is `MINIMAL`. Provider grammar omits unsupported string-length constraints
and UUID enums; Pydantic text bounds and run-owned evidence/quote validation remain
mandatory. Controlled probes isolated the UUID enum rejection. HTTP connection/header
waiting now honors the caller's attempt budget instead of an unrelated five-second cap;
the watchdog, DNS, remaining deadline and streamed-read limits still apply.

## S-D1 minimal live critique

`submit_critique(run_id, key)` evaluates a saved live report once. The same single
worker and inference transport serve synthesis and critique. Critique receives only
saved question/report/source metadata/excerpts, no tools. It returns five ordered
integer scores (0–2) and at most twelve bounded claim-linked comments. Application code
calculates their sum and validates ownership/report version; malformed scores, unknown
claim IDs, blank/oversized comments, links, refusals and budget failures cannot complete.
The model identity and `critic-v1` prompt version are application-owned metadata.

Critique configuration/key live in the versioned run JSON; an immediate SQLite
transaction scans the local runs for key conflicts/busy state and claims only
`report_ready` work. This deliberately avoids another table migration/index for a
single-user local store. Existing optional-field defaults reopen older databases.
A separate `critique_usage` output records the same typed usage checkpoints. Report
content is immutable; failure/cancellation/restart preserve it and existing evidence.
Validated critique and derived artifacts precede terminal success. Complete live
exports require all four outputs and validated critique usage.

Server gates: `SYNAPSE_ENABLE_CRITIQUE=1`, `GEMINI_API_KEY`, and the existing free-tier
confirmation. The UI offers Evaluate report only for eligible saved runs, labels live
scores as model judgments, and exposes the finding's original claim/excerpts. No
automatic revision, second critic, parallel framework, or new dependency was added.
The default configuration is shared with synthesis: Gemini 3.5 Flash-Lite, 8,192 input
preflight / 2,048 output tokens, 30 seconds/request, minimal thinking, no retries.
