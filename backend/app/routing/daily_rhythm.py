"""Display explicit rest/sleep availability inside a verified dated hotel stay."""

from datetime import UTC, datetime, timedelta

from app.agent.trip_dates import _localize
from app.models.scheduling_policy import advance, seconds_until
from app.routing.base import PlanningError
from app.routing.trip_modes import RhythmClockConflict


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
