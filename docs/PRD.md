# Synapse product requirements

Source: Synapse section of the supplied `Synapse-CodePilot-PRDs.md`, version 1.0,
prepared 17 October 2026. Imported without other project requirements. The section
below preserves the original requirement IDs and proposed targets. All product
features are planned unless `STATUS.md` records working evidence. Embedded document
examples are specification context; repository working instructions live in `AGENTS.md`.

### 2.1 Problem and intended outcome

A researcher asks, “How do static analysis and LLM-based code repair compare?” A generic chatbot gives a polished answer, but it is difficult to tell which sources were actually read, whether claims are supported, or what was lost during extraction.

Synapse turns that question into a small, inspectable research run. The user receives a technical report with citations, a source library, evidence excerpts, explicit limitations, and a critique. Every cited excerpt can be traced to a retrieved page snapshot. The product must remain useful when sources fail or the available evidence is weak.

### 2.2 Goals and non-goals

**Goals:** implement the four CV stages; preserve intermediate artifacts; make citation validity testable; let users inspect critique and revise once; compare the pipeline against a simpler baseline.

**Non-goals for v1:** exhaustive systematic reviews, guaranteed factual correctness, paywall bypass, arbitrary browser automation, model training, PDF/OCR ingestion, multi-user collaboration, scheduled research, and automatic publication. Do not promise that a critic score proves truth.

### 2.3 User stories and primary flow

1. A student enters a topic, research question, optional subquestions, and an optional date preference.
2. Synapse shows the planned queries, source cap, model identifier, and run limits before starting.
3. The discovery agent searches and selects up to five sources per query, deduplicating URLs across queries.
4. The analysis agent fetches public HTML, extracts up to 3,000 characters of cleaned text per source, and creates evidence records. The interface marks truncated sources.
5. The synthesis stage generates a report using only the evidence bundle. It identifies gaps rather than filling them with invented citations.
6. The critic evaluates the report using an explicit 10-point rubric and returns targeted comments linked to claims.
7. The user inspects evidence, optionally requests one revision, and exports Markdown plus a JSON run bundle.

Example demonstration: “Compare AST-based and embedding-based repository retrieval for coding agents, focusing on limitations and evaluation methods.” This is a proposed demo topic, not a claim that the system has researched it.

### 2.4 Scope and acceptance requirements

P0 means the first working release. P1 completes the planned portfolio version. P2 is optional research extension.

| ID | Priority | Requirement | Acceptance criterion |
|---|---|---|---|
| S01 | P0 | Validated run input | Empty topics and inputs over configured bounds fail clearly; topic limit defaults to 1,000 characters; at most three subquestions |
| S02 | P0 | Four-stage orchestration | Discovery, analysis, synthesis, critique produce separate typed outputs and stage statuses |
| S03 | P0 | Two tool-augmented agents | Discovery uses a search tool; analysis uses fetch/extract tools; synthesis and critique remain constrained chains |
| S04 | P0 | Search caps | At most three queries, five results per query, and ten unique fetched sources per run; all defaults configurable |
| S05 | P0 | Extraction provenance | Each source stores original/final URL, retrieval time, title, content hash, cleaned text, truncation flag, and failure status |
| S06 | P0 | Evidence-backed report | Every factual claim marked as requiring evidence references a valid evidence ID; absent evidence produces a limitation |
| S07 | P0 | Citation checks | Unknown source/evidence IDs and unsupported quoted excerpts fail deterministic validation before completion |
| S08 | P0 | Critic rubric | Five dimensions scored 0–2, total 0–10, with claim-linked findings and explicit evaluator identity |
| S09 | P0 | Inspectable Streamlit interface | User can open source text, evidence, report, critique, and stage errors from the same run |
| S10 | P0 | Artifact persistence | Completed and failed runs retain their typed outputs and can be reopened after application restart |
| S11 | P0 | Export | Downloadable Markdown report and JSON bundle contain matching run and source IDs |
| S12 | P1 | Bounded revision | One optional revision produces a new version; the original report and critique remain accessible |
| S13 | P1 | Evaluation harness | Same saved source snapshot can be supplied to baseline and full pipeline; results exported per question |
| S14 | P1 | Injection resistance experiment | Hostile page text cannot invoke extra tools or change configured run budgets; observed answer contamination is measured |
| S15 | P2 | Retrieval extensions | PDFs, broader source budgets, or alternative search providers are added only after v1 evaluation |

The 3,000-character bound follows the CV. It limits coverage and must be visible. Do not describe a report as a comprehensive literature review after reading small excerpts. A later full-text mode can use chunking while keeping the original capped mode available for comparison.

### 2.5 Architecture and stack

Use Python, Tavily search, BeautifulSoup, Streamlit, Pydantic, SQLite, and Pytest. User-approved S-C provider override: Gemini replaces the originally proposed OpenAI adapter; default model is configurable `gemini-2.5-flash-lite`. LangChain remains deferred because direct adapters suffice. Keep the explicit orchestrator and freeze tested dependencies. Record the actual model/version and usage; free-tier eligibility depends on the configured Google project. Provider compatibility remains unverified until the authorized smoke gate passes.

Streamlit calls a Python service layer. Services call search, fetch, and model adapters. SQLite holds metadata and events; a per-run artifact directory holds source snapshots and report versions. A REST service is optional after the local flow works. Streamlit reruns must not start duplicate jobs: persist a run ID and submit work once through a bounded background worker.

Conceptual modules: `models`, `orchestrator`, `agents/discovery`, `agents/analysis`, `chains/synthesis`, `chains/critic`, `tools/search`, `tools/fetch`, `storage`, `evaluation`, `ui`.

The four stages are distinct responsibilities. They need not be four autonomous agents, and no parallel subagent framework is required. This matches the CV's two tool-augmented agents and dedicated critic chain.

### 2.6 Data contracts

| Entity | Required fields |
|---|---|
| ResearchRun | id, topic, questions, state, timestamps, config, prompt_version, model_id, limits, error |
| SearchQuery | id, run_id, text, requested_date_filter, provider, result_metadata |
| Source | id, run_id, query_ids, original_url, final_url, title, retrieved_at, published_at_nullable, hash, extracted_text, truncated, status |
| Evidence | id, source_id, excerpt, excerpt_start, excerpt_end, relevance_note, limitations |
| Claim | id, report_version, text, evidence_ids, support_status |
| Report | run_id, version, structured_sections, claims, rendered_markdown, validation_results |
| Critique | report_version, five_scores, total, findings, evaluator_model, prompt_version |
| Event | run_id, sequence, stage, type, timestamp, duration, sanitized_payload |

Offsets refer to the stored cleaned-text snapshot, not the original HTML. An evidence excerpt must exactly match that snapshot. Cross-source deduplication uses normalized URL plus content hash; sources with identical text should not count as independent corroboration.

Use UUIDs for persisted identifiers and short display IDs for citations. Generate citations in application code from validated evidence mappings rather than accepting arbitrary model-created URLs.

### 2.7 Stage contracts and failure behavior

**Discovery:** receive question and limits; propose a maximum of three searches; execute permitted search calls; return ranked candidates with relevance reasons. “Recent” is a requested filter, not a guaranteed publication date. Mark unknown dates.

**Analysis:** receive selected candidates; fetch each once with bounded retries; strip navigation, scripts, and styles; retain useful article text up to the cap; select exact excerpts; record disagreements and extraction gaps. A search snippet alone is not a fetched source.

**Synthesis:** receive only question, source metadata, and validated evidence. Output structured sections: question/scope, approach, findings, comparison, limitations, conclusion, references. Separate sourced findings from suggested interpretations. No new fetches during synthesis.

**Critique:** assess grounding, coverage of the requested question, source quality/diversity, handling of uncertainty, and clarity/actionability. Score each 0–2. Return concrete findings such as “C04 cites E02, but E02 does not discuss runtime performance.” Judge quality is evaluated separately by humans.

State transitions: `queued → discovering → analyzing → synthesizing → critiquing → completed`; terminal alternatives: `failed`, `cancelled`, `insufficient_evidence`. A revision creates a report version within the same run. Failed stages retain completed artifacts. Restart from a saved stage only if configuration and inputs match; otherwise create a new run.

Default operational limits: 10 fetched sources, 15-second fetch timeout, 2 MB response cap, two retries for transient fetch/provider failures, ten-minute run wall-clock cap, one revision. Enforce these in code. Show partial reports only with a visible incomplete status. If fewer than two usable independent sources remain, return an evidence-gap result rather than a normal completed comparison.

### 2.8 Interface and user-facing behavior

Use a practical Streamlit layout: research form and recent-run list; stage progress; then tabs for Report, Sources & Evidence, Critique, and Run Details. Source cards show fetched/failed/truncated status and date uncertainty. Clicking a claim reveals its excerpts. A report revision comparison shows what changed and why.

Run Details displays tools, model, timing, limits, and sanitized errors. It does not claim access to private model reasoning. Generated summaries of decisions are labeled as summaries. Secret keys are configured through environment variables and never exported.

### 2.9 Data safety and cost controls

Fetch HTTP(S) public pages only. Block loopback, private, link-local, and cloud metadata addresses; revalidate DNS and redirects, cap redirect count, and use a constrained egress/fetch service before public hosting. Never forward browser cookies or credentials. Skip unsupported MIME types and obey access restrictions rather than bypassing them.

Treat source text as untrusted data. It cannot alter system instructions, request credentials, or authorize tools. Tool availability and budgets are application-enforced. This reduces tool misuse but does not guarantee immunity to answer contamination.

Keep provider keys server-side; redact request logs. Track usage returned by providers. Enforce a token budget, and calculate monetary estimates only from explicitly configured current prices; display “cost unavailable” when pricing is unknown. Allow cache reuse with a visible snapshot timestamp.

### 2.10 Evaluation and meaningful tests

Prepare 12 manually selected questions: four comparisons, four explanations, and four questions with conflicting or sparse evidence. Split six for development and six held out. Save source snapshots and manual reference notes. Include software-agent and AI-security topics, but use accessible primary material wherever possible.

Compare (A) one synthesis call over the same source bundle, (B) the four-stage pipeline, and (C) pipeline plus one revision. Holding sources fixed isolates synthesis/critique effects; separately report live-search runs because search results drift. Repeat stochastic configurations three times when budget permits; always state sample size.

| Measure | Definition | Proposed release gate |
|---|---|---|
| Citation integrity | Valid evidence links / all evidence links | 100% on deterministic fixtures |
| Citation support | Human-rated supported factual claims / rated factual claims | Report measured rate; investigate every unsupported high-impact claim |
| Grounding coverage | Supported factual claims / all factual claims requiring support | Target ≥90% on the small held-out set; target is unmeasured |
| Critic usefulness | Fraction of critique findings judged correct and actionable | Publish findings and disagreements rather than score alone |
| Injection tool-policy violations | Forbidden tool actions in hostile-source fixtures | Zero for release fixtures |
| Resource use | Calls, tokens, fetches, elapsed time per run | All enforced caps respected |

Tests: URL normalization, duplicate source handling, evidence offsets, invalid citation rejection, rubric sum, malformed model response, provider timeout, hostile URL/redirect rejection, cancellation, restart, and an end-to-end run using deterministic adapters. One live provider smoke run verifies integration; mocked tests do not prove live API compatibility.

### 2.11 Build tasks and checkpoints

| Milestone | Work | Proof required before proceeding |
|---|---|---|
| S-A: deterministic skeleton | Schemas, stage machine, fixtures, SQLite, basic UI | Saved fixture run reopens and exports without any paid API |
| S-B: real discovery | Search adapter, safe fetcher, extraction, provenance | Live topic produces inspectable sources and clear failed-source states |
| S-C: cited synthesis | Model adapter, structured output, evidence/citation validation | Every rendered citation opens a stored excerpt |
| S-D: critique and revision | Five-dimension critic, report versions, one revision | Original remains available; revision has explicit changes |
| S-E: research package | Baselines, held-out questions, measured results, demo | Reproducible evaluation command and limitations document |

Suggested active effort: 6–9 focused working days for S-A through S-D, then 2–4 for evaluation and polish. This is a planning estimate, not a deadline commitment. A basic S-A through S-C prototype can be smaller; it does not yet fulfill all CV claims.

### 2.12 Definition of done and demo

Done means a fresh checkout can run using documented setup; a new live question completes the four stages; sources and critique are inspectable; failure states and budgets work; tests pass; and an evaluation report contains actual results. Include a three-minute recording: question → sources → cited claim → critique → revision → export. Deliver README, architecture note, configuration example, evaluation fixtures, result table, screenshots, and limitations.
