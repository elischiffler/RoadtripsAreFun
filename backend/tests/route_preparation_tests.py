"""Bounded read-only preparation: real admission/projection, offline source seams."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.progress import reporting
from app.catalog.release_holds import SOURCE_IDS
from app.models.route_preparation import RoutePreparationRequest
from app.routers import route_preparation as api
from app.routing import route_preparation as prep
from app.utils.auth import require_authenticated_user
from tests.routing_api.guided_flow_tests import _place


def rhythm(drive_start=9, drive_end=20, sleep_start=22, sleep_end=7):
    slots = ["rest"] * 24
    for kind, start, end in [("drive", drive_start, drive_end), ("sleep", sleep_start, sleep_end)]:
        hour = start
        while hour != end:
            slots[hour] = kind
            hour = (hour + 1) % 24
    return {"daily_schedule": {"slots": slots, "timezone": "route_local"}}


def payload(**changes):
    return RoutePreparationRequest(
        **(
            {
                "geometry": [[-105, 40], [-85, 40]],
                "driving_seconds": 20 * 3600,
                "departure_clock": "09:00",
                "scheduling_policy": rhythm(),
            }
            | changes
        )
    )


def test_hints_use_road_meals_and_driving_windows_without_claiming_eligibility():
    areas = prep.estimate_stay_areas(payload())
    assert len(areas) == 2  # 11h driving block minus lunch+dinner allowances.
    assert areas[0].driving_seconds_before == 9.25 * 3600
    assert areas[0].meal_allowance_seconds == 105 * 60
    assert areas[0].pause_clock == "20:00"
    assert 0 < areas[0].route_fraction < areas[1].route_fraction < 1
    assert areas[0].clock_basis == "departure_wall_clock_estimate"
    assert areas[0].tentative and not areas[0].availability_checked
    assert not areas[0].hotel_quotes_checked and "local clock" in areas[0].notice
    assert prep.estimate_stay_areas(payload(driving_seconds=3600)) == []


def test_wrapped_night_drive_uses_central_wake_relative_meal_policy():
    areas = prep.estimate_stay_areas(
        payload(departure_clock="18:00", scheduling_policy=rhythm(18, 6, 8, 16))
    )
    assert areas[0].pause_clock == "06:00" and areas[0].day_index == 1
    assert areas[0].driving_seconds_before == 10.25 * 3600
    assert areas[0].meal_allowance_seconds == 105 * 60
    assert (
        prep.estimate_stay_areas(
            payload(departure_clock="10:00", scheduling_policy=rhythm(18, 6, 8, 16))
        )
        == []
    )


def test_daytime_drive_end_legacy_bounds_zero_route_and_bounded_areas():
    assert (
        prep.estimate_stay_areas(
            payload(scheduling_policy=rhythm(7, 15, 20, 4), departure_clock="07:00")
        )[0].pause_clock
        == "15:00"
    )
    assert prep.estimate_stay_areas(payload(scheduling_policy={}))
    assert prep.estimate_stay_areas(payload(scheduling_policy={}, departure_clock="05:00"))
    assert prep.estimate_stay_areas(payload(geometry=[[0, 0], [0, 0]])) == []
    assert len(prep.estimate_stay_areas(payload(driving_seconds=63 * 86400))) == 3


def test_dateline_interpolation_follows_road_distance_not_vertex_index():
    areas = prep.estimate_stay_areas(payload(geometry=[[179, 0], [-179, 0], [-169, 0]]))
    assert -180 <= areas[0].coordinates[1] <= 180
    assert areas[0].coordinates[1] == pytest.approx(179 + 12 * areas[0].route_fraction - 360)


@pytest.mark.parametrize(
    "change",
    [
        {"departure_clock": "24:00"},
        {"driving_seconds": float("nan")},
        {"driving_seconds": True},
        {"geometry": [[181, 0], [0, 0]]},
    ],
)
def test_invalid_or_unbounded_request_is_rejected(change):
    with pytest.raises(ValidationError):
        payload(**change)


def test_preview_projection_is_bounded_and_excludes_private_fields():
    stops = [
        {
            "name": str(i),
            "coordinates": [0, 0],
            "provider_id": str(i),
            "persona_weights": {"food": 1},
            "source_provenance": ["secret"],
        }
        for i in range(30)
    ]
    scene = prep.preview_details("considering", {"coordinates": [[0, 0]] * 10005}, stops)
    assert len(scene["stops"]) == 12 and len(scene["geometry"]["coordinates"]) == 10000
    assert scene["stops"][0]["name"] == "0" and scene["stops"][-1]["name"] == "29"
    assert "persona_weights" not in str(scene) and "secret" not in str(scene)
    assert (
        prep.preview_details("selected", {"coordinates": [[0, 0], [float("nan"), 0]]}, stops)[
            "geometry"
        ]
        is None
    )


@pytest.mark.asyncio
async def test_progressive_source_reads_are_bounded_admitted_and_partial_failures_safe(monkeypatch):
    calls, events = [], []

    def source(point, kinds, **kwargs):
        calls.append((point, kinds, kwargs))
        if len(calls) == 3:
            raise RuntimeError("PRIVATE CONNECTION STRING")
        base = _place(f"fixture:{len(calls)}", coordinates=point)
        held = deepcopy(base) | {"provider_id": sorted(SOURCE_IDS)[0]}
        return [held, base, base, _place("far", coordinates=[0, 0])]

    monkeypatch.setattr(prep.alternatives, "catalog_nearby", source)
    with reporting(events.append):
        result = await prep.prepare_route(payload())
    assert len(calls) == 6 and result.sections_failed == 1
    assert all(
        c[2] == {"radius_miles": 5, "limit": 12, "require_visit_calendar": True} for c in calls
    )
    assert result.catalog_status == "partial"
    assert len(result.places) == 5 and not (SOURCE_IDS & {p.id for p in result.places})
    assert events[0]["stage"] == "preparation.areas"
    assert [e["sections_checked"] for e in events if e["stage"] == "preparation.catalog"] == list(
        range(1, 7)
    )
    assert "PRIVATE" not in str(events) + result.model_dump_json()


@pytest.mark.asyncio
async def test_cancellation_stops_remaining_sections_at_async_boundary(monkeypatch):
    entered = asyncio.Event()

    async def lookup(*args, **kwargs):
        entered.set()
        await asyncio.Future()

    monkeypatch.setattr(prep, "threaded", lookup)
    task = asyncio.create_task(prep.prepare_route(payload()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_account_guard_precedes_read_and_authenticated_stream_returns_real_progress(monkeypatch):
    calls = []
    monkeypatch.setattr(prep.alternatives, "catalog_nearby", lambda *a, **kw: calls.append(a) or [])
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    assert (
        client.post("/route-preparation/stream", json=payload().model_dump(mode="json")).status_code
        == 401
    )
    assert calls == []
    app.dependency_overrides[require_authenticated_user] = lambda: "signed-fixture-owner"
    response = client.post("/route-preparation/stream", json=payload().model_dump(mode="json"))
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.headers["cache-control"] == "no-store"
    assert events[-1]["type"] == "result" and len(calls) == 6
    assert events[-1]["response"]["catalog_status"] == "ready"
