import os
import socket
from contextlib import contextmanager


@contextmanager
def no_network_if_enabled():
    if os.environ.get("NO_NETWORK") != "1":
        yield
        return
    orig_socket = socket.socket

    def _blocked(*a, **k):
        raise RuntimeError("Network disabled for tests (NO_NETWORK=1)")

    socket.socket = _blocked
    try:
        yield
    finally:
        socket.socket = orig_socket

