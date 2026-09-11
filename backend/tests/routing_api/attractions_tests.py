"""Tests for the TripAdvisor attraction source.

Focus: a failed upstream request must not leak the TripAdvisor API key (carried
in the request URL/params) to the client-facing HTTPException.detail.
"""

import pytest
from fastapi import HTTPException
from requests.exceptions import RequestException

from app.routing.sources import attractions


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
