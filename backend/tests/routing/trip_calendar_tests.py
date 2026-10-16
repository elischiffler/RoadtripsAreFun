"""Full-dwell prebudget checks share the final calendar's timezone semantics."""

import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.routing.base import MAX_TRIP_OVERNIGHTS
from app.routing.trip_calendar import TripCalendar, possible_visit
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


def timed(day, window, **extra):
    return {
        "provider_id": "fixture:timed",
        "coordinates": [40.7, -74.0],
        "categories": ["culture"],
        "source_provenance": [
            {
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "date_overrides": [{"date": day, "windows": [window]}],
                    "source_receipts": [{"source_url": "https://operator.example/fixture"}],
                    **extra,
                }
            }
        ],
    }


@pytest.mark.parametrize(
    "day,window,expected",
    [
        ("2030-03-10", {"opens": "01:00", "closes": "03:00"}, False),
        ("2030-11-03", {"opens": "00:00", "closes": "02:00"}, True),
        ("2030-03-10", {"opens": "02:00", "closes": "05:00"}, False),
    ],
)
def test_actual_iana_dst_elapsed_dwell_matches_final_solver(day, window, expected):
    zone = ZoneInfo("America/New_York")
    start = datetime.fromisoformat(day).replace(tzinfo=zone)
    record = timed(day, window)
    assert possible_visit(record, start, zone) is expected
    if expected:
        solve_visit(record, start, start.replace(hour=6))
    else:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(record, start, start.replace(hour=6))


def test_overnight_window_and_next_day_closure_keep_the_same_hard_rules():
    zone = ZoneInfo("America/New_York")
    start = datetime(2030, 7, 17, 23, tzinfo=zone)
    record = timed("2030-07-17", {"opens": "23:00", "closes": "02:00", "end_day_offset": 1})
    assert possible_visit(record, start, zone)
    record["source_provenance"][0]["source_visit_calendar"]["annual_closures"] = ["07-18"]
    assert not possible_visit(record, start, zone)


def test_unrelated_nonexistent_midnight_does_not_erase_a_daytime_visit():
    zone = ZoneInfo("America/Santiago")
    start = datetime(2026, 9, 5, 9, tzinfo=zone)
    record = timed("2026-09-05", {"opens": "10:00", "closes": "17:00"})
    assert possible_visit(record, start, zone)
    visit, _ = solve_visit(record, start, start.replace(hour=20))
    assert visit.hour == 10


def test_existing_overnight_bound_includes_last_permitted_day_only():
    zone = ZoneInfo("America/New_York")
    start = datetime(2030, 7, 17, 9, tzinfo=zone)
    last_day = (start + timedelta(days=MAX_TRIP_OVERNIGHTS)).date()
    record = timed(str(last_day), {"opens": "10:00", "closes": "12:00"})
    original = copy.deepcopy(record)
    assert possible_visit(record, start, zone)
    assert record == original
    record["source_provenance"][0]["source_visit_calendar"]["date_overrides"][0]["date"] = str(
        last_day + timedelta(days=1)
    )
    assert not possible_visit(record, start, zone)


@pytest.mark.asyncio
async def test_resolve_candidate_zone_instead_of_inheriting_departure_zone():
    seen = []

    async def timezone(point):
        seen.append(point)
        return "America/New_York"

    # The New York window has ended at this instant, although it is still 9am LA.
    start = datetime(2030, 7, 17, 9, tzinfo=ZoneInfo("America/Los_Angeles"))
    record = timed("2030-07-17", {"opens": "09:00", "closes": "12:00"})
    assert not await TripCalendar(start, timezone).eligible(record)
    assert seen == [record["coordinates"]]
    assert not await TripCalendar(start, None).eligible(record)
