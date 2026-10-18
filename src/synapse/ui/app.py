"""Run with Streamlit; only the Start button may submit a research run."""

import os
from uuid import UUID, uuid4

import streamlit as st

from synapse.export import render
from synapse.models import LABEL, TERMINAL, Snapshot, State
from synapse.service import ResearchService
from synapse.storage import ServiceError
from synapse.ui.resources import get_service


def select_saved_run() -> None:
    selected = st.session_state["history"]
    if selected != "Choose a saved run":
        st.query_params["run"] = selected


def render_run(service: ResearchService, snapshot: Snapshot) -> None:
    run = snapshot.run
    st.subheader(f"Saved run: {run.input.topic}")
    completed = sum(
        output is not None
        for output in (snapshot.discovery, snapshot.analysis, snapshot.report, snapshot.critique)
    )
    st.progress(completed / 4, text=f"{completed}/4 stage outputs saved · {run.state.value}")
    if run.state == State.COMPLETED:
        st.success("Run completed · all four fixture stages saved")
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
        if snapshot.analysis:
            for source in snapshot.analysis.sources:
                with st.expander(f"{source.display_id} · {source.title} · {source.status}"):
                    st.caption(LABEL)
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
            st.metric("Predetermined fixture score", f"{snapshot.critique.total}/10")
            st.caption(snapshot.critique.evaluator_model)
            st.table(
                [
                    {"Dimension": dimension, "Score (0–2)": score}
                    for dimension, score in zip(
                        [
                            "Grounding",
                            "Coverage",
                            "Source quality/diversity",
                            "Uncertainty",
                            "Clarity/actionability",
                        ],
                        snapshot.critique.scores,
                        strict=True,
                    )
                ]
            )
            for finding in snapshot.critique.findings:
                st.text(f"{finding.comment} (claim {finding.claim_id})")
            st.warning("This fixed score is not an independent evaluation or proof of truth.")
        else:
            st.info("No critique has been saved yet.")
    with details_tab:
        st.json(run.model_dump(mode="json"))
        st.caption("Persisted actions and statuses; no private model reasoning.")
        st.json([event.model_dump(mode="json") for event in snapshot.events])
        if snapshot.discovery:
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


st.set_page_config(page_title="Synapse · offline research", layout="wide")
st.title("Synapse")
st.caption("Discover → analyze → synthesize → critique · inspect every saved step")
st.warning(f"{LABEL}. Curated synthetic sources and predetermined outputs; no live research.")

try:
    service = get_service(os.environ.get("SYNAPSE_DATA_DIR", "data/synapse"))
except (ServiceError, OSError, ValueError):
    st.error(
        "Unable to open local research data. Check storage or another running Synapse process."
    )
    st.stop()

st.session_state.setdefault("submission_key", str(uuid4()))
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

try:
    runs = service.list_runs()
    active = any(run.state not in TERMINAL for run in runs)
    if st.button("Start offline run", type="primary", key="start", disabled=active):
        selected_id = service.submit(fixture_id, st.session_state["submission_key"])
        st.session_state["selected_run"] = str(selected_id)
        st.session_state["history"] = str(selected_id)
        st.session_state["submission_key"] = str(uuid4())
        st.query_params["run"] = str(selected_id)
        st.rerun()
    if runs:
        names = {
            str(run.id): f"{run.input.topic} · {run.state.value} · {str(run.id)[:8]}"
            for run in runs
        }
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
