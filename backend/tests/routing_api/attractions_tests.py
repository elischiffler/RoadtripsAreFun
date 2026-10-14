"""Legacy planner contract now reads catalog; no Tripadvisor transport exists."""

import pytest
from fastapi import HTTPException

from app.routing.sources import attractions


@pytest.mark.asyncio
async def test_find_stop_uses_catalog_bounds_and_attribution(monkeypatch):
    def nearby(point, categories, **kwargs):
        assert point == [40, -74] and categories == ["daytime"]
        assert kwargs == {"radius_miles": 5, "limit": 1}
        return [
            {
                "name": "Museum",
                "coordinates": point,
                "provider_id": "overture:1",
                "source_release": "release",
                "source_attribution": "contributors",
            }
        ]

    monkeypatch.setattr(attractions.repository, "nearby", nearby)
    stop = await attractions.find_stop("attractions", "40", "-74", 30)
    assert stop["type"] == "stop" and stop["rank"] == 1
    assert stop["source_attribution"] == "contributors"


@pytest.mark.asyncio
async def test_find_stop_empty_catalog(monkeypatch):
    monkeypatch.setattr(attractions.repository, "nearby", lambda *args, **kwargs: [])
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", "40", "-74", 5)
    assert raised.value.status_code == 404


@pytest.mark.asyncio
async def test_find_stop_safe_database_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("secret")

    monkeypatch.setattr(attractions.repository, "nearby", fail)
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", "40", "-74", 5)
    assert raised.value.status_code == 503
    assert "secret" not in raised.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("radius", [0, -1, float("nan"), float("inf")])
async def test_find_stop_invalid_radius(radius):
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", "40", "-74", radius)
    assert raised.value.status_code == 400


def test_no_tripadvisor_network_implementation():
    from pathlib import Path

    root = Path(attractions.__file__).parents[2]
    for relative in [
        "routing/sources/attractions.py",
        "routing/sources/persona_candidates.py",
        "routing/sources/evenings.py",
    ]:
        source = (root / relative).read_text()
        assert "terra.tripadvisor.com" not in source
        assert "terra_requests" not in source
        assert "TRIPADVISOR_API" not in source


@pytest.mark.asyncio
async def test_all_catalog_discovery_adapters_make_zero_http_calls(monkeypatch):
    from datetime import UTC, datetime

    import httpx
    import requests

    from app.routing.sources import evenings, persona_candidates

    def unexpected(*args, **kwargs):
        raise AssertionError("Catalog discovery must not perform HTTP requests")

    monkeypatch.setattr(httpx.AsyncClient, "request", unexpected)
    monkeypatch.setattr(httpx.Client, "request", unexpected)
    monkeypatch.setattr(requests, "get", unexpected)
    monkeypatch.setattr(attractions.repository, "nearby", lambda *args, **kwargs: [])
    assert await persona_candidates.LivePlaceProvider().attractions_near([40, -74]) == []
    assert await evenings.LiveEveningProvider().nearby([40, -74], ["food"], datetime.now(UTC)) == []
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", "40", "-74", 5)
    assert raised.value.status_code == 404
