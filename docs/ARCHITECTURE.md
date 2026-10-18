# Synapse architecture

## Current implementation

M0 provides a Python 3.12/3.13 package, argparse help/version entry points, locked
development tools, and offline package/CI checks. There is no research service,
storage, UI, model SDK, search SDK, or external request code yet.

Distribution: `synapse-research`; import/command: `synapse`. `src/` layout prevents
accidental import from the checkout root from substituting for an installed package.
The build backend is pinned; `uv.lock` pins the development dependency graph.

## Planned flow and responsibilities

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

Planned modules: `models`, `orchestrator`, `agents/discovery`, `agents/analysis`,
`chains/synthesis`, `chains/critic`, `tools/search`, `tools/fetch`, `storage`,
`evaluation`, and `ui`. Create modules as working behavior needs them.

## State, persistence, and concurrency

`queued -> discovering -> analyzing -> synthesizing -> critiquing -> completed`.
Terminal alternatives: `failed`, `cancelled`, `insufficient_evidence`.

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
