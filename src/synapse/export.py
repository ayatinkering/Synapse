"""Render only validated saved outputs; every export carries its fixture label."""

import re

from synapse.models import LABEL, Snapshot, State
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
    lines = [
        "# Synapse report",
        "",
        f"**{LABEL}**",
        "",
        f"Run: {run.id}",
        f"Fixture: {plain(run.fixture_id)}",
        f"Status: {run.state.value}",
        "",
    ]
    if run.state != State.COMPLETED:
        lines += [
            "**INCOMPLETE — missing stages are not inferred.**",
            "",
            plain(run.error or "Run not finished."),
            "",
        ]
    if snapshot.report:
        lines += [f"Report version: {snapshot.report.version}", ""]
        for section in snapshot.report.sections:
            lines += [f"## {plain(section.title)}", "", plain(section.text), ""]
        evidence_map = {e.id: e for e in snapshot.analysis.evidence} if snapshot.analysis else {}
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
            ]
        lines += [""]
        sources = {s.id: s for s in snapshot.analysis.sources}
        for evidence in snapshot.analysis.evidence:
            source = sources[evidence.source_id]
            lines += [
                f"### {evidence.display_id}",
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
    if snapshot.critique:
        lines += [
            "## Predetermined critique",
            "",
            f"Score: {snapshot.critique.total}/10",
            plain(snapshot.critique.evaluator_model),
            "",
        ]
        lines += [f"- {plain(f.comment)} (claim {f.claim_id})" for f in snapshot.critique.findings]
    lines += [
        "",
        "## Limitations",
        "",
        "Synthetic evidence and predetermined outputs do not establish research quality.",
        "",
    ]
    return "\n".join(lines), snapshot.model_dump_json(indent=2)
