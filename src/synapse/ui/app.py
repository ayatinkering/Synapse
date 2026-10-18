"""Run with Streamlit; only the Start button may submit a research run."""

import os
from uuid import UUID, uuid4

import streamlit as st

from synapse.critic import RUBRIC
from synapse.export import plain, render
from synapse.models import LABEL, TERMINAL, RunInput, Snapshot, State
from synapse.service import ResearchService
from synapse.storage import ServiceError
from synapse.ui.resources import get_service


def select_saved_run() -> None:
    selected = st.session_state["history"]
    if selected != "Choose a saved run":
        try:
            st.query_params["run"] = str(UUID(selected))
        except ValueError:
            # A stale browser option must not overwrite a valid saved-run link.
            return


def render_run(service: ResearchService, snapshot: Snapshot) -> None:
    run = snapshot.run
    st.subheader(f"Saved run: {plain(run.input.topic)}")
    completed = sum(
        output is not None
        for output in (snapshot.discovery, snapshot.analysis, snapshot.report, snapshot.critique)
    )
    st.progress(completed / 4, text=f"{completed}/4 stage outputs saved · {run.state.value}")
    st.caption(run.label)
    if run.state == State.SOURCES_READY:
        st.success("Sources ready — cited synthesis is available")
        st.caption(
            "Generate one report from these saved excerpts: no new Tavily search. "
            "Gemini token usage is recorded; monetary cost is unavailable."
        )
        if service.synthesis:
            st.json(service.synthesis.config.model_dump())
        if st.button(
            "Generate cited report",
            key=f"synthesize-{run.id}",
            disabled=not service.synthesis_enabled,
        ):
            service.submit_synthesis(run.id, f"synthesis-v1:{run.id}")
            st.rerun()
        if not service.synthesis_enabled:
            st.info(
                "Enable synthesis server-side with GEMINI_API_KEY, SYNAPSE_ENABLE_SYNTHESIS=1 "
                "and SYNAPSE_GEMINI_FREE_TIER=1 after confirming the project uses free quota."
            )
    elif run.state == State.REPORT_READY:
        st.success("Report ready — critique available")
        if service.critic:
            st.json(service.critic.config.model_dump())
        st.caption(
            "Evaluate saved claims/evidence once. One Gemini generation; no new search or revision."
        )
        if st.button(
            "Evaluate report", key=f"critique-{run.id}", disabled=not service.critique_enabled
        ):
            service.submit_critique(run.id, f"critic-v1:{run.id}")
            st.rerun()
        if not service.critique_enabled:
            st.info(
                "Enable SYNAPSE_ENABLE_CRITIQUE=1 with GEMINI_API_KEY "
                "and SYNAPSE_GEMINI_FREE_TIER=1 server-side."
            )
    elif run.state == State.COMPLETED:
        st.success("Run completed · all four stages saved")
    elif run.error:
        st.error(run.error)
    else:
        st.info(f"Run {run.state.value}")
    if run.state not in TERMINAL and st.button("Cancel run", key="cancel"):
        service.cancel(run.id)
        st.rerun()
    report_tab, sources_tab, critique_tab, details_tab = st.tabs(
        ["Report", "Sources & Evidence", "Critique", "Run Details"]
    )
    with report_tab:
        if snapshot.report:
            st.markdown(render(snapshot)[0])
            claims = {claim.display_id: claim for claim in snapshot.report.claims}
            selected = st.selectbox("Inspect a claim", list(claims), key=f"claim-{run.id}")
            claim = claims[selected]
            if snapshot.analysis:
                for evidence in snapshot.analysis.evidence:
                    if evidence.id in claim.evidence_ids:
                        st.caption(f"{evidence.display_id} · exact stored excerpt")
                        st.text(evidence.excerpt)
                        st.caption(
                            f"Source {evidence.source_id}; "
                            f"offsets {evidence.excerpt_start}:{evidence.excerpt_end}"
                        )
        else:
            st.info("No report is available. Missing stages are not inferred.")
    with sources_tab:
        if snapshot.discovery:
            for query in snapshot.discovery.queries:
                if query.error:
                    st.text(f"Search query: {query.text}")
                    st.warning(query.error)
        if snapshot.analysis:
            for source in snapshot.analysis.sources:
                with st.expander(f"{source.display_id} · {plain(source.title)} · {source.status}"):
                    st.caption(source.label if run.kind == "fixture" else "Fetched HTML snapshot")
                    st.text(f"Original URL: {source.original_url}")
                    st.caption(f"Retrieved: {source.retrieved_at.isoformat()}")
                    st.text(source.final_url)
                    st.caption(
                        f"Truncated: {source.truncated} · Publication date: "
                        f"{source.published_at.isoformat() if source.published_at else 'unknown'}"
                    )
                    if source.error:
                        st.warning(source.error)
                    st.code(source.extracted_text, language=None)
                    st.caption(f"SHA-256: {source.content_hash}")
                    for evidence in snapshot.analysis.evidence:
                        if evidence.source_id == source.id:
                            st.text(f"{evidence.display_id}: {evidence.excerpt}")
                            st.caption(evidence.limitations)
        else:
            st.info("No analyzed sources have been saved yet.")
    with critique_tab:
        if snapshot.critique:
            st.metric(
                "Predetermined fixture score" if run.kind == "fixture" else "Model critique score",
                f"{snapshot.critique.total}/10",
            )
            st.caption(snapshot.critique.evaluator_model)
            st.table(
                [
                    {"Dimension": dimension, "Score (0–2)": score}
                    for dimension, score in zip(
                        RUBRIC,
                        snapshot.critique.scores,
                        strict=True,
                    )
                ]
            )
            for finding in snapshot.critique.findings:
                st.text(f"{finding.comment} (claim {finding.claim_id})")
            st.caption(f"Prompt: {snapshot.critique.prompt_version}")
            if snapshot.critique.findings and snapshot.report and snapshot.analysis:
                selected_finding = st.selectbox(
                    "Inspect a critique finding",
                    range(len(snapshot.critique.findings)),
                    format_func=lambda i: f"Finding {i + 1}",
                    key=f"finding-{run.id}",
                )
                finding = snapshot.critique.findings[selected_finding]
                claim = next(c for c in snapshot.report.claims if c.id == finding.claim_id)
                st.text(f"{claim.display_id}: {claim.text}")
                for evidence in snapshot.analysis.evidence:
                    if evidence.id in claim.evidence_ids:
                        st.text(f"{evidence.display_id}: {evidence.excerpt}")
            st.warning(
                "A model score is not an independent fact check or proof of truth."
                if run.kind == "live"
                else "This fixed score is not an independent evaluation or proof of truth."
            )
        else:
            st.info("No critique has been saved yet.")
    with details_tab:
        st.json(run.model_dump(mode="json"))
        if snapshot.critique_usage:
            st.caption("Critique usage; unavailable counts remain unknown. Cost unavailable.")
            st.json(snapshot.critique_usage.model_dump(mode="json"))
        if snapshot.synthesis:
            st.caption("Gemini token counts; unavailable counts remain unknown. Cost unavailable.")
            st.json(snapshot.synthesis.model_dump(mode="json"))
        st.caption("Persisted actions and statuses; no private model reasoning.")
        st.json([event.model_dump(mode="json") for event in snapshot.events])
        if snapshot.discovery:
            for query in snapshot.discovery.queries:
                st.text(f"Query: {query.text} · {query.status}")
                if query.error:
                    st.warning(query.error)
            st.json(snapshot.discovery.model_dump(mode="json"))
    if run.state in TERMINAL:
        markdown, bundle = service.export_run(run.id)
        st.download_button(
            "Download Markdown",
            markdown,
            file_name=f"synapse-{run.id}.md",
            mime="text/markdown",
            key="markdown-download",
        )
        st.download_button(
            "Download JSON",
            bundle,
            file_name=f"synapse-{run.id}.json",
            mime="application/json",
            key="json-download",
        )


@st.fragment(run_every=1)
def live_run(service: ResearchService, run_id: UUID) -> None:
    try:
        snapshot = service.get_run(run_id)
        if snapshot.run.state in TERMINAL:
            st.rerun()
        render_run(service, snapshot)
    except (ServiceError, ValueError, OSError):
        st.error("Unable to load this run. Check local storage and restart the application.")


st.set_page_config(page_title="Synapse · research evidence", layout="wide")
st.title("Synapse")
st.caption("Discover → analyze → synthesize → critique · inspect every saved step")


try:
    service = get_service(os.environ.get("SYNAPSE_DATA_DIR", "data/synapse"))
except (ServiceError, OSError, ValueError):
    st.error(
        "Unable to open local research data. Check storage or another running Synapse process."
    )
    st.stop()

st.session_state.setdefault("submission_key", str(uuid4()))
mode = st.radio("Run mode", ["Offline demonstration", "Live discovery"], key="mode")
live = mode == "Live discovery"
input: RunInput | None = None
fixture_id = "comparison"
if not live:
    st.warning(f"{LABEL}. Curated synthetic sources and predetermined outputs; no live research.")
    fixtures = {fixture.id: fixture for fixture in service.list_fixtures()}
    fixture_id = st.selectbox(
        "Scenario", list(fixtures), format_func=lambda value: fixtures[value].name, key="fixture"
    )
    fixture = fixtures[fixture_id]
    st.subheader(fixture.name)
    st.text(fixture.input.question)
    with st.expander("Preview queries and run limits"):
        for query in fixture.queries:
            st.text(query)
        st.json(service.limits.model_dump())
        st.caption("Model: fixture-v1 · 0 provider calls · no credentials required")
else:
    st.info(
        "Live discovery fetches public HTML. Cited synthesis is optional afterward; "
        "critique evaluates the saved report."
    )
    topic = st.text_input("Topic", max_chars=1000, key="topic")
    question = st.text_area("Research question", max_chars=1000, key="question")
    subquestions = st.text_area(
        "Optional subquestions (up to three, one per line)", max_chars=3002, key="subquestions"
    )
    date = st.selectbox(
        "Requested publication window",
        [None, "day", "week", "month", "year"],
        format_func=lambda v: "Any time" if v is None else f"Past {v}",
        key="date",
    )
    try:
        input = RunInput(
            topic=topic,
            question=question,
            subquestions=[s for s in subquestions.splitlines() if s.strip()],
            date_preference=date,
        )
        preview = service.preview_discovery(input)
        st.caption("Planned queries (question, then up to two distinct subquestions)")
        for query in preview.queries:
            st.text(query)
    except (ValueError, ServiceError):
        input = None
        st.info("Enter a topic and question; use at most three nonempty subquestions.")
    with st.expander("Run limits and provider calls"):
        st.json(service.limits.model_dump())
        st.text(
            "Tavily basic search: up to three queries, three attempts per query. "
            "Retries may incur charges. Provider-reported usage is saved; cost unavailable."
        )
        st.caption(
            "Discovery makes no model calls. Generate a report separately from saved sources."
        )
    if not service.live_enabled:
        st.warning(
            "Live submission disabled. Configure SYNAPSE_ENABLE_LIVE=1 and "
            "TAVILY_API_KEY server-side, then restart. Never enter keys in a research field."
        )

try:
    runs = service.list_runs()
    active = any(run.state not in TERMINAL for run in runs)
    disabled = active or (live and (input is None or not service.live_enabled))
    if st.button(
        "Start live discovery" if live else "Start offline run",
        type="primary",
        key="start",
        disabled=disabled,
    ):
        if live and input is not None:
            selected_id = service.submit_discovery(input, st.session_state["submission_key"])
        else:
            selected_id = service.submit(fixture_id, st.session_state["submission_key"])
        st.session_state["selected_run"] = str(selected_id)
        st.session_state["history"] = str(selected_id)
        st.session_state["submission_key"] = str(uuid4())
        st.query_params["run"] = str(selected_id)
        st.rerun()
    if runs:
        names = {str(run.id): f"{run.input.topic} · {str(run.id)[:8]}" for run in runs}
        options = ["Choose a saved run", *names]
        st.sidebar.selectbox(
            "Recent runs",
            options,
            format_func=lambda value: names.get(value, value),
            key="history",
            on_change=select_saved_run,
        )
    link = st.query_params.get("run")
    if link:
        try:
            run_id = UUID(link)
        except ValueError:
            st.error("Invalid run link. Select a saved run from the sidebar.")
        else:
            st.session_state["selected_run"] = str(run_id)
            snapshot = service.get_run(run_id)
            if snapshot.run.state in TERMINAL:
                render_run(service, snapshot)
            else:
                live_run(service, run_id)
except (ServiceError, ValueError, OSError) as error:
    st.error(
        str(error)
        if isinstance(error, ServiceError)
        else "Saved run data could not be validated or written."
    )
