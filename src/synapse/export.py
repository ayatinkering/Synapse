"""Render only validated saved outputs; every export carries its fixture label."""

import re

from synapse.critic import RUBRIC
from synapse.models import Snapshot, State
from synapse.validation import (
    validate_analysis,
    validate_critique,
    validate_discovery,
    validate_report,
)


def plain(text: str) -> str:
    """Escape untrusted Markdown syntax and HTML; only application code creates links."""
    return re.sub(r"([\\`*_{}\[\]()<>#!|])", r"\\\1", text)


def render(snapshot: Snapshot) -> tuple[str, str]:
    run = snapshot.run
    if snapshot.discovery:
        validate_discovery(run, snapshot.discovery)
    if snapshot.analysis:
        if snapshot.discovery is None:
            raise ValueError("Analysis requires discovery")
        validate_analysis(run, snapshot.discovery, snapshot.analysis)
    if snapshot.report:
        if snapshot.analysis is None:
            raise ValueError("Report requires evidence")
        validate_report(run, snapshot.analysis, snapshot.report)
    if snapshot.critique:
        if snapshot.report is None:
            raise ValueError("Critique requires report")
        validate_critique(run, snapshot.report, snapshot.critique)
    if run.state == State.COMPLETED and not all(
        (snapshot.discovery, snapshot.analysis, snapshot.report, snapshot.critique)
    ):
        raise ValueError("Completed run has missing stage outputs")
    if (
        run.state == State.COMPLETED
        and run.kind == "live"
        and (snapshot.critique_usage is None or snapshot.critique_usage.status != "validated")
    ):
        raise ValueError("Completed live run requires validated critique usage")
    if run.state == State.REPORT_READY and (
        snapshot.report is None
        or snapshot.synthesis is None
        or snapshot.synthesis.status != "validated"
    ):
        raise ValueError("Report-ready run has missing validated synthesis")
    lines = [
        "# Synapse report" if snapshot.report else "# Synapse evidence bundle",
        "",
        f"**{plain(run.label)}**",
        "",
        f"Run: {run.id}",
        f"Fixture: {plain(run.fixture_id)}" if run.fixture_id else "Mode: live discovery",
        f"Status: {run.state.value}",
        "",
    ]
    if run.state != State.COMPLETED:
        lines += [
            "**INCOMPLETE — missing stages are not inferred.**",
            "",
            plain(
                run.error
                or (
                    "Discovery and analysis finished; report and critique pending."
                    if run.state == State.SOURCES_READY
                    else "Report ready; critique pending."
                    if run.state == State.REPORT_READY
                    else "Run not finished."
                )
            ),
            "",
        ]
    if run.kind == "live":
        lines += [
            "## Request and limits",
            "",
            plain(run.input.question),
            "",
            f"Requested date filter: {plain(run.input.date_preference or 'any time')}",
            "",
        ]
        lines += [
            f"- {key}: {value}"
            for key, value in run.limits.model_dump().items()
            if key != "schema_version"
        ]
        lines += ["", "## Search outcomes (snippets are not evidence)", ""]
        if snapshot.discovery:
            for query in snapshot.discovery.queries:
                lines += [
                    f"- {query.id} · {plain(query.text)} · {query.status}",
                    plain(query.error or ""),
                ]
                for attempt in query.attempts:
                    lines += [
                        f"  Attempt {attempt.number}: {attempt.status}; "
                        f"HTTP {attempt.status_code}; {plain(attempt.error or '')}; "
                        f"request {plain(attempt.request_id or 'unknown')}; "
                        f"credits: {attempt.credits if attempt.credits is not None else 'unknown'}"
                    ]
        lines += [""]
    if run.synthesis_config:
        lines += [
            "## Synthesis configuration and usage",
            "",
            f"Model: {plain(run.model_id or 'unknown')}",
            f"Prompt: {plain(run.prompt_version or 'unknown')}",
            f"Input token limit: {run.synthesis_config.max_input_tokens}",
            f"Output token limit: {run.synthesis_config.max_output_tokens}",
            "Monetary cost: unavailable; free-tier eligibility depends on the project.",
            "",
        ]
        if snapshot.synthesis:
            lines += [
                f"- {key}: {plain(str(value))}"
                for key, value in snapshot.synthesis.model_dump().items()
                if key != "schema_version"
            ]
        lines += [""]
    if snapshot.report:
        lines += [f"Report version: {snapshot.report.version}", ""]
        evidence_map = {e.id: e for e in snapshot.analysis.evidence} if snapshot.analysis else {}
        for section in snapshot.report.sections:
            lines += [f"## {plain(section.title)}", "", plain(section.text), ""]
            if run.kind == "live":
                for claim in snapshot.report.claims:
                    if claim.section != section.title:
                        continue
                    citations = " ".join(
                        f"[{evidence_map[e].display_id}](#{evidence_map[e].display_id.lower()})"
                        for e in claim.evidence_ids
                    )
                    lines += [
                        f"- **{claim.display_id}** ({claim.support_status}) "
                        f"{plain(claim.text)} {citations}"
                    ]
        if run.kind == "fixture":
            for claim in snapshot.report.claims:
                citations = " ".join(
                    f"[{evidence_map[e].display_id}](#{evidence_map[e].display_id.lower()})"
                    for e in claim.evidence_ids
                )
                lines += [f"- **{claim.display_id}** {plain(claim.text)} {citations}"]
    if snapshot.analysis:
        lines += ["", "## References and evidence", ""]
        for source in snapshot.analysis.sources:
            lines += [
                f"- {source.display_id} · {source.id} · {plain(source.title)} · {source.status}",
                f"  Truncated: {source.truncated}. {plain(source.error or '')}",
                f"  Original URL: {plain(source.original_url)}",
                f"  Final URL: {plain(source.final_url)}",
                f"  Retrieved: {source.retrieved_at.isoformat()}",
                "  Publication date: "
                + (source.published_at.isoformat() if source.published_at else "unknown"),
                f"  SHA-256: {source.content_hash}",
            ]
        lines += [""]
        sources = {s.id: s for s in snapshot.analysis.sources}
        for evidence in snapshot.analysis.evidence:
            source = sources[evidence.source_id]
            lines += [
                f"### {evidence.display_id}",
                "",
                f"Evidence ID: {evidence.id}",
                "",
                plain(evidence.excerpt),
                "",
                f"Source: {source.id} ({source.display_id}) — {plain(source.title)}",
                f"URL: {plain(source.final_url)}",
                f"Offsets: {evidence.excerpt_start}:{evidence.excerpt_end}",
                f"Truncated: {source.truncated}; "
                f"publication date unknown: {source.published_at is None}",
                "",
            ]
    if snapshot.critique_usage:
        lines += [
            "## Critique configuration and usage",
            "",
            "Configuration: "
            + (plain(str(run.critique_config.model_dump())) if run.critique_config else "unknown"),
            f"Usage: {plain(str(snapshot.critique_usage.model_dump()))}",
            "Monetary cost: unavailable.",
            "",
        ]
    if snapshot.critique:
        lines += [
            "## Predetermined critique" if run.kind == "fixture" else "## Model critique",
            "",
            f"Score: {snapshot.critique.total}/10",
            plain(snapshot.critique.evaluator_model),
            f"Prompt: {plain(snapshot.critique.prompt_version)}",
            "",
        ]
        lines += [
            f"- {dimension}: {score}/2"
            for dimension, score in zip(RUBRIC, snapshot.critique.scores, strict=True)
        ]
        lines += [f"- {plain(f.comment)} (claim {f.claim_id})" for f in snapshot.critique.findings]
    lines += [
        "",
        "## Limitations",
        "",
        "Synthetic evidence and predetermined outputs do not establish research quality."
        if run.kind == "fixture"
        else "Model critique is not proof of truth; semantic support remains subject to review."
        if snapshot.critique
        else "Critique pending. Citation integrity does not establish semantic support."
        if snapshot.report
        else "Report and critique pending. Heuristic excerpts do not establish semantic support.",
        "",
    ]
    return "\n".join(lines), snapshot.model_dump_json(indent=2)
