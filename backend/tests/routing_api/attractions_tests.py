"""Tests for the Tripadvisor Terra attraction source.

Covers the Terra migration contract:
* header-based auth (``X-API-Key``) and the Terra base URL,
* old-style category -> Terra enum mapping,
* radius clamped to Terra's 5-mile ceiling,
* the fixed stop-dict shape + rank derived from best-first result order,
* 404 when no location is found,
* a clearer 502 for an unauthorized key,
* the standing guarantee that a failed request never leaks the API key.
"""

import pytest
from fastapi import HTTPException
from requests.exceptions import RequestException

from app.routing import config
from app.routing.sources import attractions


class _FakeResponse:
    """Minimal stand-in for a ``requests.Response``."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _nearby_payload(entries):
    return {"data": entries, "pagination": {"page": 1, "size": 20}}


def _entry(location_id, name, lat, lon, *, url=None, formatted=None, rating=None):
    location = {
        "id": location_id,
        "names": [{"language": "en", "value": name, "primary": True}],
        "coordinates": {"latitude": lat, "longitude": lon},
    }
    if url is not None:
        location["urls"] = {"tripadvisor": {"main": url}}
    if formatted is not None:
        location["addresses"] = [{"language": "en", "formatted": formatted}]
    if rating is not None:
        location["traveler_ratings"] = {"overall": {"rating": rating}}
    return {"location": location, "distance_miles": 0.5, "bearing": 10.0}


@pytest.mark.asyncio
async def test_find_stop_uses_header_auth_and_terra_url(monkeypatch):
    """Terra uses the ``X-API-Key`` header (not a ``key`` query param) against the
    Terra base URL. The key must never appear in the query string."""
    captured = {}
    monkeypatch.setattr(config, "TRIPADVISOR_API", "test-uuid-key")

    def _capture(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse(
            _nearby_payload(
                [_entry(1, "Museum", 39.5, -108.0, url="http://x", formatted="Main St")]
            )
        )

    monkeypatch.setattr(attractions.requests, "get", _capture)

    await attractions.find_stop("attractions", "39.5", "-108.0", 5)

    assert captured["url"].startswith(config.TRIPADVISOR_BASE_URL)
    assert captured["url"].endswith("/locations/nearby")
    assert captured["headers"][config.TRIPADVISOR_API_KEY_HEADER] == "test-uuid-key"
    assert "key" not in captured["params"]  # no query-param key on Terra


@pytest.mark.asyncio
async def test_find_stop_maps_category_and_clamps_radius(monkeypatch):
    """Old-style ``attractions`` maps to Terra's ``ATTRACTION`` enum, and a radius
    over Terra's 5-mile ceiling is clamped rather than sent (Terra 400s past 5)."""
    captured = {}

    def _capture(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(_nearby_payload([_entry(1, "Museum", 39.5, -108.0)]))

    monkeypatch.setattr(attractions.requests, "get", _capture)

    await attractions.find_stop("attractions", "39.5", "-108.0", 30)

    assert captured["params"]["category"] == "ATTRACTION"
    assert captured["params"]["radius"] == config.TRIPADVISOR_MAX_RADIUS_MI
    assert captured["params"]["unit"] == "MI"


@pytest.mark.asyncio
async def test_find_stop_returns_contract_shape_and_best_first_rank(monkeypatch):
    """The returned stop dict keeps the fixed contract, and rank is derived from
    best-first result order (1 = best) since Terra has no ranking integer."""

    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(
            _nearby_payload(
                [
                    _entry(
                        10,
                        "Top Attraction",
                        39.5,
                        -108.0,
                        url="https://ta/main",
                        formatted="1 Main St, Town",
                        rating=5.0,
                    ),
                    _entry(11, "Second", 39.6, -108.1, rating=4.0),
                ]
            )
        )

    monkeypatch.setattr(attractions.requests, "get", _fake_get)

    stop = await attractions.find_stop("attractions", "39.5", "-108.0", 5)

    assert stop["name"] == "Top Attraction"
    assert stop["type"] == "stop"
    assert stop["coordinates"] == [39.5, -108.0]
    assert stop["url"] == "https://ta/main"
    assert stop["address"] == "1 Main St, Town"
    assert stop["rank"] == 1  # first (best-rated) result


@pytest.mark.asyncio
async def test_find_stop_skips_entries_without_coordinates(monkeypatch):
    """Entries missing coordinates are skipped for selection, but ``rank`` counts
    every location-bearing entry (including coordinate-less ones) by position.

    So with a coordinate-less entry first, the usable second entry is returned
    with rank 2 — matching find_stop, which increments rank before checking
    coordinates."""

    def _fake_get(url, params=None, headers=None, timeout=None):
        entry_no_coords = {"location": {"id": 1, "names": [{"value": "No Coords"}]}}
        return _FakeResponse(
            _nearby_payload([entry_no_coords, _entry(2, "Has Coords", 40.0, -105.0)])
        )

    monkeypatch.setattr(attractions.requests, "get", _fake_get)

    stop = await attractions.find_stop("attractions", "40.0", "-105.0", 5)

    assert stop["name"] == "Has Coords"
    assert stop["coordinates"] == [40.0, -105.0]
    assert stop["rank"] == 2  # rank counts the skipped no-coords entry ahead of it


@pytest.mark.asyncio
async def test_find_stop_no_results_raises_404(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(_nearby_payload([]))

    monkeypatch.setattr(attractions.requests, "get", _fake_get)

    with pytest.raises(HTTPException) as exc_info:
        await attractions.find_stop("attractions", "0.0", "0.0", 5)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_find_stop_unauthorized_key_raises_clear_502(monkeypatch):
    """A dead/unauthorized key (401/403) surfaces a clearer message than the
    generic parse failure — this was the true root cause of the original 502."""

    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(
            {"status": 403, "title": "Forbidden", "detail": "explicit deny"},
            status_code=403,
        )

    monkeypatch.setattr(attractions.requests, "get", _fake_get)

    with pytest.raises(HTTPException) as exc_info:
        await attractions.find_stop("attractions", "39.5", "-108.0", 5)

    assert exc_info.value.status_code == 502
    assert "unauthorized" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_find_stop_request_failure_does_not_leak_secret(monkeypatch):
    """A RequestException whose message embeds the API key must not surface that
    secret in the client-facing response detail."""
    secret = "super-secret-terra-key"
    monkeypatch.setattr(attractions.config, "TRIPADVISOR_API", secret)

    def _boom(*args, **kwargs):
        raise RequestException(
            "HTTPSConnectionPool: failed for "
            "https://terra.tripadvisor.com/api/locations/nearby with X-API-Key=" + secret
        )

    monkeypatch.setattr(attractions.requests, "get", _boom)

    with pytest.raises(HTTPException) as exc_info:
        await attractions.find_stop("attractions", "33.0", "-117.0", 5)

    assert exc_info.value.status_code == 502
    assert secret not in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_details_returns_rank_and_stop(monkeypatch):
    """Direct by-id details returns (rank, stop). Rank comes from ``rankings`` when
    present, else a neutral fallback; the stop keeps the fixed contract shape."""

    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(
            {
                "id": 42,
                "names": [{"value": "Ranked Place", "primary": True}],
                "coordinates": {"latitude": 41.0, "longitude": -105.0},
                "urls": {"tripadvisor": {"main": "https://ta/42"}},
                "addresses": [{"formatted": "42 Rank Rd"}],
                "rankings": [{"rank": 3, "total": 100}],
            }
        )

    monkeypatch.setattr(attractions.requests, "get", _fake_get)

    rank, stop = await attractions.get_details("42")

    assert rank == 3
    assert stop["name"] == "Ranked Place"
    assert stop["type"] == "stop"
    assert stop["coordinates"] == [41.0, -105.0]
    assert stop["rank"] == 3


if __name__ == "__main__":
    pytest.main()
