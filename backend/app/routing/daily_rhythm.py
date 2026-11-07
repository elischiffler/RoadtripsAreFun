"""Display explicit rest/sleep availability inside a verified dated hotel stay."""

from datetime import UTC, datetime, timedelta

from app.agent.trip_dates import _localize
from app.models.scheduling_policy import advance, seconds_until
from app.routing.base import PlanningError
from app.routing.trip_modes import RhythmAvailabilityConflict, RhythmClockConflict


def rest_blocks(arrival, departure, rhythm):
    zone = arrival.tzinfo
    if zone is None:
        raise PlanningError("A verified local timezone is required for the daily rhythm", 422)
    cuts = {arrival.astimezone(UTC), departure.astimezone(UTC)}
    sleep_start, sleep_end = rhythm.bounds("sleep")
    for offset in range(-1, (departure.date() - arrival.date()).days + 2):
        day = arrival.date() + timedelta(days=offset)
        for hour in (sleep_start, sleep_end % 24):
            naive = datetime.combine(day, datetime.min.time()).replace(hour=hour)
            # Ignore neighboring dates before asking the strict localizer about
            # DST. An ambiguity outside this actual stay cannot invalidate it.
            possible = [naive.replace(tzinfo=zone, fold=fold).astimezone(UTC) for fold in (0, 1)]
            if not any(
                arrival.astimezone(UTC) < point < departure.astimezone(UTC) for point in possible
            ):
                continue
            try:
                point = _localize(naive, zone)
            except ValueError:
                raise RhythmClockConflict() from None
            if seconds_until(arrival, point) > 0 and seconds_until(point, departure) > 0:
                cuts.add(point.astimezone(UTC))
    values = sorted(cuts)
    result = []
    for start, end in zip(values, values[1:]):
        middle = advance(start, seconds_until(start, end) / 2).astimezone(zone)
        kind = "sleep" if rhythm.slots[middle.hour] == "sleep" else "rest"
        result.append(
            {
                "kind": kind,
                "name": "Sleep time" if kind == "sleep" else "Rest time",
                "status": "planned",
                "optional": False,
                "arrival_time": start.astimezone(zone).isoformat(),
                "departure_time": end.astimezone(zone).isoformat(),
                "duration_seconds": int(seconds_until(start, end)),
                "timezone": getattr(zone, "key", None),
            }
        )
    return result


def clear_rhythm_metadata(stop):
    """A legacy policy cannot reuse copied derived rhythm display state."""
    for key in ("lodging", "daily_rhythm_blocks", "check_in_timing_notice"):
        stop.pop(key, None)


def drive_cycle(policy, instant, zone, *, allow_completed_boundary=False):
    """Resolve the known next stop's local cycle, not the origin's calendar date.

    A zero-road tail can complete exactly at a cutoff; it cannot begin fresh
    driving in rest/sleep or reinterpret the cutoff as tomorrow's window.
    """
    local = instant.astimezone(zone) if zone is not None else instant
    try:
        return policy.travel_day_for(local)
    except ValueError:
        if allow_completed_boundary:
            previous = advance(local, -0.000001)
            if policy.daily_schedule.available(previous):
                day = policy.travel_day_for(previous)
                if abs(seconds_until(local, policy.deadline(day, zone))) <= 0.000001:
                    return day
        raise RhythmAvailabilityConflict() from None
