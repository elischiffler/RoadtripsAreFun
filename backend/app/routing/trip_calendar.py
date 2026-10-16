"""Request-local, conservative calendar feasibility before discovery budgets.

There is no requested end date in PlanOptions. Test every possible visit day
within the scheduler's existing overnight bound, rather than today's date or
only departure day. This is a necessary condition, not a joint itinerary proof;
the scheduler and final road timing still enforce their actual daily deadlines.
"""

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.scheduling_policy import seconds_until
from app.routing.base import MAX_TRIP_OVERNIGHTS
from app.routing.runtime import singleflight
from app.routing.visit_calendar import (
    _TICKS,
    VISIT_SECONDS,
    _allowed_day,
    _at,
    calendar_eligible,
    day_intervals,
    requires_calendar,
    source_calendar,
)


def possible_visit(record, departure: datetime, zone: ZoneInfo) -> bool:
    """Require one full dwell in a source window on a permissible trip day.

    Use the same attributed windows, season/closure rules, DST localization and
    elapsed-time arithmetic as solve_visit. Never treat a fixed event start as
    proof of its end. No source facts or unknown values are rewritten.
    """
    if not calendar_eligible(record):
        return False
    if not requires_calendar(record):
        return True
    if departure.tzinfo is None or not isinstance(zone, ZoneInfo):
        return False
    calendar = source_calendar(record)
    earliest = departure.astimezone(zone)
    first = earliest.date()
    # The scheduler starts its booking-day counter in the origin's zone. A
    # westbound candidate can still be on yesterday at departure; dropping the
    # origin date would wrongly lose its final permitted visit day.
    last = max(first, departure.date()) + timedelta(days=MAX_TRIP_OVERNIGHTS)
    try:
        deadline = _at(last + timedelta(days=1), "00:00", zone)
    except ValueError:
        deadline = None
    for offset in range(-1, (last - first).days + 1):
        day = first + timedelta(days=offset)
        for opens, closes in day_intervals(calendar, day, zone):
            if closes.date() > last:
                if deadline is None:
                    continue
                closes = min(closes, deadline)
            lower = max(0, math.ceil(seconds_until(earliest, opens) * _TICKS))
            upper = math.floor(seconds_until(earliest, closes) * _TICKS) - VISIT_SECONDS * _TICKS
            if calendar.fixed_starts:
                if any(
                    _allowed_day(calendar, value.astimezone(zone).date())
                    and lower <= round(seconds_until(earliest, value) * _TICKS) <= upper
                    for value in calendar.fixed_starts
                ):
                    return True
            elif lower <= upper:
                return True
    return False


@dataclass(frozen=True)
class TripCalendar:
    departure: datetime
    timezone_at: Callable[[list[float]], Awaitable[str]] | None

    def snapshot(self):
        return {
            "departure": self.departure.isoformat(),
            "maximum_overnights": MAX_TRIP_OVERNIGHTS,
            "timezone_source": "candidate_provider",
            "scope": "necessary_full_dwell_window; final_itinerary_validation_required",
        }

    async def eligible(self, record):
        if not calendar_eligible(record):
            return False
        if not requires_calendar(record):
            return True
        if self.timezone_at is None:
            return False
        coordinates = record["coordinates"]

        async def resolve():
            return ZoneInfo(await self.timezone_at(list(coordinates)))

        zone = await singleflight(("calendar_timezone", tuple(coordinates)), resolve)
        # The candidate's resolved zone is required even when departure is aware.
        return possible_visit(record, self.departure, zone)
