"""Authored synthetic examples. No external source is fetched or represented as read."""

from hashlib import sha256
from importlib.resources import files
from typing import Protocol

from synapse.models import (
    Analysis,
    Candidate,
    Claim,
    Critique,
    Discovery,
    Evidence,
    Finding,
    FixtureInfo,
    Query,
    Report,
    Run,
    Section,
    Source,
)


def list_fixtures() -> list[FixtureInfo]:
    from pydantic import TypeAdapter

    return TypeAdapter(list[FixtureInfo]).validate_json(
        files("synapse").joinpath("fixtures/catalog.json").read_text()
    )


def get_fixture(fixture_id: str) -> FixtureInfo:
    for info in list_fixtures():
        if info.id == fixture_id:
            return info
    raise ValueError("Unknown fixture")


class Stages(Protocol):
    def discover(self, run: Run) -> Discovery: ...
    def analyze(self, run: Run, discovery: Discovery) -> Analysis: ...
    def synthesize(self, run: Run, analysis: Analysis) -> Report: ...
    def critique(self, run: Run, report: Report) -> Critique: ...


class FixtureAdapter:
    def discover(self, run: Run) -> Discovery:
        info = get_fixture(run.fixture_id)
        queries = [Query(run_id=run.id, text=text) for text in info.queries]
        candidates = [
            Candidate(
                run_id=run.id,
                query_ids=[queries[min(i, len(queries) - 1)].id],
                url=f"https://fixtures.synapse.invalid/source-{i + 1}",
                title=title,
                relevance="Authored fixture for inspecting provenance.",
            )
            for i, title in enumerate(
                [
                    "Synthetic AST example",
                    "Synthetic embedding example",
                    "Synthetic unavailable page",
                ]
            )
        ]
        if run.fixture_id == "sparse":
            candidates = [candidates[0], candidates[2]]
        return Discovery(run_id=run.id, queries=queries, candidates=candidates)

    def analyze(self, run: Run, discovery: Discovery) -> Analysis:
        sources: list[Source] = []
        evidence: list[Evidence] = []
        for i, candidate in enumerate(discovery.candidates):
            failed = candidate.title == "Synthetic unavailable page"
            excerpt = (
                "In this synthetic AST example, named symbols supply structural matches; "
                "unresolved dynamic calls remain outside the example."
                if "AST" in candidate.title
                else "In this synthetic embedding example, wording similarity supplies candidate "
                "matches; a similarity score alone does not establish relevance."
            )
            full_text = "" if failed else excerpt + "\n" + ("Synthetic background context. " * 150)
            text = full_text[: run.limits.text_characters]
            source = Source(
                id=candidate.id,
                run_id=run.id,
                query_ids=candidate.query_ids,
                display_id=f"S{i + 1:02}",
                original_url=candidate.url,
                final_url=candidate.url,
                title=candidate.title,
                extracted_text=text,
                content_hash=sha256(text.encode()).hexdigest(),
                truncated=len(full_text) > len(text),
                status="failed" if failed else "fetched",
                error="Synthetic unavailable page; no request was made." if failed else None,
            )
            sources.append(source)
            if not failed:
                selected = excerpt[: len(text)]
                evidence.append(
                    Evidence(
                        run_id=run.id,
                        source_id=source.id,
                        display_id=f"E{len(evidence) + 1:02}",
                        excerpt=selected,
                        excerpt_start=0,
                        excerpt_end=len(selected),
                        relevance_note="Describes a fixture mechanism and its limitation.",
                    )
                )
        return Analysis(run_id=run.id, sources=sources, evidence=evidence)

    def synthesize(self, run: Run, analysis: Analysis) -> Report:
        return Report(
            run_id=run.id,
            sections=[
                Section(title="Question and scope", text=run.input.question),
                Section(title="Approach", text="Compare two authored synthetic examples."),
                Section(title="Findings", text="The claims below reproduce the fixture evidence."),
                Section(
                    title="Comparison", text="These examples contrast structure with similarity."
                ),
                Section(
                    title="Limitations",
                    text="Synthetic, capped snapshots cannot establish real-world performance.",
                ),
                Section(
                    title="Conclusion",
                    text="Inspect the excerpts; do not treat this demonstration as research.",
                ),
            ],
            claims=[
                Claim(
                    run_id=run.id,
                    display_id=f"C{i + 1:02}",
                    text=e.excerpt,
                    evidence_ids=[e.id],
                    quote=e.excerpt,
                )
                for i, e in enumerate(analysis.evidence)
            ],
            validation_results=["Evidence references and quoted excerpts validated."],
        )

    def critique(self, run: Run, report: Report) -> Critique:
        return Critique(
            run_id=run.id,
            scores=[2, 1, 0, 2, 1],
            total=6,
            findings=[
                Finding(
                    claim_id=report.claims[0].id,
                    comment="Predetermined: the excerpt has no performance measurement.",
                )
            ],
        )
