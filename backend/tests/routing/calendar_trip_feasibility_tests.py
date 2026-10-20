"""Requested-trip calendar gates before discovery quotas, with final hard scheduling.

Provider/road/hotel responses below are explicit offline controls. The expired
calendar uses the reviewed Weaverville operator's actual 2026 clocks and season;
its 18 synthetic copies reproduce quota pressure, not 18 genuine destinations.
"""

import asyncio
import copy
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.schemas import LLMResponse
from app.routing.base import MAX_TRIP_OVERNIGHTS, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.discovery import SelectedAttraction
from app.routing.explanation import capture_explanation
from app.routing.occupancy import HotelRoom
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.sources import persona_candidates as source
from app.routing.trip_calendar import possible_visit
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit

ZONE = ZoneInfo("America/Los_Angeles")
POINT = [40.730418279702896, -122.93963362422937]  # Retained native Weaverville point.


def weaverville_calendar():
    return {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [{"weekdays": [2], "opens": "16:00", "closes": "19:00"}],
        "seasons": [{"kind": "dated", "start": "2026-05-20", "end": "2026-10-14"}],
        "source_receipts": [
            {
                "source_url": "https://weavervillefarmersmarket.org/",
                "snapshot_sha256": "a75efb2b8ec409bac4225e7ed2f24c19b72e9f36396ed0ca1e5f28cdd329db40",
                "checked_at": "2026-10-15T19:57:13.668816+00:00",
                "literal_facts": {
                    "literal": "2026 Market Season May 20th – Oct 14th Wednesdays 4pm – 7pm"
                },
            }
        ],
    }


def fixture_calendar(**fields):
    return {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [{"weekdays": [2], "opens": "10:00", "closes": "17:00"}],
        "source_receipts": [{"source_url": "https://operator.example/synthetic-calendar"}],
        **fields,
    }


def timed_place(identifier, rules, *, rank=1):
    return {
        "provider_id": identifier,
        "name": "Offline calendar control " + identifier,
        "coordinates": list(POINT),
        "provider_rank": rank,
        # Same initial category as outdoor prevents variety rotation from hiding
        # the original bounded-shortlist failure.
        "categories": ["daytime", "food_destination"],
        "source": "synthetic-calendar-regression",
        "source_release": "offline-control",
        "source_attribution": "Explicit regression fixture; no live availability claim",
        "source_provenance": [
            {
                "dataset": "Offline calendar regression",
                "source_visit_calendar": copy.deepcopy(rules),
            }
        ],
    }


def outdoor_place():
    return {
        "provider_id": "synthetic:outdoor-control",
        "name": "Usable untimed outdoor control",
        "coordinates": list(POINT),
        "provider_rank": 100,
        "categories": ["daytime", "nature"],
        "source_provenance": [
            {
                "dataset": "Synthetic outdoor regression control; explicit fixture hours",
                "source_visit_calendar": fixture_calendar(
                    weekly_windows=[
                        {"weekdays": list(range(7)), "opens": "08:00", "closes": "20:00"}
                    ]
                ),
            }
        ],
    }


def route(duration=3600, *, progress_fraction=0.5):
    lat, lon = POINT
    # Elapsed durations are controlled fixtures, never asserted real road times.
    return SimpleNamespace(
        duration=float(duration),
        distance=1000.0,
        legs=[],
        geometry=SimpleNamespace(
            coordinates=[
                [lon - 0.03 * progress_fraction, lat],
                [lon + 0.03 * (1 - progress_fraction), lat],
            ]
        ),
    )


class RatingAI:
    def __init__(self):
        self.rated_names = []

    def complete(self, messages, tools):
        marker = "Rate only these source-record names, preserving each exactly: "
        names = json.loads(messages[-1].content.split(marker, 1)[1])
        self.rated_names.extend(names)
        return LLMResponse(
            content=json.dumps(
                {
                    "candidates": [
                        {"name": name, "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.8)}
                        for name in names
                    ]
                }
            )
        )


class Places:
    def __init__(self, records):
        self.records = copy.deepcopy(records)

    async def attractions_near(self, point):
        return copy.deepcopy(self.records)


def configure(fake_services, baseline, records):
    ai, discoveries, hotel_dates = RatingAI(), [], []
    provider = Places(records)
    services = fake_services.bundle()

    async def candidates(raw_route, plan, weights):
        result = await source.attraction_candidates(
            raw_route, plan, weights, ai=ai, places=provider
        )
        discoveries.append(result)
        return result

    async def roads(*_args):
        return SimpleNamespace(
            duration=baseline.duration,
            legs=[SimpleNamespace(duration=baseline.duration / 2)] * 2,
        )

    async def hotels(position, check_in, _prices, _weights, hotel_rooms):
        hotel_dates.append(check_in.isoformat())
        return [
            {
                "provider_id": "synthetic:hotel-" + check_in.isoformat(),
                "name": "Offline dated hotel control",
                "coordinates": list(position),
                "price": 80.0,
                "utility": 0.8,
                "hotel_rooms": [room.model_dump() for room in hotel_rooms],
                "room_offers": [],
                "check_in_date": check_in.isoformat(),
                "price_scope": "one_room_one_night_including_taxes_fees",
            }
        ]

    async def timezone(_point):
        return ZONE.key

    services.cp_sat_candidates = candidates
    services.candidate_route = roads
    services.cp_sat_hotels = hotels
    services.timezone_at = timezone
    return services, ai, discoveries, hotel_dates


def options(day, *, hour=9):
    return PlanOptions(
        1,
        100,
        datetime.fromisoformat(day).replace(hour=hour, tzinfo=ZONE),
        weights=default_weights(),
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("unusable", ["expired_season", "short_session", "impossible_fixed_start"])
async def test_unusable_full_shortlist_cannot_starve_a_real_outdoor_plan(fake_services, unusable):
    rules = weaverville_calendar()
    trip = options("2026-10-21")
    if unusable == "short_session":
        rules = fixture_calendar(
            weekly_windows=[{"weekdays": [2], "opens": "16:00", "closes": "17:59"}]
        )
    elif unusable == "impossible_fixed_start":
        rules = fixture_calendar(
            weekly_windows=[{"weekdays": [2], "opens": "16:00", "closes": "19:00"}],
            fixed_starts=["2026-10-21T18:00:00-07:00"],
        )
    expired = [timed_place(f"usda-market:unusable-{n:02d}", rules, rank=n + 1) for n in range(18)]
    outdoor = outdoor_place()
    original = copy.deepcopy(expired)
    baseline = route()
    services, ai, discoveries, hotel_dates = configure(fake_services, baseline, [*expired, outdoor])
    with capture_explanation():
        result = await CPSatPlanner().plan(baseline, trip, services)
    assert [stop["provider_id"] for stop in result.stopping_points] == [outdoor["provider_id"]]
    assert [p["provider_id"] for p in discoveries[0].candidates] == [outdoor["provider_id"]]
    if unusable == "expired_season":
        assert ai.rated_names == [outdoor["name"]]
        assert discoveries[0].explanation["raw_pool_count"] == 1
    else:
        # A sub-two-hour window can now fit an AI-estimated visit. Reserve the
        # fallback-feasible outdoor place before spending remaining rating slots
        # on those windows; this ratings-only fake triggers two-hour fallbacks.
        assert ai.rated_names.count(outdoor["name"]) == 1
        assert discoveries[0].explanation["raw_pool_count"] == 19
    assert len(discoveries[0].explanation["calendar_excluded_provider_ids"]) == 18
    assert result.stopping_points[0]["source_provenance"] == outdoor["source_provenance"]
    assert expired == original and hotel_dates == []
    # The final hard gate remains authoritative even after coarse trip discovery.
    with pytest.raises(VisitCalendarConflict):
        solve_visit(expired[0], trip.start, trip.start.replace(hour=20))


@pytest.mark.asyncio
async def test_future_season_is_evaluated_for_requested_trip_and_preserves_source(fake_services):
    rules = fixture_calendar(
        seasons=[{"kind": "dated", "start": "2030-07-01", "end": "2030-07-31"}]
    )
    place = timed_place("usda-market:future-season-control", rules)
    original = copy.deepcopy(place)
    baseline = route()
    services, _, discoveries, _ = configure(fake_services, baseline, [place])
    with capture_explanation():
        result = await CPSatPlanner().plan(baseline, options("2030-07-17"), services)
    assert [p["provider_id"] for p in discoveries[0].candidates] == [place["provider_id"]]
    assert len(result.stopping_points) == 1
    stop = result.stopping_points[0]
    assert stop["source_provenance"] == original["source_provenance"]
    assert stop["source_attribution"] == original["source_attribution"]
    assert stop["availability"]["visit_start"].startswith("2030-07-17T10:00")
    assert stop["availability"]["dwell_seconds"] == 7200
    assert stop["availability"]["ticket_availability"] == "unknown"
    assert place == original


@pytest.mark.asyncio
async def test_later_trip_day_dated_window_survives_discovery_and_overnights(fake_services):
    # A 30-hour controlled drive reaches this source point after three hotel nights.
    # The source opens only on travel day four; filtering only departure day or a
    # two-day solve horizon would discard a visit the actual scheduler can make.
    rules = fixture_calendar(
        weekly_windows=[],
        seasons=[{"kind": "dated", "start": "2030-05-25", "end": "2030-05-25"}],
        date_overrides=[{"date": "2030-05-25", "windows": [{"opens": "10:00", "closes": "17:00"}]}],
    )
    place = timed_place("usda-market:fourth-day-control", rules)
    baseline = route(30 * 3600, progress_fraction=29 / 30)
    services, _, discoveries, hotel_dates = configure(fake_services, baseline, [place])
    with capture_explanation():
        result = await CPSatPlanner().plan(baseline, options("2030-05-22"), services)
    assert [p["provider_id"] for p in discoveries[0].candidates] == [place["provider_id"]]
    assert hotel_dates == ["2030-05-22", "2030-05-23", "2030-05-24"]
    visits = [stop for stop in result.stopping_points if stop["type"] == "stop"]
    assert len(visits) == 1
    assert visits[0]["availability"]["visit_start"].startswith("2030-05-25T11:00")
    assert visits[0]["availability"]["visit_end"].startswith("2030-05-25T13:00")
    assert visits[0]["source_provenance"] == place["source_provenance"]


@pytest.mark.asyncio
async def test_concurrent_requested_trip_windows_do_not_leak_between_plans(fake_services):
    rules = fixture_calendar(
        seasons=[{"kind": "dated", "start": "2030-07-01", "end": "2030-07-31"}]
    )
    timed = timed_place("usda-market:concurrent-season-control", rules)
    outdoor = outdoor_place()

    async def run(day):
        baseline = route()
        services, _, discoveries, _ = configure(fake_services, baseline, [timed, outdoor])
        with capture_explanation():
            result = await CPSatPlanner().plan(baseline, options(day), services)
        return result, discoveries[0]

    (summer, summer_discovery), (after, after_discovery) = await asyncio.gather(
        run("2030-07-17"), run("2030-08-07")
    )
    assert {place["provider_id"] for place in summer_discovery.candidates} == {
        timed["provider_id"],
        outdoor["provider_id"],
    }
    assert [place["provider_id"] for place in after_discovery.candidates] == [
        outdoor["provider_id"]
    ]
    assert summer.stopping_points
    assert [stop["provider_id"] for stop in after.stopping_points] == [outdoor["provider_id"]]
    assert after_discovery.explanation["calendar_excluded_provider_ids"] == [timed["provider_id"]]


@pytest.mark.asyncio
async def test_cross_zone_last_permitted_day_keeps_a_visit_after_exactly_60_overnights(
    fake_services,
):
    origin = ZoneInfo("America/New_York")
    departure = datetime(2030, 5, 1, 0, 30, tzinfo=origin)
    last_day = departure.date() + timedelta(days=MAX_TRIP_OVERNIGHTS)
    assert departure.astimezone(ZONE).date().isoformat() == "2030-04-30"
    assert last_day.isoformat() == "2030-06-30"
    rules = fixture_calendar(
        weekly_windows=[],
        date_overrides=[
            {"date": last_day.isoformat(), "windows": [{"opens": "10:00", "closes": "17:00"}]}
        ],
    )
    place = timed_place("usda-market:cross-zone-last-day-control", rules)
    place.update(utility=0.8, route_progress_seconds=556.5 * 3600, detour_seconds=0)
    baseline = SimpleNamespace(
        duration=place["route_progress_seconds"],
        distance=5_000_000,
        legs=[],
        geometry=SimpleNamespace(coordinates=[[-74.0, 40.7], [POINT[1], POINT[0]]]),
    )
    services, _, _, hotel_dates = configure(fake_services, baseline, [place])

    async def timezone(coordinates):
        # Explicit clock controls: origin/intermediate bookings use New York;
        # the candidate and destination use the independently resolved LA zone.
        return ZONE.key if coordinates == POINT else origin.key

    services.timezone_at = timezone
    trip = PlanOptions(
        1,
        100,
        departure,
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    stops, _ = await schedule_cp_sat_route(
        baseline, [SelectedAttraction(place["route_progress_seconds"], place)], trip, services
    )
    visits = [stop for stop in stops if stop["type"] == "stop"]
    assert len(hotel_dates) == MAX_TRIP_OVERNIGHTS == 60
    assert len(visits) == 1
    assert visits[0]["availability"]["visit_start"] == "2030-06-30T14:00:00-07:00"
    assert visits[0]["availability"]["visit_end"] == "2030-06-30T16:00:00-07:00"
    assert visits[0]["source_provenance"] == place["source_provenance"]
    # Coarse discovery must retain what the actual unchanged scheduler accepts.
    assert possible_visit(place, departure, ZONE)
