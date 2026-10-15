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


@pytest.mark.asyncio
@pytest.mark.parametrize("lat,lon", [("nan", "0"), ("0", "inf"), ("91", "0"), ("0", "181")])
async def test_find_stop_invalid_coordinates_never_query_catalog(monkeypatch, lat, lon):
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid coordinates must not query the catalog")

    monkeypatch.setattr(attractions.repository, "nearby", unexpected)
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", lat, lon, 5)
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
@pytest.mark.parametrize("catalog_state", ["populated", "empty", "unavailable"])
async def test_all_catalog_discovery_adapters_make_zero_http_calls(monkeypatch, catalog_state):
    from datetime import UTC, datetime

    import httpx
    import requests

    from app.routing.sources import evenings, persona_candidates

    http_attempts = []

    def unexpected(*args, **kwargs):
        http_attempts.append(True)
        raise AssertionError("Catalog discovery must not perform HTTP requests")

    monkeypatch.setattr(httpx.AsyncClient, "request", unexpected)
    monkeypatch.setattr(httpx.AsyncClient, "send", unexpected)
    monkeypatch.setattr(httpx.Client, "request", unexpected)
    monkeypatch.setattr(httpx.Client, "send", unexpected)
    monkeypatch.setattr(requests.Session, "request", unexpected)
    record = {
        "provider_id": "nps:museum",
        "name": "Museum",
        "coordinates": [40, -74],
        "categories": ["daytime", "culture"],
        "source_attribution": "National Park Service",
        "source_release": "reviewed-release",
    }

    def nearby(*args, **kwargs):
        if catalog_state == "unavailable":
            raise RuntimeError("private connection details")
        return [record] if catalog_state == "populated" else []

    monkeypatch.setattr(attractions.repository, "nearby", nearby)
    daytime = persona_candidates.LivePlaceProvider()
    evening = evenings.LiveEveningProvider()
    arrival = datetime.now(UTC)
    if catalog_state == "unavailable":
        with pytest.raises(persona_candidates.CandidateProviderError, match="catalog lookup"):
            await daytime.attractions_near([40, -74])
        with pytest.raises(RuntimeError, match="catalog lookup"):
            await evening.nearby([40, -74], ["culture"], arrival)
    else:
        day_places = await daytime.attractions_near([40, -74])
        evening_places = await evening.nearby([40, -74], ["culture"], arrival)
        if catalog_state == "populated":
            for places in (day_places, evening_places):
                assert places[0].provider_id == record["provider_id"]
                assert places[0].source_attribution == record["source_attribution"]
                assert places[0].source_release == record["source_release"]
            stop = await attractions.find_stop("attractions", "40", "-74", 5)
            assert stop["provider_id"] == record["provider_id"]
            assert stop["source_attribution"] == record["source_attribution"]
            assert http_attempts == []
            return
        assert day_places == evening_places == []
    with pytest.raises(HTTPException) as raised:
        await attractions.find_stop("attractions", "40", "-74", 5)
    assert raised.value.status_code == (503 if catalog_state == "unavailable" else 404)
    assert "private connection" not in raised.value.detail
    assert http_attempts == []
