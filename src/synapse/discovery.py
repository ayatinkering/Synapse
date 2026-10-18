"""Deterministic live discovery and evidence selection; no model or synthesis calls."""

import re
from collections.abc import Callable, Iterator
from hashlib import sha256
from typing import Literal

from synapse.fetch import SafeFetcher
from synapse.models import Analysis, Candidate, Discovery, Evidence, Query, Run, Source
from synapse.network import ToolError, WorkContext, public_url
from synapse.search import TavilySearch
from synapse.validation import normalize_url

LIVE_LABEL: Literal["Live discovery — report pending"] = "Live discovery — report pending"


def select_excerpts(text: str, question: str) -> list[tuple[int, int]]:
    terms = {term.casefold() for term in re.findall(r"\w{3,}", question)}
    spans = [
        (m.start(), m.end()) for m in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text) if m.group().strip()
    ]
    ranked = sorted(
        spans,
        key=lambda span: (
            -len(terms & {t.casefold() for t in re.findall(r"\w{3,}", text[span[0] : span[1]])}),
            span[0],
        ),
    )[:3]
    return [
        (
            start + len(text[start:end]) - len(text[start:end].lstrip()),
            end - len(text[start:end]) + len(text[start:end].rstrip()),
        )
        for start, end in sorted(ranked)
    ]


class LiveDiscovery:
    def __init__(self, search: TavilySearch, fetcher: SafeFetcher) -> None:
        self.search, self.fetcher = search, fetcher

    def discover(
        self,
        run: Run,
        queries: list[str],
        context: WorkContext,
        checkpoint: Callable[[Discovery], None],
    ) -> Discovery:
        results: list[Query] = []
        candidates: dict[str, Candidate] = {}
        for text in queries:
            context.remaining()
            query, hits = self.search.search(
                Query(
                    run_id=run.id,
                    text=text,
                    provider="tavily",
                    requested_date_filter=run.input.date_preference,
                ),
                run.limits,
                context,
                checkpoint=lambda progress: checkpoint(
                    Discovery(
                        run_id=run.id,
                        queries=[*results, progress],
                        candidates=list(candidates.values()),
                    )
                ),
            )
            results.append(query)
            for hit in hits:
                try:
                    url = normalize_url(public_url(hit.url))
                except ToolError:
                    url = hit.url
                if url in candidates:
                    old = candidates[url]
                    candidates[url] = old.model_copy(
                        update={
                            "query_ids": list(dict.fromkeys([*old.query_ids, *hit.query_ids])),
                            "search_hits": [*old.search_hits, *hit.search_hits],
                        }
                    )
                elif len(candidates) < run.limits.max_sources:
                    candidates[url] = hit
            discovery = Discovery(
                run_id=run.id, queries=results[:], candidates=list(candidates.values())
            )
            checkpoint(discovery)
            if query.error in {"SEARCH_AUTH", "SEARCH_QUOTA"}:
                break
        return discovery

    def analyze(self, run: Run, discovery: Discovery, context: WorkContext) -> Iterator[Analysis]:
        sources: list[Source] = []
        evidence: list[Evidence] = []
        for candidate in discovery.candidates:
            context.remaining()
            fetched = self.fetcher.fetch(candidate.url, context, run.limits)
            source = Source(
                id=candidate.id,
                run_id=run.id,
                query_ids=candidate.query_ids,
                display_id=f"S{len(sources) + 1:02}",
                original_url=candidate.url,
                final_url=fetched.final_url,
                title=fetched.title or candidate.title,
                published_at=fetched.published_at,
                extracted_text=fetched.text,
                content_hash=sha256(fetched.text.encode()).hexdigest(),
                truncated=fetched.truncated,
                status="failed" if fetched.error else "fetched",
                error=fetched.error,
                label=LIVE_LABEL,
            )
            sources.append(source)
            if not fetched.error:
                for start, end in select_excerpts(
                    fetched.text, " ".join([run.input.question, *run.input.subquestions])
                ):
                    evidence.append(
                        Evidence(
                            run_id=run.id,
                            source_id=source.id,
                            display_id=f"E{len(evidence) + 1:02}",
                            excerpt=fetched.text[start:end],
                            excerpt_start=start,
                            excerpt_end=end,
                            relevance_note="Heuristic term overlap; not semantic validation.",
                            limitations="Capped snapshot; relevance and claims require review.",
                        )
                    )
            yield Analysis(run_id=run.id, sources=sources[:], evidence=evidence[:])
