"""Presentation-only meal windows; never route legs, visits or reservations."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.models.itinerary_models import Itinerary_Day

_WINDOWS = (("breakfast", 7, 9), ("lunch", 12, 14), ("dinner", 18, 20))
_NOTICE = (
    "Open planning window; no time or place is reserved. "
    "May overlap driving or visits; adjust the time."
)


def _comparable(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value


def _outside(window: datetime, boundary: datetime | None, *, before: bool) -> bool:
    # Missing timezone information cannot establish an absolute ordering.
    if boundary is None or (window.tzinfo is None) != (boundary.tzinfo is None):
        return False
    if before:
        return _comparable(window) <= _comparable(boundary)
    return _comparable(window) >= _comparable(boundary)


def add_meal_windows(
    days: list[Itinerary_Day],
    *,
    departure: datetime | None,
    trip_end: datetime | None = None,
    start_timezone: str | None = None,
) -> list[Itinerary_Day]:
    """Append advisory windows, keeping all physical rows and timings intact.

    The first known IANA timezone on a day is used for that day's windows; when
    unavailable, retain the preceding day's zone or known departure offset.
    Windows remain full suggested windows even when only part overlaps the trip.
    Only entirely elapsed/future windows are omitted at authoritative bounds.
    No duration is assigned: the solver has not reserved any meal time.
    """
    if departure is None:
        # Do not manufacture dated suggestions from the legacy fallback date.
        return days
    timezone = start_timezone
    fallback_zone = departure.tzinfo
    result = []
    emitted_ids = set()
    for day in days:
        actual = [stop for stop in day.stops if stop.kind != "meal"]
        timezone = next((stop.timezone for stop in actual if stop.timezone), timezone)
        zone = ZoneInfo(timezone) if timezone else fallback_zone
        if not timezone:
            for stop in actual:
                if stop.arrival_time:
                    known_zone = datetime.fromisoformat(stop.arrival_time).tzinfo
                    if known_zone is not None:
                        zone = fallback_zone = known_zone
                        break
        local_date = datetime.strptime(day.date, "%A, %B %d %Y").date()
        meals = []
        for meal, start_hour, end_hour in _WINDOWS:
            identifier = f"meal:{local_date.isoformat()}:{meal}"
            if identifier in emitted_ids:
                continue
            window_start = datetime.combine(local_date, time(start_hour), tzinfo=zone)
            window_end = datetime.combine(local_date, time(end_hour), tzinfo=zone)
            if _outside(window_end, departure, before=True) or _outside(
                window_start, trip_end, before=False
            ):
                continue
            meals.append(
                Itinerary_Day.Itinerary_Stop(
                    id=identifier,
                    kind="meal",
                    meal_type=meal,
                    name=meal.capitalize(),
                    time="Unscheduled",
                    window_start=window_start.isoformat(),
                    window_end=window_end.isoformat(),
                    timezone=timezone,
                    optional=True,
                    status="open",
                    notice=_NOTICE,
                )
            )
            emitted_ids.add(identifier)
        result.append(day.model_copy(update={"stops": [*actual, *meals]}))
    return result
