#!/usr/bin/env python3
"""Run pytest without ambient credentials, dotenv, DNS or external sockets.

Only an explicitly selected disposable loopback PostgreSQL test database can be
enabled. Source acquisition is a separate command; tests cannot contact Mentro
or any other external service, even if a provider is accidentally left real.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


def install(*, loopback=False):
    for key in list(os.environ):
        if key.startswith(
            ("MENTRO_", "OPENAI_", "ANTHROPIC_", "GOOGLE_", "AWS_", "PG")
        ) or key in {
            "DATABASE_URL",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "MAPBOX_API",
            "OPENCAGE_KEY",
            "CAR_DATA_API",
            "ROUTING_REMOTE_URL",
            "ROADTRIPS_DATABASE_TARGET",
            "ROADTRIPS_NEON_WRITES_ENABLED",
            "LOCAL_PREVIEW",
            "CORS_ORIGINS",
        }:
            os.environ.pop(key, None)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    # Older python-dotenv versions need the explicit override as well.
    import dotenv

    dotenv.load_dotenv = lambda *args, **kwargs: False
    if not loopback:
        os.environ.pop("CATALOG_TEST_DATABASE_URL", None)
    elif value := os.environ.get("CATALOG_TEST_DATABASE_URL"):
        target = urlparse(value)
        if (
            target.hostname not in {"127.0.0.1", "localhost", "::1"}
            or target.path != "/catalog_test"
        ):
            raise ValueError(
                "only the disposable loopback catalog_test database is allowed"
            )
    original_connect, original_connect_ex = (
        socket.socket.connect,
        socket.socket.connect_ex,
    )
    original_getaddrinfo = socket.getaddrinfo

    def permitted(host):
        if not loopback:
            return False
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def check(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6} and not permitted(
            address[0]
        ):
            raise OSError("offline tests prohibit external network connections")

    def connect(sock, address):
        check(sock, address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(sock, address)
        return original_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if host is not None and not permitted(host):
            raise OSError("offline tests prohibit external DNS resolution")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-loopback", action="store_true")
    args, pytest_args = parser.parse_known_args()
    install(loopback=args.allow_loopback)
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "backend")]
    os.chdir(root / "backend")
    import pytest

    return pytest.main(pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
