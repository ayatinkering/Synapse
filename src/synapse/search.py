"""Tavily search with explicit request budgets and sanitized attempt records."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from synapse.models import Attempt, Candidate, Limits, Query, SearchHit
from synapse.network import (
    HTTPTransport,
    Resolver,
    ToolError,
    Transport,
    WorkContext,
    public_addresses,
    read_body,
    resolve,
)

ENDPOINT = "https://api.tavily.com/search"


class Hit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: str = Field(min_length=1, max_length=8192)
    title: str = Field(default="", max_length=2000)
    content: str = Field(default="", max_length=100_000)
    score: float | None = Field(default=None, allow_inf_nan=False)


class Usage(BaseModel):
    credits: float = Field(ge=0, allow_inf_nan=False)


class SearchPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[Hit] = Field(max_length=100)
    request_id: str | None = Field(default=None, max_length=200)
    usage: Usage | None = None


def retry_delay(value: str | None, fallback: float) -> float:
    if value:
        try:
            seconds = float(value)
            if 0 <= seconds <= 86400:
                return max(fallback, seconds)
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                return max(fallback, (date - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return fallback


class TavilySearch:
    def __init__(
        self, key: str, *, transport: Transport | None = None, resolver: Resolver = resolve
    ) -> None:
        self._key = key
        self.transport = transport or HTTPTransport()
        self.resolver = resolver

    def search(
        self,
        query: Query,
        limits: Limits,
        context: WorkContext,
        checkpoint: Callable[[Query], None] | None = None,
    ) -> tuple[Query, list[Candidate]]:
        attempts: list[Attempt] = []
        for number in range(1, limits.transient_retries + 2):
            status_code: int | None = None
            delay = float(2 ** (number - 1))
            try:
                end = context.clock() + min(15, context.remaining())
                addresses = public_addresses(ENDPOINT, self.resolver, min(5, context.remaining()))
                budget = min(context.remaining(), end - context.clock())
                if budget <= 0:
                    raise ToolError("TIMEOUT", transient=True)
                payload: dict[str, Any] = {
                    "query": query.text,
                    "search_depth": "basic",
                    "auto_parameters": False,
                    "max_results": limits.results_per_query,
                    "topic": "general",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                    "include_usage": True,
                }
                if query.requested_date_filter:
                    payload["time_range"] = query.requested_date_filter
                attempts.append(Attempt(number=number, status="started"))
                if checkpoint:
                    checkpoint(
                        query.model_copy(update={"status": "pending", "attempts": attempts[:]})
                    )
                response = self.transport.request(
                    "POST",
                    ENDPOINT,
                    addresses[0],
                    budget,
                    {
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    json.dumps(payload).encode(),
                )
                try:
                    context.remaining()
                    status_code = response.status
                    delay = retry_delay(response.headers.get("retry-after"), delay)
                    if status_code in {401, 403}:
                        raise ToolError("SEARCH_AUTH", fatal=True)
                    if status_code in {402, 432, 433}:
                        raise ToolError("SEARCH_QUOTA", fatal=True)
                    if status_code == 429 or 500 <= status_code <= 599:
                        raise ToolError("SEARCH_TRANSIENT", transient=True)
                    if status_code != 200:
                        raise ToolError("SEARCH_HTTP_FAILED")
                    raw = read_body(response, context, end, limits.response_bytes)
                    try:
                        result = SearchPayload.model_validate_json(raw)
                    except ValidationError as error:
                        raise ToolError("SEARCH_MALFORMED") from error
                finally:
                    response.close()
                attempts[-1] = Attempt(
                    number=number,
                    status="success",
                    status_code=status_code,
                    request_id=result.request_id,
                    credits=result.usage.credits if result.usage else None,
                )
                candidates = [
                    Candidate(
                        run_id=query.run_id,
                        query_ids=[query.id],
                        url=hit.url,
                        title=hit.title[:500],
                        relevance="Provider-ranked search result; not fetched evidence.",
                        search_hits=[
                            SearchHit(
                                query_id=query.id,
                                rank=rank,
                                score=hit.score,
                                snippet=hit.content[:1000],
                            )
                        ],
                    )
                    for rank, hit in enumerate(result.results[: limits.results_per_query], start=1)
                ]
                return query.model_copy(
                    update={"status": "success", "attempts": attempts}
                ), candidates
            except ToolError as error:
                failed = Attempt(
                    number=number, status="failed", status_code=status_code, error=error.code
                )
                if attempts and attempts[-1].number == number:
                    attempts[-1] = failed
                else:
                    attempts.append(failed)
                if checkpoint:
                    checkpoint(
                        query.model_copy(update={"status": "pending", "attempts": attempts[:]})
                    )
                if not error.transient or number > limits.transient_retries:
                    return query.model_copy(
                        update={"status": "failed", "error": error.code, "attempts": attempts}
                    ), []
                context.sleep(delay)
        raise AssertionError("Retry loop must return")
