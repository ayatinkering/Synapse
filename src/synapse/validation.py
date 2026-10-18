"""Deterministic integrity checks; these do not judge semantic claim support."""

from collections import Counter
from collections.abc import Sequence
from uuid import UUID

from synapse.models import Analysis, Critique, Discovery, Report, Run


def unique(values: Sequence[UUID | str]) -> None:
    if len(set(values)) != len(values):
        raise ValueError("Duplicate identifiers")


def validate_discovery(run: Run, result: Discovery) -> None:
    if result.run_id != run.id or not result.queries:
        raise ValueError("Invalid discovery ownership or empty queries")
    if len(result.queries) > run.limits.max_queries:
        raise ValueError("Query budget exceeded")
    unique([q.id for q in result.queries] + [c.id for c in result.candidates])
    query_ids = {q.id for q in result.queries}
    counts: Counter[UUID] = Counter()
    for query in result.queries:
        if query.run_id != run.id:
            raise ValueError("Cross-run query")
    for candidate in result.candidates:
        if (
            candidate.run_id != run.id
            or not candidate.query_ids
            or not set(candidate.query_ids) <= query_ids
        ):
            raise ValueError("Invalid candidate query ownership")
        counts.update(candidate.query_ids)
    if any(count > run.limits.results_per_query for count in counts.values()):
        raise ValueError("Search result budget exceeded")
    if len(result.candidates) > run.limits.max_sources:
        raise ValueError("Source budget exceeded")


def validate_analysis(run: Run, discovery: Discovery, result: Analysis) -> None:
    if result.run_id != run.id or len(result.sources) > run.limits.max_sources:
        raise ValueError("Invalid analysis ownership or source budget")
    candidates = {c.id: c for c in discovery.candidates}
    unique([s.id for s in result.sources] + [e.id for e in result.evidence])
    unique([s.display_id for s in result.sources])
    unique([e.display_id for e in result.evidence])
    sources = {s.id: s for s in result.sources}
    for source in result.sources:
        candidate = candidates.get(source.id)
        if source.run_id != run.id or candidate is None or source.query_ids != candidate.query_ids:
            raise ValueError("Invalid source ownership")
        if source.original_url != candidate.url:
            raise ValueError("Source URL does not match discovery")
        if len(source.extracted_text) > run.limits.text_characters:
            raise ValueError("Extraction budget exceeded")
    for evidence in result.evidence:
        source_match = sources.get(evidence.source_id)
        if evidence.run_id != run.id or source_match is None or source_match.status != "fetched":
            raise ValueError("Invalid evidence ownership")
        if not (
            0 <= evidence.excerpt_start < evidence.excerpt_end <= len(source_match.extracted_text)
        ):
            raise ValueError("Invalid excerpt offsets")
        if (
            source_match.extracted_text[evidence.excerpt_start : evidence.excerpt_end]
            != evidence.excerpt
        ):
            raise ValueError("Stored excerpt does not match source")


def independent_sources(result: Analysis) -> int:
    # Connected duplicate groups: shared URL OR hash cannot corroborate each other.
    groups: list[set[str]] = []
    for source in result.sources:
        if source.status != "fetched" or not source.extracted_text.strip():
            continue
        keys = {f"url:{source.final_url.rstrip('/').split('#')[0]}", f"hash:{source.content_hash}"}
        overlapping = [g for g in groups if g & keys]
        for group in overlapping:
            keys |= group
            groups.remove(group)
        groups.append(keys)
    return len(groups)


def validate_report(run: Run, analysis: Analysis, report: Report) -> None:
    if report.run_id != run.id:
        raise ValueError("Cross-run report")
    unique([c.id for c in report.claims])
    unique([c.display_id for c in report.claims])
    evidence = {e.id: e for e in analysis.evidence}
    if not report.claims:
        raise ValueError("Report has no evidence-backed claims")
    for claim in report.claims:
        if claim.run_id != run.id or (claim.requires_evidence and not claim.evidence_ids):
            raise ValueError("Claim requires owned evidence")
        if not set(claim.evidence_ids) <= evidence.keys():
            raise ValueError("Unknown evidence reference")
        if claim.quote is not None and not any(
            claim.quote in evidence[e].excerpt for e in claim.evidence_ids
        ):
            raise ValueError("Unsupported quoted excerpt")


def validate_critique(run: Run, report: Report, critique: Critique) -> None:
    if critique.run_id != run.id or critique.report_version != report.version:
        raise ValueError("Invalid critique ownership/version")
    if not {f.claim_id for f in critique.findings} <= {c.id for c in report.claims}:
        raise ValueError("Unknown critique claim")
