"""Hard source-calendar gates, authentic Burlington facts, and final road timing."""

import copy
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.agent.persona import AccountPersona
from app.catalog import repository
from app.catalog.market_visit_calendar import build
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route, Route_Payload
from app.models.scheduling_policy import SchedulingPolicy
from app.routers import routing_api
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanOptions
from app.routing.cp_sat_selection import select_attractions
from app.routing.discovery import DiscoveryResult
from app.routing.occupancy import HotelRoom
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.travel_timing import apply_timing
from app.routing.visit_calendar import (
    SCHEMA,
    VisitCalendarConflict,
    calendar_eligible,
    solve_visit,
    source_calendar,
)

ZONE = ZoneInfo("America/New_York")


def instant(value, zone=ZONE):
    return datetime.fromisoformat(value).replace(tzinfo=zone)


def calendar(**changes):
    return {
        "schema_version": SCHEMA,
        "weekly_windows": [{"weekdays": list(range(7)), "opens": "09:00", "closes": "17:00"}],
        "source_receipts": [
            {"source_url": "https://operator.example/hours", "literal": ["daily 9–5"]}
        ],
        **changes,
    }


def candidate(rules=None, provider_id="usda-market:fixture", **changes):
    return {
        "provider_id": provider_id,
        "name": provider_id,
        "coordinates": [44.46973, -73.215415],
        "address": "verified source address",
        "source_provenance": [{"source_visit_calendar": rules or calendar()}],
        "utility": 0.9,
        "route_progress_seconds": 0,
        "detour_seconds": 0,
        "type": "stop",
        "duration": 0,
        "timezone": ZONE.key,
        **changes,
    }


def current_fixture(monkeypatch, row):
    """Retained synthetic/current source facts, independently read on reuse."""
    monkeypatch.setattr(
        repository,
        "current_records",
        lambda ids: {
            row["provider_id"]: {
                key: copy.deepcopy(row[key]) for key in ["coordinates", "source_provenance"]
            }
        },
    )


@pytest.fixture
def burlington():
    path = (
        Path(__file__).resolve().parents[3]
        / "docs/data/catalog-expansion-kaggle-20261015/additions.preview.jsonl"
    )
    row = next(
        json.loads(line) for line in path.read_text().splitlines() if '"usda-market:301158"' in line
    )
    facts = row["provenance"][0]["published_access_facts"]
    rules = build(facts)
    return candidate(rules, "usda-market:301158", name=row["name"])


@pytest.mark.parametrize(
    "arrival,accepted",
    [
        ("2026-10-15T10:00", False),  # Thursday: independent review's failing trip.
        ("2026-10-17T16:00", False),  # Saturday after closing.
        ("2026-10-17T13:00", False),  # Open on arrival but full visit cannot fit.
        ("2026-10-17T12:00", True),  # Exact closing boundary for full two hours.
        ("2026-10-17T10:00", True),
        ("2026-11-07T10:00", False),
        ("2026-05-16T10:00", False),  # Native June start restricts operator May start.
    ],
)
def test_authentic_burlington_full_dwell(burlington, arrival, accepted):
    start = instant(arrival)
    deadline = start.replace(hour=20)
    if not accepted:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(burlington, start, deadline)
        return
    chosen, proof = solve_visit(burlington, start, deadline)
    assert chosen == start
    assert proof["status"] == "within_published_window"
    assert proof["ticket_availability"] == "unknown"
    assert proof["dwell_source"] == "planner_policy"
    assert any(
        r["source_url"] == "https://burlingtonfarmersmarket.org/" for r in proof["source_receipts"]
    )


def test_waiting_is_hard_bounded_and_recomputed_on_actual_legs(burlington):
    start = instant("2026-10-17T08:00")
    apply_timing([burlington], start, SchedulingPolicy(), ZONE.key)
    assert burlington["road_arrival_time"].startswith("2026-10-17T08:00")
    assert burlington["arrival_time"].startswith("2026-10-17T09:00")
    assert burlington["departure_time"].startswith("2026-10-17T11:00")
    assert burlington["wait_seconds"] == 3600
    burlington["duration"] = 6 * 3600
    with pytest.raises(VisitCalendarConflict):
        apply_timing([burlington], start, SchedulingPolicy(), ZONE.key)


@pytest.mark.parametrize(
    "rules",
    [
        {"schema_version": SCHEMA},
        calendar(unknown_reasons=["dated exceptions unavailable"]),
        calendar(weekly_windows=[]),
        calendar(schema_version="unknown"),
        calendar(weekly_windows=[{"weekdays": [7], "opens": "09:00", "closes": "17:00"}]),
        calendar(seasons=[{"kind": "annual", "start": "15-01", "end": "12-31"}]),
    ],
)
def test_unknown_or_malformed_calendars_excluded_before_selection(rules):
    row = candidate(rules)
    assert not calendar_eligible(row)
    assert select_attractions([row], [], 1, 3600) == []


def test_missing_schedule_not_verified_open_and_untimed_legacy_explicit_unknown():
    row = candidate(source_provenance=[])
    assert not calendar_eligible(row)
    ordinary = {**row, "provider_id": "legacy:outdoor", "categories": ["daytime", "nature"]}
    assert calendar_eligible(ordinary)
    _, proof = solve_visit(ordinary, instant("2026-10-17T10:00"), instant("2026-10-17T20:00"))
    assert proof == {"status": "unknown", "ticket_availability": "unknown"}
    assert not calendar_eligible({**ordinary, "categories": ["daytime", "culture"]})


@pytest.mark.parametrize(
    "day,accepted", [("2026-12-24", True), ("2026-12-25", False), ("2026-12-26", True)]
)
def test_annual_wraparound_season_and_explicit_christmas_closure(day, accepted):
    row = candidate(
        calendar(
            seasons=[{"kind": "annual", "start": "12-26", "end": "12-24"}],
            annual_closures=["12-25"],
        )
    )
    start, end = instant(day + "T10:00"), instant(day + "T20:00")
    if accepted:
        solve_visit(row, start, end)
    else:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(row, start, end)


def test_dated_override_replaces_weekly_and_closure_vetoes():
    row = candidate(
        calendar(
            date_overrides=[
                {"date": "2026-10-17", "windows": []},
                {"date": "2026-10-18", "windows": [{"opens": "14:00", "closes": "17:00"}]},
            ]
        )
    )
    with pytest.raises(VisitCalendarConflict):
        solve_visit(row, instant("2026-10-17T10:00"), instant("2026-10-17T20:00"))
    chosen, _ = solve_visit(row, instant("2026-10-18T10:00"), instant("2026-10-18T20:00"))
    assert chosen.hour == 14


def test_verified_fixed_event_start_is_hard_and_does_not_imply_booking():
    row = candidate(calendar(fixed_starts=["2026-10-17T13:30:00-04:00"]))
    chosen, proof = solve_visit(row, instant("2026-10-17T10:00"), instant("2026-10-17T20:00"))
    assert chosen.hour == 13 and chosen.minute == 30
    assert proof["ticket_availability"] == "unknown"
    with pytest.raises(VisitCalendarConflict):
        solve_visit(row, instant("2026-10-17T14:00"), instant("2026-10-17T20:00"))
    chosen, _ = solve_visit(row, instant("2026-10-17T10:00:00.500"), instant("2026-10-17T20:00"))
    assert chosen.isoformat() == "2026-10-17T13:30:00-04:00"


def test_fixed_start_only_full_dwell_cannot_cross_closure_or_season_boundary():
    rules = calendar(
        weekly_windows=[], fixed_starts=["2026-12-24T23:00:00-05:00"], annual_closures=["12-25"]
    )
    start, deadline = instant("2026-12-24T22:00"), instant("2026-12-25T03:00")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), start, deadline)
    rules["annual_closures"] = []
    rules["seasons"] = [{"kind": "dated", "start": "2026-12-01", "end": "2026-12-24"}]
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), start, deadline)
    rules["seasons"] = []
    # A start alone still supplies no verified end for the full policy dwell.
    assert not calendar_eligible(candidate(rules))
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), start, deadline)


def test_overnight_window_and_next_day_explicit_closure():
    rules = calendar(
        weekly_windows=[{"weekdays": [4], "opens": "23:00", "closes": "03:00", "end_day_offset": 1}]
    )
    start, deadline = instant("2026-10-17T00:00"), instant("2026-10-17T04:00")
    chosen, _ = solve_visit(candidate(rules), start, deadline)
    assert chosen == start
    rules["date_overrides"] = [{"date": "2026-10-17", "windows": []}]
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), start, deadline)
    rules["date_overrides"] = [
        {"date": "2026-10-17", "windows": [{"opens": "01:00", "closes": "02:00"}]}
    ]
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), start, deadline)


def test_actual_local_date_after_timezone_change_and_hotel_restart(burlington):
    # Departure is Friday in California; road arrival is Saturday in Vermont.
    start = instant("2026-10-16T23:00", ZoneInfo("America/Los_Angeles"))
    # Calendar date follows the destination zone, independently of the origin
    # date; driving-policy midnight limits remain a separate hard constraint.
    chosen, _ = solve_visit(burlington, start.astimezone(ZONE), instant("2026-10-17T20:00"))
    assert chosen.isoformat().startswith("2026-10-17T09:00")
    hotel = {
        "name": "overnight",
        "type": "hotel",
        "duration": 0,
        "timezone": ZONE.key,
        "check_in_date": "2026-10-16",
    }
    second = copy.deepcopy(burlington)
    second["duration"] = 3600
    apply_timing([hotel, second], instant("2026-10-16T17:00"), SchedulingPolicy(), ZONE.key)
    assert second["arrival_time"].startswith("2026-10-17T10:00")


def test_dst_ambiguous_source_clock_is_unknown_and_elapsed_dwell_is_real_time():
    rules = calendar(weekly_windows=[{"weekdays": [6], "opens": "01:30", "closes": "05:00"}])
    with pytest.raises(VisitCalendarConflict):
        solve_visit(candidate(rules), instant("2026-11-01T00:00"), instant("2026-11-01T06:00"))
    row = candidate(
        calendar(weekly_windows=[{"weekdays": [6], "opens": "00:00", "closes": "04:00"}])
    )
    chosen, proof = solve_visit(row, instant("2026-11-01T00:30"), instant("2026-11-01T06:00"))
    assert chosen.hour == 0
    assert proof["visit_end"] == "2026-11-01T01:30:00-05:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("day,selected", [("2026-10-15", False), ("2026-10-17", True)])
async def test_real_cp_sat_planner_reselects_infeasible_burlington(
    route, fake_services, burlington, day, selected
):
    route.duration = route.legs[0].duration = 3600
    services = fake_services.bundle()
    calls = []

    async def candidates(*args):
        calls.append("discovery")
        return DiscoveryResult([burlington], {})

    async def roads(*args):
        calls.append("road")
        measured = route.model_copy(deep=True)
        measured.legs = [measured.legs[0], measured.legs[0]]
        return measured

    async def zone(*args):
        return ZONE.key

    services.cp_sat_candidates, services.candidate_route = candidates, roads
    services.cp_sat_hotels = lambda *args: None
    services.timezone_at = zone
    options = PlanOptions(
        1,
        100,
        instant(day + "T10:00"),
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    result = await CPSatPlanner().plan(route, options, services)
    assert bool(result.stopping_points) is selected
    assert calls == ["discovery", "road"]
    if selected:
        assert result.stopping_points[0]["availability"]["status"] == "within_published_window"


@pytest.mark.asyncio
async def test_final_actual_road_conflict_reselects_without_another_discovery(
    monkeypatch, route, fake_services, burlington
):
    current_fixture(monkeypatch, burlington)
    route.duration = route.legs[0].duration = 3600
    services = fake_services.bundle()
    calls = []

    async def candidates(*args):
        calls.append("discovery")
        return DiscoveryResult([burlington], {})

    async def roads(*args):
        calls.append("solo")
        measured = route.model_copy(deep=True)
        measured.legs = [measured.legs[0], measured.legs[0]]
        return measured

    async def actual(*args):
        calls.append("final")
        measured = route.model_copy(deep=True)
        if args[-1]:
            first = measured.legs[0].model_copy(deep=True)
            first.duration = 6 * 3600  # Estimate 10am -> actual 4pm, after closing.
            measured.legs = [first, measured.legs[0]]
        return measured

    async def zone(*args):
        return ZONE.key

    services.cp_sat_candidates, services.candidate_route = candidates, roads
    services.cp_sat_hotels = lambda *args: None
    services.timezone_at = zone
    monkeypatch.setattr(routing_api, "_build_services", lambda: services)
    monkeypatch.setattr(routing_api, "_call_route", actual)
    monkeypatch.setattr(routing_api, "load_account_persona", lambda user: AccountPersona.default())
    monkeypatch.setattr(routing_api, "is_upcoming_departure", lambda value: True)
    monkeypatch.setattr(
        routing_api, "get_location", lambda **kw: SimpleNamespace(address="fixture")
    )
    payload = Route_Payload(
        initial_route=route,
        num_stops=1,
        budget=100,
        start=instant("2026-10-17T10:00"),
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    result = await routing_api.plan_final_route(payload, user_id="fixture")
    assert [stop["type"] for stop in result.stops] == ["end"]
    assert calls == ["discovery", "solo", "final", "final"]


def test_calendar_timezone_must_be_resolved_iana():
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            candidate(),
            datetime.fromisoformat("2026-10-17T10:00:00-04:00"),
            instant("2026-10-17T20:00"),
        )
    assert source_calendar(candidate()) is not None
    row = candidate()
    del row["timezone"]
    with pytest.raises(VisitCalendarConflict, match="timezone is unknown"):
        apply_timing(
            [row],
            instant("2026-10-17T10:00", ZoneInfo("America/Los_Angeles")),
            SchedulingPolicy(),
            "America/Los_Angeles",
        )


@pytest.mark.asyncio
async def test_itinerary_preserves_wait_and_revalidates_overridden_date(burlington, monkeypatch):
    current_fixture(monkeypatch, burlington)
    route = Route(
        coordinates=[],
        distance=0,
        duration=0,
        steps=[],
        stops=[burlington],
        geometry={"coordinates": []},
        cost=0,
        scheduling_policy=SchedulingPolicy(),
        start_timezone=ZONE.key,
        departure_time=instant("2026-10-17T08:00"),
    )
    days = await build_itinerary(Itinerary_Payload(route=route))
    stop = days[0].stops[1]
    assert stop.time == "09:00 AM"
    assert "Wait 60 minutes" in stop.notice
    assert stop.availability["ticket_availability"] == "unknown"
    route.scheduling_policy = None
    route.departure_time = None
    # Recover the real date from the road arrival before applying legacy defaults.
    recovered = await build_itinerary(Itinerary_Payload(route=route))
    assert recovered[0].date == "Saturday, October 17 2026"
    with pytest.raises(VisitCalendarConflict):
        await build_itinerary(
            Itinerary_Payload(route=route, start_time=instant("2026-10-15T08:00"))
        )
    route.scheduling_policy = None
    with pytest.raises(VisitCalendarConflict):
        await build_itinerary(
            Itinerary_Payload(route=route, start_time=instant("2026-10-15T10:00"))
        )


@pytest.mark.asyncio
async def test_itinerary_uses_validated_elapsed_departure_across_dst(monkeypatch):
    row = candidate(
        calendar(weekly_windows=[{"weekdays": [6], "opens": "00:00", "closes": "04:00"}])
    )
    current_fixture(monkeypatch, row)
    route = Route(
        coordinates=[],
        distance=0,
        duration=0,
        steps=[],
        stops=[row],
        geometry={"coordinates": []},
        cost=0,
        scheduling_policy=SchedulingPolicy(),
        start_timezone=ZONE.key,
        departure_time=instant("2026-11-01T00:30"),
    )
    days = await build_itinerary(Itinerary_Payload(route=route))
    assert days[0].stops[2].time == "01:30 AM"
    assert days[0].stops[1].availability["visit_end"] == "2026-11-01T01:30:00-05:00"
