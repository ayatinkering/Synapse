import pytest
from network_fakes import Wire

from synapse.fetch import SafeFetcher
from synapse.network import WorkContext


@pytest.mark.parametrize(
    "url,addresses",
    [
        ("http://127.0.0.1/", ["127.0.0.1"]),
        ("https://example.org/", ["93.184.216.34", "10.0.0.1"]),
        ("http://[::ffff:127.0.0.1]/", ["::ffff:127.0.0.1"]),
        ("https://user:password@example.org/", ["93.184.216.34"]),
        ("http://example.org:8080/", ["93.184.216.34"]),
        ("file:///tmp/private", []),
    ],
)
def test_fetch_refuses_unsafe_destinations_without_connecting(
    url: str, addresses: list[str]
) -> None:
    wire = Wire([])
    result = SafeFetcher(transport=wire, resolver=lambda host, timeout: addresses).fetch(
        url, WorkContext()
    )
    assert result.error == "UNSAFE_URL"
    assert not wire.destinations


def test_fetch_extracts_only_clean_capped_html_and_preserves_metadata() -> None:
    from network_fakes import Reply

    from synapse.models import Limits

    response = Reply(b"""<html><head><title>AST Paper</title>
        <meta property="article:published_time" content="2026-01-01T10:00:00Z"></head>
        <body><nav>navigation</nav><main><p>AST trees. Dynamic calls.</p>
        <script>ignore me</script><form>secret form</form></main>
        <footer>footer</footer></body></html>""")
    wire = Wire([response])
    result = SafeFetcher(transport=wire, resolver=lambda h, t: ["93.184.216.34"]).fetch(
        "https://example.org/paper", WorkContext(), Limits(text_characters=10)
    )
    assert result.error is None and result.text == "AST trees." and result.truncated
    assert result.title == "AST Paper"
    assert result.published_at and result.published_at.isoformat() == "2026-01-01T10:00:00+00:00"
    assert wire.destinations == [("https://example.org/paper", "93.184.216.34")]
    assert response.closed


@pytest.mark.parametrize(
    "status,headers,body,error",
    [
        (403, {}, b"", "ACCESS_DENIED"),
        (200, {"content-type": "application/pdf"}, b"pdf", "UNSUPPORTED_CONTENT"),
        (
            200,
            {"content-type": "text/html", "content-length": "2000001"},
            b"",
            "RESPONSE_TOO_LARGE",
        ),
        (
            200,
            {"content-type": "text/html", "content-encoding": "gzip"},
            b"",
            "UNSUPPORTED_ENCODING",
        ),
        (200, {"content-type": "text/html"}, b"<script>no article</script>", "EMPTY_EXTRACTION"),
    ],
)
def test_fetch_records_permanent_failures_without_retry(
    status: int, headers: dict[str, str], body: bytes, error: str
) -> None:
    from network_fakes import Reply

    reply = Reply(body, status, headers)
    result = SafeFetcher(transport=Wire([reply]), resolver=lambda h, t: ["93.184.216.34"]).fetch(
        "https://example.org/", WorkContext()
    )
    assert result.error == error and reply.closed


def test_redirect_dns_is_revalidated_and_cannot_rebind_to_private_address() -> None:
    from network_fakes import Reply

    reply = Reply(status=302, headers={"location": "/next"})
    wire = Wire([reply])
    answers = iter([["93.184.216.34"], ["169.254.169.254"]])
    result = SafeFetcher(transport=wire, resolver=lambda h, t: next(answers)).fetch(
        "https://example.org/", WorkContext()
    )
    assert result.error == "UNSAFE_URL" and len(wire.destinations) == 1 and reply.closed


def test_slow_stream_is_bounded_even_when_chunks_keep_arriving() -> None:
    from network_fakes import Reply

    from synapse.models import Limits

    clock = [0.0]

    class SlowReply(Reply):
        def read(self, amount: int, timeout: float) -> bytes:
            clock[0] += 16
            return b"x"

    context = WorkContext(clock=lambda: clock[0], deadline=600)
    result = SafeFetcher(
        transport=Wire([SlowReply()]), resolver=lambda h, t: ["93.184.216.34"]
    ).fetch("https://example.org/", context, Limits(transient_retries=0))
    assert result.error == "TIMEOUT"


@pytest.mark.parametrize(
    "locations,error",
    [
        (["http://example.org/down"], "UNSAFE_REDIRECT"),
        (["/one", "/two", "/three", "/four"], "REDIRECT_LIMIT"),
    ],
)
def test_redirects_cannot_downgrade_or_exceed_cap(locations: list[str], error: str) -> None:
    from network_fakes import Reply

    wire = Wire([Reply(status=302, headers={"location": location}) for location in locations])
    result = SafeFetcher(transport=wire, resolver=lambda h, t: ["93.184.216.34"]).fetch(
        "https://example.org/", WorkContext()
    )
    assert result.error == error


def test_streamed_size_cap_is_enforced_without_content_length() -> None:
    from network_fakes import Reply

    from synapse.models import Limits

    response = Reply(b"<p>" + b"x" * 100 + b"</p>")
    result = SafeFetcher(transport=Wire([response]), resolver=lambda h, t: ["93.184.216.34"]).fetch(
        "https://example.org/", WorkContext(), Limits(response_bytes=100)
    )
    assert result.error == "RESPONSE_TOO_LARGE" and response.closed


def test_transient_fetch_retry_reresolves_and_cannot_rebind() -> None:
    from network_fakes import Reply

    clock = [0.0]
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])
    wire = Wire([Reply(status=503)])

    def wait(seconds: float) -> None:
        clock[0] += seconds

    context = WorkContext(clock=lambda: clock[0], deadline=600, waiter=wait)
    result = SafeFetcher(transport=wire, resolver=lambda h, t: next(answers)).fetch(
        "https://example.org/", context
    )
    assert result.error == "UNSAFE_URL" and len(wire.destinations) == 1


def test_bad_tls_fails_closed_without_retry_and_uses_original_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ssl

    import urllib3

    class BadTLS:
        sock = None

        def __init__(self, host: str, **kwargs: object) -> None:
            assert host == "93.184.216.34"
            assert kwargs["server_hostname"] == "example.org"
            assert kwargs["assert_hostname"] == "example.org"
            context = kwargs["ssl_context"]
            assert isinstance(context, ssl.SSLContext) and context.verify_mode == ssl.CERT_REQUIRED

        def connect(self) -> None:
            raise ssl.SSLCertVerificationError("untrusted certificate: secret raw error")

        def close(self) -> None:
            pass

    monkeypatch.setattr(urllib3.connection, "HTTPSConnection", BadTLS)
    result = SafeFetcher(resolver=lambda h, t: ["93.184.216.34"]).fetch(
        "https://example.org/", WorkContext()
    )
    assert result.error == "TLS_FAILED" and "secret" not in result.error


@pytest.mark.parametrize(
    "address", ["::1", "fe80::1", "fc00::1", "224.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::"]
)
def test_ipv6_transition_and_special_addresses_are_not_public_fetch_targets(address: str) -> None:
    wire = Wire([])
    result = SafeFetcher(transport=wire, resolver=lambda h, t: [address]).fetch(
        "https://example.org/", WorkContext()
    )
    assert result.error == "UNSAFE_URL" and not wire.destinations
