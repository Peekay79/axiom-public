import pytest
import socket

from tests.utils.no_network import no_network_if_enabled


def test_no_network_guard_blocks_when_enabled(monkeypatch):
    monkeypatch.setenv("NO_NETWORK", "1")
    with no_network_if_enabled():
        with pytest.raises(RuntimeError):
            socket.socket()

