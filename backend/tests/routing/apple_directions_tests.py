import asyncio

import httpx
import pytest

from app.routing.base import PlanningError
from app.routing.sources import apple


def _response(url, value, status=200, **headers):
    return httpx.Response(status, request=httpx.Request("GET", url), json=value, headers=headers)


def _route(origin, destination):
    start, end = (
        dict(zip(("latitude", "longitude"), map(float, point.split(",")), strict=True))
        for point in (origin, destination)
    )
    return {
        "routes": [{"distanceMeters": 100, "durationSeconds": 20, "stepIndexes": [0, 1]}],
        "steps": [
            {"stepPathIndex": 0, "durationSeconds": 20, "distanceMeters": 100},
            {"stepPathIndex": 1, "durationSeconds": 0, "distanceMeters": 0},
        ],
        "stepPaths": [[start, end], [end]],
    }


@pytest.fixture(autouse=True)
def reset_provider(monkeypatch):
    monkeypatch.setattr(apple, "_token", None)
    monkeypatch.setattr(apple, "_token_lock", asyncio.Lock())
    monkeypatch.setattr(apple, "_cooldown_until", 0)
    monkeypatch.setattr(apple, "_signing_token", lambda: "signed-credential")


async def test_apple_exchange_and_ordered_waypoints(monkeypatch):
    calls = []

    async def send(url, *, params, headers, timeout):
        calls.append((url, params, headers))
        if url.endswith("/token"):
            assert headers["Authorization"] == "Bearer signed-credential"
            return _response(url, {"accessToken": "apple-access-token", "expiresInSeconds": 300})
        assert headers["Authorization"] == "Bearer apple-access-token"
        assert params["transportType"] == "Automobile"
        return _response(url, _route(params["origin"], params["destination"]))

    monkeypatch.setattr(apple, "http_get", send)
    route = await apple.call_route(33, -117, 35, -119, "-118,34")
    assert route.directions_provider == "apple"
    assert (route.distance, route.duration) == (200, 40)
    assert route.geometry.coordinates == [[-117, 33], [-118, 34], [-119, 35]]
    assert [leg.duration for leg in route.legs] == [20, 20]
    assert sum(url.endswith("/token") for url, _, _ in calls) == 1
    assert len(calls) == 3
    assert {params["origin"] for _, params, _ in calls if params} == {"33.0,-117.0", "34.0,-118.0"}


async def test_apple_quota_blocks_following_calls_without_legacy_fallback(monkeypatch):
    requests = []

    async def send(url, **kwargs):
        requests.append(url)
        return _response(url, {}, 429, **{"Retry-After": "60"})

    monkeypatch.setattr(apple, "http_get", send)
    for _ in range(2):
        with pytest.raises(PlanningError, match="temporarily limited") as failure:
            await apple.call_route(33, -117, 34, -118)
        assert failure.value.status_code == 503

    assert requests == ["https://maps-api.apple.com/v1/token"]


def test_apple_parser_rejects_unrelated_or_bad_provider_geometry():
    value = _route("33,-117", "34,-118")
    value["stepPaths"][1] = [{"latitude": 34, "longitude": -119}]
    with pytest.raises(ValueError, match="Discontinuous"):
        apple._decode_leg(value)

    value = _route("33,-117", "34,-118")
    value["steps"][0]["stepPathIndex"] = -1
    with pytest.raises(ValueError, match="path index"):
        apple._decode_leg(value)
