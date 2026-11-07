"""Explicit edits tested with frozen catalog, timezone and road adapters."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.route_edit import RouteEditRequest
from app.models.routing_models.routing_models import Mapbox_geo
from app.routers import routing_api
from app.routing.base import PlanningError
from app.routing.route_edit import preview_route_edit
from app.utils.auth import require_authenticated_user


def facts(pid, coords):
    return {
        "provider_id": pid,
        "name": f"Verified {pid}",
        "coordinates": coords,
        "source": "boulder-osmp",
        "categories": ["daytime"],
        "source_provenance": [],
        "source_attribution": "Frozen source credit",
    }


def saved_route():
    return {
        "coordinates": [[40, -105], [40.1, -105], [40.2, -105]],
        "distance": 20000,
        "duration": 1200,
        "cost": 0,
        "steps": [],
        "geometry": {"type": "LineString", "coordinates": [[-105, 40], [-105, 40.2]]},
        "stops": [
            {**facts("boulder:existing", [40.1, -105]), "type": "stop", "duration": 600},
            {"name": "Destination", "coordinates": [40.2, -105], "type": "end", "duration": 600},
        ],
        "departure_time": "2030-06-01T09:00:00+00:00",
        "start_timezone": "UTC",
        "scheduling_policy": {},
    }


def request(**changes):
    return RouteEditRequest.model_validate(
        {
            "route": saved_route(),
            "provider_id": "boulder:new",
            "action": "add",
            "stop_index": 1,
            **changes,
        }
    )


def catalog(ids):
    rows = {
        "boulder:existing": facts("boulder:existing", [40.1, -105]),
        "boulder:new": facts("boulder:new", [40.15, -105.1]),
    }
    return {key: deepcopy(rows[key]) for key in ids if key in rows}


def road(count, duration=600):
    return SimpleNamespace(
        legs=[SimpleNamespace(duration=duration, distance=1000) for _ in range(count)],
        distance=1000 * count,
        duration=duration * count,
        geometry=Mapbox_geo(type="LineString", coordinates=[[-105, 40], [-105, 40.2]]),
    )


async def run(payload, *, duration=600, lookup=catalog, response=None):
    call = AsyncMock(
        return_value=response
        or road(len(payload.route.stops) + (payload.action == "add"), duration)
    )
    result = await preview_route_edit(
        payload, route_call=call, timezone_at=AsyncMock(return_value="UTC"), catalog_lookup=lookup
    )
    return result, call


@pytest.mark.asyncio
async def test_add_recalculates_actual_legs_and_preserves_original():
    payload = request(include_meal_slots=True)
    original = payload.model_dump()
    result, call = await run(payload)
    assert payload.model_dump() == original
    assert [s["name"] for s in result.route.stops] == [
        "Verified boulder:existing",
        "Verified boulder:new",
        "Destination",
    ]
    assert result.route.coordinates == [[40, -105], [40.1, -105], [40.15, -105.1], [40.2, -105]]
    assert result.route.distance == 3000 and result.route.duration == 1800
    selected = result.route.stops[1]
    assert selected["visit_duration"]["source"] == "conservative_fallback"
    assert selected["visit_duration"]["reason"] == "missing_estimate"
    assert selected["visit_duration"]["seconds"] == 7200
    assert selected["arrival_time"] == "2030-06-01T11:20:00+00:00"
    assert selected["source_attribution"] == "Frozen source credit"
    assert any(s.kind == "meal" for day in result.itinerary for s in day.stops)
    call.assert_awaited_once_with(40, -105, 40.2, -105, "-105,40.1;-105.1,40.15")


@pytest.mark.asyncio
async def test_replace_keeps_destination_and_defaults_to_no_meals():
    result, _ = await run(request(action="replace", stop_index=0))
    assert [s.get("provider_id") for s in result.route.stops] == ["boulder:new", None]
    assert not any(s.kind == "meal" for day in result.itinerary for s in day.stops)


def with_hotel(day="2030-06-01"):
    saved = saved_route()
    hotel = {
        "name": "Booked hotel",
        "type": "hotel",
        "coordinates": [40.16, -105],
        "duration": 60,
        "check_in_date": day,
        "price": 125,
        "evening_suggestions": [{"name": "Stale suggestion"}],
    }
    saved["stops"].insert(1, hotel)
    saved["coordinates"].insert(2, hotel["coordinates"])
    return saved


@pytest.mark.asyncio
async def test_hotel_dates_quotes_retained_but_evenings_cleared():
    result, _ = await run(request(route=with_hotel()))
    hotel = result.route.stops[2]
    assert hotel["price"] == 125 and hotel["check_in_date"] == "2030-06-01"
    assert hotel["evening_suggestions"] == []
    assert not any(s.kind == "evening" for day in result.itinerary for s in day.stops)


@pytest.mark.parametrize(
    "change,match",
    [
        ({"stop_index": 4}, "current itinerary stop"),
        ({"action": "replace", "stop_index": 1}, "Only attraction"),
        ({"provider_id": "boulder:existing"}, "already in the trip"),
        ({"provider_id": "google:unknown"}, "current catalog"),
        ({"provider_id": "boulder:missing"}, "no longer available"),
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_edits_before_mapbox(change, match):
    call = AsyncMock()
    with pytest.raises(PlanningError, match=match):
        await preview_route_edit(
            request(**change), route_call=call, timezone_at=AsyncMock(), catalog_lookup=catalog
        )
    call.assert_not_awaited()


@pytest.mark.parametrize(
    "field,value",
    [
        ("departure_time", None),
        ("departure_time", "2020-01-01T09:00:00Z"),
        ("departure_time", "2030-01-01T09:00:00"),
        ("scheduling_policy", None),
    ],
)
@pytest.mark.asyncio
async def test_legacy_and_past_departures_need_replan(field, value):
    saved = saved_route()
    saved[field] = value
    with pytest.raises(PlanningError):
        await run(request(route=saved))


@pytest.mark.asyncio
async def test_current_access_hold_and_changed_existing_coordinates_reject():
    def held(ids):
        return {
            "boulder:new": {
                **facts("boulder:new", [40.15, -105.1]),
                "source_provenance": [{"source_visit_calendar": {}}],
            }
        }

    with pytest.raises(PlanningError, match="itinerary-ready"):
        await run(request(), lookup=held)

    def changed(ids):
        values = catalog(ids)
        if "boulder:existing" in values:
            values["boulder:existing"]["coordinates"] = [41, -105]
        return values

    with pytest.raises(PlanningError, match="coordinates changed"):
        await run(request(), lookup=changed)


@pytest.mark.asyncio
async def test_actual_road_cutoff_and_hotel_day_conflict_reject():
    with pytest.raises(PlanningError, match="daily driving window"):
        await run(request(), duration=5 * 3600)
    with pytest.raises(PlanningError, match="dated hotel stay"):
        await run(request(route=with_hotel("2030-06-02")))


@pytest.mark.asyncio
async def test_provider_leg_and_geometry_validation():
    with pytest.raises(PlanningError, match="incomplete"):
        await run(request(), response=road(1))
    malformed = road(3)
    malformed.geometry.coordinates = [[900, 0], [0, 0]]
    with pytest.raises(PlanningError, match="invalid edited route geometry"):
        await run(request(), response=malformed)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(coordinates=[[float("inf"), 0], [40.1, -105], [40.2, -105]]),
        lambda r: r["stops"][0].update(coordinates=[91, 0]),
        lambda r: r["stops"][0].update(type="generic"),
        lambda r: r["stops"][-1].update(type="stop"),
        lambda r: r.update(stops=r["stops"] * 25),
        lambda r: r["geometry"].update(coordinates=[[0, 0]] * 100001),
    ],
)
def test_bounded_payload(mutation):
    saved = saved_route()
    mutation(saved)
    with pytest.raises(ValidationError):
        request(route=saved)


def test_http_authentication_validation_and_safe_error(monkeypatch):
    app = FastAPI()
    app.include_router(routing_api.router)
    client = TestClient(app)
    assert client.post("/route-edit", json=request().model_dump(mode="json")).status_code == 401
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture"
    assert client.post("/route-edit", json={}).status_code == 422
    monkeypatch.setattr(routing_api, "_build_services", lambda: SimpleNamespace(timezone_at=None))
    monkeypatch.setattr(
        routing_api,
        "preview_route_edit",
        AsyncMock(side_effect=PlanningError("Choose another place", 422)),
    )
    response = client.post("/route-edit", json=request().model_dump(mode="json"))
    assert response.status_code == 422 and response.json()["detail"] == "Choose another place"
