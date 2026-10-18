"""Public-HTML retrieval and deterministic, capped text extraction."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from synapse.models import Limits
from synapse.network import (
    HTTPTransport,
    Resolver,
    ToolError,
    Transport,
    WorkContext,
    public_addresses,
    public_url,
    read_body,
    resolve,
)


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    title: str = ""
    text: str = ""
    published_at: datetime | None = None
    truncated: bool = False
    error: str | None = None


class SafeFetcher:
    def __init__(self, *, transport: Transport | None = None, resolver: Resolver = resolve) -> None:
        self.transport = transport or HTTPTransport()
        self.resolver = resolver

    def fetch(self, url: str, context: WorkContext, limits: Limits | None = None) -> FetchResult:
        limits = limits or Limits()
        final_url = url
        for attempt in range(limits.transient_retries + 1):
            try:
                final_url = public_url(url)
                end = context.clock() + min(limits.fetch_timeout_seconds, context.remaining())
                for redirects in range(4):
                    budget = min(context.remaining(), end - context.clock())
                    if budget <= 0:
                        raise ToolError("TIMEOUT", transient=True)
                    addresses = public_addresses(final_url, self.resolver, min(5, budget))
                    budget = min(context.remaining(), end - context.clock())
                    if budget <= 0:
                        raise ToolError("TIMEOUT", transient=True)
                    response = self.transport.request(
                        "GET",
                        final_url,
                        addresses[0],
                        budget,
                        {
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Encoding": "identity",
                            "User-Agent": "SynapseResearch/0.1 (local evidence retrieval)",
                        },
                    )
                    try:
                        context.remaining()
                        if response.status in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if redirects == 3 or not location:
                                raise ToolError("REDIRECT_LIMIT")
                            redirected = public_url(urljoin(final_url, location))
                            if final_url.startswith("https:") and redirected.startswith("http:"):
                                raise ToolError("UNSAFE_REDIRECT")
                            final_url = redirected
                            continue
                        if response.status == 429 or 500 <= response.status <= 599:
                            raise ToolError("HTTP_TRANSIENT", transient=True)
                        if response.status != 200:
                            raise ToolError(
                                "ACCESS_DENIED" if response.status in {401, 403} else "HTTP_FAILED"
                            )
                        mime = (
                            response.headers.get("content-type", "").split(";")[0].strip().lower()
                        )
                        if mime not in {"text/html", "application/xhtml+xml"}:
                            raise ToolError("UNSUPPORTED_CONTENT")
                        body = read_body(response, context, end, limits.response_bytes)
                    finally:
                        response.close()
                    soup = BeautifulSoup(body, "html.parser")
                    title = soup.title.get_text(" ", strip=True)[:500] if soup.title else ""
                    published: datetime | None = None
                    tag = soup.find("meta", attrs={"property": "article:published_time"})
                    if tag is None:
                        tag = soup.find("meta", attrs={"name": "datePublished"})
                    if tag is not None:
                        try:
                            value = tag.get("content")
                            if isinstance(value, str):
                                published = datetime.fromisoformat(value.replace("Z", "+00:00"))
                                published = (
                                    published.astimezone(UTC)
                                    if published.tzinfo
                                    else published.replace(tzinfo=UTC)
                                )
                        except ValueError:
                            pass
                    for tag in soup(
                        [
                            "script",
                            "style",
                            "nav",
                            "form",
                            "header",
                            "footer",
                            "noscript",
                            "template",
                            "head",
                        ]
                    ):
                        tag.decompose()
                    main = soup.find("article") or soup.find("main") or soup.body or soup
                    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
                    if not text:
                        raise ToolError("EMPTY_EXTRACTION")
                    context.remaining()
                    return FetchResult(
                        final_url,
                        title,
                        text[: limits.text_characters],
                        published,
                        len(text) > limits.text_characters,
                    )
            except ToolError as error:
                if not error.transient or attempt == limits.transient_retries:
                    return FetchResult(final_url, error=error.code)
                context.sleep(float(2**attempt))
        raise AssertionError("Retry loop must return")
