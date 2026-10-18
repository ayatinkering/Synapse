"""Bounded, pinned-IP HTTP operations. No ambient cookies, proxies, or retries."""

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import Event, Timer
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import dns.exception
import dns.resolver
import urllib3


class ToolError(Exception):
    def __init__(self, code: str, *, transient: bool = False, fatal: bool = False) -> None:
        super().__init__(code)
        self.code, self.transient, self.fatal = code, transient, fatal


class StopWork(Exception):
    """A safe cancellation/deadline signal; completed checkpoints remain authoritative."""


@dataclass
class WorkContext:
    clock: Callable[[], float] = monotonic
    cancelled: Callable[[], bool] = lambda: False
    deadline: float = field(default_factory=lambda: monotonic() + 600)
    waiter: Callable[[float], object] = Event().wait

    def remaining(self) -> float:
        if self.cancelled():
            raise StopWork("CANCELLED")
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise StopWork("DEADLINE_EXCEEDED")
        return remaining

    def sleep(self, seconds: float) -> None:
        if seconds >= self.remaining():
            raise StopWork("DEADLINE_EXCEEDED")
        # Short waits make backoff cancellable without a worker calling UI APIs.
        end = self.clock() + seconds
        while self.clock() < end:
            self.waiter(min(0.1, end - self.clock(), self.remaining()))


class Response(Protocol):
    status: int

    @property
    def headers(self) -> Mapping[str, str]: ...
    def read(self, amount: int, timeout: float) -> bytes: ...
    def close(self) -> None: ...


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Response: ...


Resolver = Callable[[str, float], list[str]]


def resolve(host: str, timeout: float) -> list[str]:
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    deadline = monotonic() + timeout
    resolver = dns.resolver.Resolver()
    addresses: list[str] = []
    try:
        for family in ("A", "AAAA"):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise ToolError("DNS_TIMEOUT", transient=True)
            try:
                answer = resolver.resolve(host, family, lifetime=remaining, search=False)
                addresses.extend(str(item) for item in answer)
            except dns.resolver.NoAnswer:
                continue
    except dns.exception.Timeout as error:
        raise ToolError("DNS_TIMEOUT", transient=True) from error
    except dns.exception.DNSException as error:
        raise ToolError("DNS_FAILED") from error
    if not addresses:
        raise ToolError("DNS_FAILED")
    return addresses


def public_url(url: str) -> str:
    try:
        if "\\" in url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None or "%" in parts.hostname:
            raise ValueError
        scheme = parts.scheme.lower()
        if parts.port not in {None, 443 if scheme == "https" else 80}:
            raise ValueError
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if not host or len(host) > 253:
            raise ValueError
        if ":" in host:
            ipaddress.IPv6Address(host)
            host = f"[{host}]"
        elif any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not all(c.isalnum() or c == "-" for c in label)
            for label in host.split(".")
        ):
            raise ValueError
        path = parts.path or "/"
        return urlunsplit((scheme, host, path, parts.query, ""))
    except (ValueError, UnicodeError) as error:
        raise ToolError("UNSAFE_URL") from error


def public_addresses(url: str, resolver: Resolver, timeout: float) -> list[str]:
    host = urlsplit(url).hostname
    if host is None:
        raise ToolError("UNSAFE_URL")
    addresses = resolver(host, timeout)
    try:
        if not addresses:
            raise ValueError
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                raise ValueError
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
                mapped = ip.ipv4_mapped
                if not mapped.is_global or mapped.is_multicast or mapped.is_reserved:
                    raise ValueError
    except ValueError as error:
        raise ToolError("UNSAFE_URL") from error
    return addresses


def network_error(error: Exception) -> ToolError:
    if isinstance(error, (urllib3.exceptions.SSLError, ssl.SSLError)):
        return ToolError("TLS_FAILED")
    return ToolError("NETWORK_ERROR", transient=True)


class HTTPResponse:
    def __init__(
        self,
        response: urllib3.HTTPResponse,
        connection: urllib3.connection.HTTPConnection,
        timer: Timer,
    ) -> None:
        self.response, self.connection, self.timer = response, connection, timer
        self.status = response.status
        self.headers = {k.lower(): v for k, v in response.headers.items()}

    def read(self, amount: int, timeout: float) -> bytes:
        try:
            if self.connection.sock is not None:
                self.connection.sock.settimeout(timeout)
            return self.response.read1(amount, decode_content=False)
        except (urllib3.exceptions.HTTPError, OSError, http.client.HTTPException) as error:
            raise network_error(error) from error

    def close(self) -> None:
        self.timer.cancel()
        self.response.close()
        self.connection.close()


class HTTPTransport:
    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Response:
        parts = urlsplit(url)
        host = parts.hostname or ""
        connection: urllib3.connection.HTTPConnection
        if parts.scheme == "https":
            connection = urllib3.connection.HTTPSConnection(
                address,
                port=443,
                timeout=timeout,
                server_hostname=host,
                assert_hostname=host,
                ssl_context=ssl.create_default_context(),
            )
        else:
            connection = urllib3.connection.HTTPConnection(address, port=80, timeout=timeout)

        # A read timeout alone resets on every header read. Close the socket at the
        # absolute attempt deadline as well, including a slow-drip response header.
        expired = Event()
        response: urllib3.HTTPResponse | None = None

        def abort() -> None:
            expired.set()
            if response is not None:
                try:
                    response.shutdown()
                except (OSError, ValueError):
                    pass
            if connection.sock is not None:
                try:
                    connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()

        timer = Timer(timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            connection.connect()
            if expired.is_set():
                raise ToolError("TIMEOUT", transient=True)
            connection.request(
                method,
                urlunsplit(("", "", parts.path or "/", parts.query, "")),
                body=body,
                headers={**headers, "Host": parts.netloc},
                preload_content=False,
                decode_content=False,
            )
            response = connection.getresponse()
            if expired.is_set():
                response.close()
                raise ToolError("TIMEOUT", transient=True)
            return HTTPResponse(response, connection, timer)
        except (urllib3.exceptions.HTTPError, OSError, http.client.HTTPException) as error:
            timer.cancel()
            connection.close()
            raise network_error(error) from error
        except Exception:
            timer.cancel()
            connection.close()
            raise


def read_body(response: Response, context: WorkContext, attempt_end: float, cap: int) -> bytes:
    encoding = response.headers.get("content-encoding", "identity").lower()
    if encoding != "identity":
        raise ToolError("UNSUPPORTED_ENCODING")
    length = response.headers.get("content-length")
    if length:
        try:
            if int(length) < 0:
                raise ValueError
            if int(length) > cap:
                raise ToolError("RESPONSE_TOO_LARGE")
        except ValueError as error:
            raise ToolError("INVALID_LENGTH") from error
    data = bytearray()
    while True:
        budget = min(context.remaining(), attempt_end - context.clock())
        if budget <= 0:
            raise ToolError("TIMEOUT", transient=True)
        chunk = response.read(min(16_384, cap + 1 - len(data)), budget)
        context.remaining()
        if context.clock() >= attempt_end:
            raise ToolError("TIMEOUT", transient=True)
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > cap:
            raise ToolError("RESPONSE_TOO_LARGE")
