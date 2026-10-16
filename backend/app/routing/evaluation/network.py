"""Process-scoped offline guard. Workers never connect to any network address."""

import socket
from contextlib import contextmanager
from unittest.mock import patch


class OfflineNetworkError(RuntimeError):
    pass


def denied(*args, **kwargs):
    raise OfflineNetworkError("Offline evaluation attempted a network connection")


@contextmanager
def no_network():
    # Used only in the isolated CLI worker, never in a running API process.
    with (
        patch.object(socket.socket, "connect", denied),
        patch.object(socket.socket, "connect_ex", denied),
        patch.object(socket, "create_connection", denied),
        patch.object(socket, "getaddrinfo", denied),
        patch.object(socket.socket, "sendto", denied),
    ):
        yield
