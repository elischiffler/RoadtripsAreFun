"""Pinned row exceptions accept recomputed meal metadata, never changed source facts."""

from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.catalog import admission, release_holds
from app.catalog import hold_resolution as h
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers.itinerary_api import build_itinerary
from app.routing.meal_reservations import MealClock
from app.routing.travel_timing import apply_timing
from tests.catalog_routing_hold_resolution_tests import row_for, runtime


def meal_breaks():
    start = datetime(2030, 6, 1, 9, tzinfo=ZoneInfo("Etc/UTC"))
    clock = MealClock(start, start.replace(hour=20))
    clock.drive(start, 10 * 3600, start.tzinfo)
    assert len(clock.breaks) == 2
    return deepcopy(clock.breaks)


@pytest.mark.parametrize("index", range(170))
def test_all_pinned_versions_keep_exact_resolution_with_real_or_empty_meal_annotations(index):
    item = h.RESOLUTIONS[index]
    value = runtime(row_for(item))
    held = item["resolved_held_ids"]
    original = deepcopy(value)
    for breaks in ([], meal_breaks()):
        value["meal_breaks"] = breaks
        assert h.resolved(value, held)
        assert not release_holds.blocked(value)
        assert {key: content for key, content in value.items() if key != "meal_breaks"} == original
    contract = next(
        f["catalog_admission"] for f in value["source_provenance"] if "catalog_admission" in f
    )
    assert admission.routing_eligible(value, now_epoch=contract["reviewed_at_epoch"] + 1) == (
        contract["tier"] == "T3"
    )
    assert not admission.routing_eligible(value, now_epoch=contract["expires_at_epoch"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rows: rows[0].update(source="unreviewed source override"),
        lambda rows: rows[0].pop("notice"),
        lambda rows: rows[0].update(kind="arrival"),
        lambda rows: rows[0].update(status="open"),
        lambda rows: rows[0].update(optional=True),
        lambda rows: rows[0].update(meal_type="snack"),
        lambda rows: rows[0].update(name="Source says free parking"),
        lambda rows: rows[0].update(duration_seconds=True),
        lambda rows: rows[0].update(duration_seconds=0),
        lambda rows: rows[0].update(timezone=None),
        lambda rows: rows[0].update(timezone="Unknown/Zone"),
        lambda rows: rows[0].update(timezone="America/Los_Angeles"),
        lambda rows: rows[0].update(arrival_time="2030-06-01T13:15:00"),
        lambda rows: rows[0].update(departure_time="2030-06-01T14:01:00+00:00"),
        lambda rows: rows[0].update(window_start="2030-06-01T11:00:00+00:00"),
        lambda rows: rows[0].update(window_end="2030-06-02T14:00:00+00:00"),
        lambda rows: rows[0].update(id="meal:2030-06-02:lunch"),
        lambda rows: rows[0].update(notice="x" * 1001),
        lambda rows: rows.append(deepcopy(rows[0])),
        lambda rows: rows.reverse(),
    ],
)
def test_malformed_or_unrecognized_meal_annotations_fail_closed(mutation):
    item = h.RESOLUTIONS[0]
    value = runtime(row_for(item))
    value["meal_breaks"] = meal_breaks()
    assert h.resolved(value, item["resolved_held_ids"])
    mutation(value["meal_breaks"])
    assert not h.resolved(value, item["resolved_held_ids"])
    assert release_holds.blocked(value)


@pytest.mark.parametrize("bad", [None, {}, "reserved", [None], [{}] * 190])
def test_nonlist_unbounded_or_missing_meal_metadata_cannot_resolve(bad):
    item = h.RESOLUTIONS[0]
    value = runtime(row_for(item)) | {"meal_breaks": bad}
    assert not h.resolved(value, item["resolved_held_ids"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(name="Changed source name"),
        lambda value: value.update(url="https://changed.example"),
        lambda value: value.update(coordinates=[0, 0]),
        lambda value: value.update(source_access="cleared"),
        lambda value: value["source_provenance"][0].update(unreviewed=True),
        lambda value: value["source_provenance"].pop(0),
    ],
)
def test_wellformed_meals_do_not_mask_source_or_unknown_field_tampering(mutation):
    item = h.RESOLUTIONS[0]
    value = runtime(row_for(item)) | {"meal_breaks": meal_breaks()}
    mutation(value)
    assert not h.resolved(value, item["resolved_held_ids"])
    assert release_holds.blocked(value)


@pytest.mark.asyncio
async def test_pinned_t3_actual_reserved_route_rebuild_rechecks_and_recomputes_meals(monkeypatch):
    item = next(
        e
        for e in h.RESOLUTIONS
        if any(
            f.get("catalog_admission", {}).get("tier") == "T3"
            for f in e["approved_payload"]["provenance"]
        )
    )
    row = row_for(item)
    facts = runtime(row)
    qualification = next(
        f for f in row["provenance"] if f.get("dataset") == "Roadtrips routing qualification"
    )
    contract = next(f["catalog_admission"] for f in row["provenance"] if "catalog_admission" in f)
    monkeypatch.setattr(admission.time, "time", lambda: contract["reviewed_at_epoch"] + 1)
    zone = ZoneInfo(qualification["timezone"])
    date = qualification["source_visit_calendar"]["date_overrides"][0]["date"]
    start = datetime.fromisoformat(date + "T09:00:00").replace(tzinfo=zone)
    stops = [
        deepcopy(facts) | {"type": "stop", "duration": 4 * 3600, "timezone": zone.key},
        {"name": "Destination", "type": "end", "duration": 3600, "timezone": zone.key},
    ]
    apply_timing(stops, start, SchedulingPolicy(), zone.key, reserve_meal_slots=True)
    assert stops[0]["meal_breaks"] and h.resolved(stops[0], item["resolved_held_ids"])
    expected = deepcopy(stops[0]["meal_breaks"])
    # A different but structurally valid interval is still untrusted presentation.
    for key, clock in [("arrival_time", "12:00:00"), ("departure_time", "12:45:00")]:
        value = start.replace(hour=int(clock[:2]), minute=int(clock[3:5]))
        stops[0]["meal_breaks"][0][key] = value.isoformat()
    assert h.resolved(stops[0], item["resolved_held_ids"])
    route = Route(
        coordinates=[],
        distance=1,
        duration=5 * 3600,
        steps=[],
        stops=stops,
        geometry={"coordinates": []},
        cost=0,
        departure_time=start,
        start_timezone=zone.key,
        scheduling_policy=SchedulingPolicy(),
        reserve_meal_slots=True,
    )

    def lookup(ids):
        return {row["source_id"]: deepcopy(facts)}

    payload = Itinerary_Payload(route=route, include_meal_slots=True)
    days = await build_itinerary(payload, catalog_lookup=lookup)
    meals = [stop for day in days for stop in day.stops if stop.kind == "meal"]
    assert len(meals) == 1 and meals[0].status == "reserved"
    assert route.stops[0]["meal_breaks"] == expected
    assert await build_itinerary(payload, catalog_lookup=lookup) == days
    assert h.resolved(route.stops[0], item["resolved_held_ids"])
    assert admission.routing_eligible(route.stops[0])
