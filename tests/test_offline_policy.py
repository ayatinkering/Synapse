"""Check the guard before later milestones add external adapters."""

import socket

import pytest


def test_default_suite_rejects_network_connections() -> None:
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)
