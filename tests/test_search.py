import json
from typing import Any
from uuid import uuid4

import pytest
from network_fakes import Reply, Wire

from synapse.models import Limits, Query
from synapse.network import WorkContext
from synapse.search import TavilySearch


def test_search_uses_bounded_basic_request_and_retains_rank_usage() -> None:
    class SearchWire(Wire):
        def request(
            self,
            method: str,
            url: str,
            address: str,
            timeout: float,
            headers: dict[str, str],
            body: bytes | None = None,
        ) -> Reply:
            assert method == "POST" and url == "https://api.tavily.com/search"
            assert headers["Authorization"] == "Bearer test-only-key"
            assert body
            payload = json.loads(body)
            assert payload["search_depth"] == "basic"
            assert payload["auto_parameters"] is False
            assert payload["include_raw_content"] is False and payload["include_answer"] is False
            assert payload["include_usage"] is True and payload["max_results"] == 5
            assert payload["time_range"] == "month"
            return super().request(method, url, address, timeout, headers, body)

    payload: dict[str, Any] = {
        "results": [
            {
                "url": "https://example.org/paper",
                "title": "Paper",
                "content": "Snippet",
                "score": 0.9,
            },
        ],
        "request_id": "req-1",
        "usage": {"credits": 1},
    }
    wire = SearchWire(
        [Reply(json.dumps(payload).encode(), headers={"content-type": "application/json"})]
    )
    query = Query(run_id=uuid4(), text="AST retrieval", requested_date_filter="month")
    result, hits = TavilySearch(
        "test-only-key", transport=wire, resolver=lambda host, timeout: ["93.184.216.34"]
    ).search(query, Limits(), WorkContext())
    assert result.status == "success" and result.attempts[0].credits == 1
    assert result.attempts[0].request_id == "req-1"
    assert len(hits) == 1 and hits[0].search_hits[0].snippet == "Snippet"
    assert hits[0].search_hits[0].rank == 1


def test_search_retries_are_visible_and_backoff_honors_retry_after() -> None:
    clock = [0.0]
    waits: list[float] = []

    def wait(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    wire = Wire(
        [
            Reply(status=429, headers={"retry-after": "3"}),
            Reply(status=500),
            Reply(b'{"results": [], "usage": {"credits": 1}}'),
        ]
    )
    result, hits = TavilySearch(
        "test-only-key", transport=wire, resolver=lambda h, t: ["93.184.216.34"]
    ).search(
        Query(run_id=uuid4(), text="AST"),
        Limits(),
        WorkContext(clock=lambda: clock[0], deadline=600, waiter=wait),
    )
    assert result.status == "success" and not hits
    assert [a.status_code for a in result.attempts] == [429, 500, 200]
    assert len(wire.destinations) == 3
    assert abs(sum(waits) - 5) < 0.00001


@pytest.mark.parametrize(
    "status,body,error",
    [
        (401, b"secret raw error", "SEARCH_AUTH"),
        (432, b"secret raw error", "SEARCH_QUOTA"),
        (200, b'{"results": "bad"}', "SEARCH_MALFORMED"),
        (200, b'{"results": [], "usage": {"credits": -1}}', "SEARCH_MALFORMED"),
    ],
)
def test_search_permanent_errors_do_not_retry_or_leak_body(
    status: int, body: bytes, error: str
) -> None:
    result, hits = TavilySearch(
        "test-only-key",
        transport=Wire([Reply(body, status)]),
        resolver=lambda h, t: ["93.184.216.34"],
    ).search(Query(run_id=uuid4(), text="AST"), Limits(), WorkContext())
    assert result.error == error and not hits and len(result.attempts) == 1
    assert "secret" not in result.model_dump_json()
