"""Tests for the TripAdvisor attraction source.

Focus: a failed upstream request must not leak the TripAdvisor API key (carried
in the request URL/params) to the client-facing HTTPException.detail.
"""

import pytest
from fastapi import HTTPException
from requests.exceptions import RequestException

from app.routing.sources import attractions


@pytest.mark.asyncio
async def test_find_stop_latlong_uses_single_literal_comma(monkeypatch):
    """``latLong`` must be a literal ``lat,lon`` so ``requests`` encodes the comma
    once. Pre-encoding it as ``%2C`` here caused a double-encode (``%252C``) that
    TripAdvisor rejects, surfacing downstream as a 502 "Improper TripAdvisor
    response" and breaking route planning."""
    captured = {}

    def _capture(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        # Short-circuit before any real network / JSON parsing happens.
        raise RequestException("stop here")

    monkeypatch.setattr(attractions.requests, "get", _capture)

    with pytest.raises(HTTPException):
        await attractions.find_stop("attractions", "39.5", "-108.0", 25)

    latlong = captured["params"]["latLong"]
    assert latlong == "39.5,-108.0"
    assert "%2C" not in latlong  # no manual pre-encoding


@pytest.mark.asyncio
async def test_find_stop_request_failure_does_not_leak_secret(monkeypatch):
    """A RequestException whose message embeds the API-key-bearing URL must not
    surface that secret in the response detail."""
    secret = "super-secret-tripadvisor-key"
    monkeypatch.setattr(attractions.config, "TRIPADVISOR_API", secret)

    def _boom(*args, **kwargs):
        # Mimic requests surfacing the full URL (with the key) in the error text.
        raise RequestException(
            "HTTPSConnectionPool: failed for "
            "https://api.content.tripadvisor.com/...?key=" + secret
        )

    monkeypatch.setattr(attractions.requests, "get", _boom)

    with pytest.raises(HTTPException) as exc_info:
        await attractions.find_stop("attractions", "33.0", "-117.0", 30)

    assert exc_info.value.status_code == 502
    assert secret not in str(exc_info.value.detail)


if __name__ == "__main__":
    pytest.main()
