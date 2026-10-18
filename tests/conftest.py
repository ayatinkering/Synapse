"""Default tests must never silently start provider or other network requests."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Block Python socket connections except in explicitly selected live tests.

    This catches accidental in-process network calls; it is not a process sandbox.
    """
    if request.node.get_closest_marker("live"):
        return

    def denied(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network access is disabled in offline tests")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
