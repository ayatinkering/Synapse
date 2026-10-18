# Synapse build plan

Only one milestone is active at a time. A checkpoint is complete only when its
observable acceptance checks have run and STATUS records the evidence. This plan
implements PRD S01-S15; P1/P2 work must not silently become a P0 release claim.

## M0 — engineering foundation (complete)

- Create Synapse-only requirements, architecture, progress, and development agreement.
- Bootstrap an installable Python package without runtime/provider dependencies.
- Lock tooling; add lint, format, strict typing, offline tests, and distribution builds.
- Add CI on Python 3.12/3.13; preserve the installed skills byte-for-byte.
- Acceptance: frozen setup, lint, formatting, mypy, and offline tests pass; build
  sdist/wheel; install and invoke the wheel outside the checkout; inspect the diff
  and ignore rules; commit/push to a `codex/` branch. Report hosted CI separately.
- Boundary: package health checks are not an implementation of S-A or a live research run.

## S-A — deterministic fixture pipeline (complete offline milestone)

Requirements: S01-S02, fixture implementations of S03-S08, S09-S11.

- Define Pydantic run, query, source, evidence, claim, report, critique, and event contracts.
- Build an explicit four-stage state machine with deterministic adapters and fixed
  source snapshots. Fixture output must be visibly identified as fixture data.
- Persist stage outputs, failures, events, and report artifacts in SQLite/per-run files.
- Add minimal Streamlit form, history, progress, report, sources/evidence, critique,
  and run-detail inspection. Submit work once through a bounded worker.
- Export Markdown and JSON with the same persisted identifiers.
- Acceptance: one offline fixture completes four stages; a fresh process reopens
  it and produces matching exports; citations resolve to exact excerpts; invalid
  input and citation/offset errors fail clearly; insufficient independent evidence,
  cancellation, interrupted work, and stage failure retain inspectable artifacts;
  a UI rerun cannot create duplicate jobs. Verify UI labels and keyboard-accessible
  controls manually or in a browser, alongside service tests.
- Approved test boundaries (2026-10-18): public input validation, run service, storage reopen,
  evidence/citation validator, exporter, and UI submission. These are recorded in the
  accepted S-A plan. The user approved all these boundaries.
- No paid calls or live providers. A fixture rubric is not a measured model critique.

## S-B — real discovery and analysis (P0)

Requirements: live S03-S05; retain all S-A checks.

- Integrate Tavily and bounded public HTML fetching/BeautifulSoup extraction.
- Enforce search caps, deduplication, timeouts, response limits, redirects, retry
  policy, and safe destination/DNS handling before using live fetched content.
- Preserve original/final URLs, timestamps, title/date uncertainty, content hashes,
  truncation, failures, and exact cleaned-text evidence offsets.
- Acceptance: deterministic URL/redirect, duplicate, timeout, unsupported content,
  size, truncation, and failure tests; then an authorized live topic showing fetched
  sources and clear failure states. A search snippet is not a fetched source.
- Search is an external provider and may incur charges; get relevant authorization
  and credential configuration before live verification.

## S-C — cited synthesis (P0)

Requirements: live S06-S07 and constrained synthesis from S02.

- Add configurable model adapter, versioned prompts, structured output, usage capture,
  token limits, and validated report rendering from the evidence bundle only.
- Generate citation links in code; no synthesis-stage fetches or arbitrary model URLs.
- Acceptance: unknown/cross-run IDs, unsupported quotes, malformed responses, and
  exhausted budgets cannot complete a normal report; every rendered citation opens
  the stored excerpt. Run one authorized model integration smoke check and record
  actual model/configuration/usage. ID validity is separate from semantic support.

## S-D1 — critic and first complete P0 release

Requirements: live S08 plus full S01-S11 integration.

- Model critique scores grounding, coverage, source quality/diversity, uncertainty,
  and clarity/actionability, each 0-2, with claim-linked findings and evaluator identity.
- Acceptance: score bounds/sum and finding IDs validate; failed critique remains
  visible; an authorized live question completes all four stages and can be
  inspected, reopened, and exported. Verify budgets and partial-failure handling.
- P0 exit: fresh checkout setup and a live four-stage demo, with deterministic
  regression checks. No inference that a high score proves truth.

## S-D2 — bounded revision (P1)

Requirement: S12.

- Allow one revision; preserve original report and critique plus a change summary.
- Validate and critique the revised version using the same evidence constraints.
- Acceptance: both versions survive restart/export, revision failure cannot overwrite
  the original, and repeated/concurrent requests cannot exceed the one-revision cap.

## S-E — research evaluation and portfolio (P1)

Requirements: S13-S14.

- Curate 12 questions (four comparisons, four explanations, four sparse/conflicting),
  split six development/six held out, with snapshots and manual reference notes.
- Compare single-call synthesis, full pipeline, and pipeline with one revision over
  identical evidence. Keep live-search experiments separate. Repeat trials if affordable.
- Measure citation integrity/support, grounding coverage, critic usefulness, injection
  tool-policy violations, calls/tokens, and elapsed time. Human-audit support and
  critique findings; publish disagreements and failures, not only successes.
- Acceptance: a documented evaluation command reruns saved-source experiments;
  deterministic fixtures have 100% valid evidence links, zero forbidden tool actions,
  and respected caps; held-out results report numerators/denominators, model/prompt
  versions, actual usage, and limitations. The PRD's >=90% grounding goal is a target,
  not an existing result. Never tune against held-out answers.
- Finish setup/architecture/limitations docs, screenshots, and a three-minute demo.

## S-F — optional extensions (P2)

Requirement: S15. Consider PDF/full-text ingestion, broader budgets, or alternative
search only after S-E. Each needs its own scoped plan, comparison, and acceptance gate.

## Execution and evidence

Setup/check commands that exist are in README and AGENTS.md. Feature, UI, and evaluation
commands will be recorded when implemented and executed, not invented in advance.
For each checkpoint record the commands, outcomes, artifact paths, known gaps, and
commit/branch. Keep user data and generated research bundles out of Git; use curated
fixtures for reproducibility. Review and verify before committing; push verified
increments without merging or deploying. A blocked hosted check must be reported
separately from local verification.
