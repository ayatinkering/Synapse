from collections.abc import Mapping


class Reply:
    def __init__(
        self, body: bytes = b"", status: int = 200, headers: Mapping[str, str] | None = None
    ) -> None:
        self.status = status
        self.headers = dict(headers or {"content-type": "text/html"})
        self.body = body
        self.closed = False

    def read(self, amount: int, timeout: float) -> bytes:
        chunk, self.body = self.body[:amount], self.body[amount:]
        return chunk

    def close(self) -> None:
        self.closed = True


class Wire:
    def __init__(self, replies: list[Reply]) -> None:
        self.replies = replies
        self.destinations: list[tuple[str, str]] = []

    def request(
        self,
        method: str,
        url: str,
        address: str,
        timeout: float,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> Reply:
        self.destinations.append((url, address))
        return self.replies.pop(0)
