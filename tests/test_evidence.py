from uuid import uuid4

import pytest

from synapse.fixtures import FixtureAdapter, list_fixtures
from synapse.models import Run
from synapse.validation import (
    independent_sources,
    validate_analysis,
    validate_discovery,
    validate_report,
)


def sample() -> tuple[Run, FixtureAdapter]:
    info = list_fixtures()[0]
    return Run(fixture_id=info.id, input=info.input), FixtureAdapter()


def test_fixture_preserves_exact_capped_evidence() -> None:
    run, adapter = sample()
    discovery = adapter.discover(run)
    validate_discovery(run, discovery)
    analysis = adapter.analyze(run, discovery)
    validate_analysis(run, discovery, analysis)
    assert len([s for s in analysis.sources if s.status == "fetched"]) == 2
    assert any(s.truncated for s in analysis.sources)
    assert any(s.published_at is None for s in analysis.sources)
    assert any(s.status == "failed" for s in analysis.sources)
    for evidence in analysis.evidence:
        source = next(s for s in analysis.sources if s.id == evidence.source_id)
        assert (
            source.extracted_text[evidence.excerpt_start : evidence.excerpt_end] == evidence.excerpt
        )
        assert len(source.extracted_text) <= 3000


def test_corrupt_offsets_are_rejected() -> None:
    run, adapter = sample()
    discovery = adapter.discover(run)
    analysis = adapter.analyze(run, discovery)
    bad = analysis.evidence[0].model_copy(update={"excerpt_start": 1})
    with pytest.raises(ValueError, match="excerpt"):
        validate_analysis(run, discovery, analysis.model_copy(update={"evidence": [bad]}))


def test_unknown_citation_cannot_be_rendered() -> None:
    run, adapter = sample()
    analysis = adapter.analyze(run, adapter.discover(run))
    report = adapter.synthesize(run, analysis)
    bad = report.claims[0].model_copy(update={"evidence_ids": [uuid4()]})
    with pytest.raises(ValueError, match="evidence"):
        validate_report(run, analysis, report.model_copy(update={"claims": [bad]}))


@pytest.mark.parametrize("change", ["quote", "run_id", "evidence_ids"])
def test_claims_reject_unsupported_quotes_and_cross_run_ids(change: str) -> None:
    run, adapter = sample()
    analysis = adapter.analyze(run, adapter.discover(run))
    report = adapter.synthesize(run, analysis)
    update: dict[str, object] = {
        "quote": "An invented measurement",
        "run_id": uuid4(),
        "evidence_ids": [],
    }
    bad = report.claims[0].model_copy(update={change: update[change]})
    with pytest.raises(ValueError):
        validate_report(run, analysis, report.model_copy(update={"claims": [bad]}))


def test_duplicate_content_cannot_corroborate_itself() -> None:
    run, adapter = sample()
    analysis = adapter.analyze(run, adapter.discover(run))
    first, second = analysis.sources[:2]
    duplicate = second.model_copy(
        update={"extracted_text": first.extracted_text, "content_hash": first.content_hash}
    )
    assert independent_sources(analysis.model_copy(update={"sources": [first, duplicate]})) == 1


def test_normalized_urls_cannot_count_twice() -> None:
    run, adapter = sample()
    analysis = adapter.analyze(run, adapter.discover(run))
    first, second = analysis.sources[:2]
    first = first.model_copy(update={"final_url": "https://EXAMPLE.invalid:443/page/#section"})
    second = second.model_copy(update={"final_url": "https://example.invalid/page"})
    assert independent_sources(analysis.model_copy(update={"sources": [first, second]})) == 1
