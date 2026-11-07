"""Deterministic, place-free meal breaks shared by estimated and actual clocks.

The clock reserves elapsed time, not a venue, parking place or extra road detour.
Driving pauses use the next known stop's IANA clock; no meal location is inferred.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.agent.trip_dates import _localize
from app.models.scheduling_policy import advance, seconds_until
from app.routing.base import PlanningError

MEALS = (("breakfast", 7, 9, 30 * 60), ("lunch", 12, 14, 45 * 60), ("dinner", 18, 20, 60 * 60))


def meal_windows(schedule=None):
    """Default meal windows on an unwrapped local wake-cycle clock."""
    shift = 0 if schedule is None else schedule.bounds("sleep")[1] % 24 - 7
    return tuple(
        (kind, start + shift, end + shift, duration) for kind, start, end, duration in MEALS
    )


_NOTICE = (
    "Time reserved for a meal break. No venue or safe stopping location is verified; "
    "choose a safe place. Extra driving or parking time is not included. "
    "The timezone is the next known stop's planning clock."
)


def _absolute(value):
    return value.astimezone(UTC) if value.tzinfo else value


def _later(a, b):
    return a if _absolute(a) >= _absolute(b) else b


def _earlier(a, b):
    return a if _absolute(a) <= _absolute(b) else b


class MealScheduleConflict(PlanningError):
    public_message = (
        "The route cannot fit full meal breaks within the meal windows and driving cutoffs. "
        "Choose an earlier departure, fewer visits, or different driving cutoffs and replan."
    )

    def __init__(self):
        super().__init__(self.public_message, 422)


class MealScheduleHTTPError(HTTPException):
    code = "meal_schedule_conflict"

    def __init__(self):
        super().__init__(422, MealScheduleConflict.public_message)


class MealClock:
    """One request-local clock; speculative scheduling uses independent copies."""

    def __init__(self, departure: datetime, nominal_end: datetime, daily_schedule=None):
        self.daily_schedule = daily_schedule
        self.departure = departure
        self.nominal_end = nominal_end
        self.done = set()
        self.breaks = []

    def copy(self):
        return deepcopy(self)

    def _next(self, start, end, zone):
        local_start = self.departure.astimezone(zone) if zone else self.departure
        local_end = end.astimezone(zone) if zone else end
        days = (local_end.date() - local_start.date()).days
        if days > 62:
            raise PlanningError("Meal scheduling exceeds the trip-day limit", 422)
        choices = []
        for offset in range(-1 if self.daily_schedule else 0, max(0, days) + 1):
            date = local_start.date() + timedelta(days=offset)
            for meal, opening, closing, duration in meal_windows(self.daily_schedule):
                key = (date.isoformat(), meal)
                if key in self.done:
                    continue
                wall_start = datetime.combine(date, datetime.min.time()) + timedelta(hours=opening)
                wall_end = datetime.combine(date, datetime.min.time()) + timedelta(hours=closing)
                window_start = wall_start.replace(tzinfo=zone)
                window_end = wall_end.replace(tzinfo=zone)
                if self.daily_schedule and zone:
                    # Ignore unrelated neighboring cycles before strict DST localization.
                    endings = [wall_end.replace(tzinfo=zone, fold=f) for f in (0, 1)]
                    openings = [wall_start.replace(tzinfo=zone, fold=f) for f in (0, 1)]
                    if all(_absolute(t) <= _absolute(self.departure) for t in endings) or all(
                        _absolute(t) >= _absolute(self.nominal_end)
                        or _absolute(t) >= _absolute(end)
                        for t in openings
                    ):
                        continue
                    if hasattr(zone, "key"):
                        try:
                            window_start = _localize(wall_start, zone)
                            window_end = _localize(wall_end, zone)
                        except ValueError:
                            raise self.conflict(meal) from None
                earliest = _later(window_start, self.departure)
                # Fixed meal-free bounds prevent delays from pulling in more meals.
                last = _earlier(window_end, self.nominal_end)
                if seconds_until(earliest, last) + 1e-6 < duration:
                    continue
                if seconds_until(window_start, end) <= 1e-6:
                    continue
                if seconds_until(start, window_end) < -1e-6:
                    raise self.conflict(meal)
                choices.append(
                    (
                        earliest,
                        key,
                        window_start,
                        window_end,
                        duration,
                        last,
                        advance(last, -duration),
                    )
                )
        return min(choices, key=lambda item: _absolute(item[0])) if choices else None

    @staticmethod
    def conflict(meal):
        return MealScheduleConflict()

    def _reserve(self, candidate, start, zone):
        earliest, key, window_start, window_end, duration, last, _ = candidate
        beginning = _later(start, earliest)
        finish = advance(beginning, duration)
        if seconds_until(finish, window_end) < -1e-6:
            raise self.conflict(key[1])
        self.done.add(key)
        self.breaks.append(
            {
                "id": f"meal:{key[0]}:{key[1]}",
                "kind": "meal",
                "meal_type": key[1],
                "name": key[1].capitalize(),
                "status": "reserved",
                "optional": False,
                "arrival_time": beginning.isoformat(),
                "departure_time": finish.isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "duration_seconds": duration,
                "timezone": getattr(zone, "key", None),
                "notice": _NOTICE
                + (" Meal breaks follow your sleep schedule." if self.daily_schedule else ""),
            }
        )
        return finish

    def drive(self, start, seconds, zone):
        """Pause road time at a meal; the road duration itself stays unchanged."""
        now = start.astimezone(zone) if zone else start
        remaining = seconds
        while remaining > 1e-6:
            end = advance(now, remaining)
            candidate = self._next(now, end, zone)
            if candidate is None:
                return end
            if seconds_until(candidate[6], end) <= 1e-6:
                return end
            beginning = _later(now, candidate[6])
            driven = max(0.0, seconds_until(now, beginning))
            remaining -= driven
            now = self._reserve(candidate, beginning, zone)
        return now

    def before_visit(self, road_arrival, visit_arrival, duration, zone):
        """Put breaks in opening waits or before an unsplit visit, never inside it."""
        cursor = road_arrival
        while True:
            candidate = self._next(cursor, advance(visit_arrival, duration), zone)
            if candidate is None:
                return visit_arrival
            if (
                seconds_until(
                    advance(visit_arrival, duration), advance(candidate[3], -candidate[4])
                )
                >= -1e-6
            ):
                return visit_arrival
            finish = self._reserve(candidate, cursor, zone)
            if seconds_until(finish, visit_arrival) < -1e-6:
                return finish
            cursor = finish

    def rest(self, arrival, departure, zone, *, awake_intervals=None):
        """Use hotel awake time without moving sleep or the selected restart."""
        cursor = arrival
        while True:
            candidate = self._next(cursor, departure, zone)
            if candidate is None:
                return
            beginning = _later(cursor, candidate[0])
            if awake_intervals is not None:
                for awake_start, awake_end in awake_intervals:
                    trial = _later(beginning, awake_start)
                    limit = _earlier(_earlier(awake_end, departure), candidate[3])
                    if seconds_until(advance(trial, candidate[4]), limit) >= -1e-6:
                        beginning = trial
                        break
                else:
                    # A meal still fitting after restart belongs to the next
                    # drive; an already closed window cannot be eaten in sleep.
                    if seconds_until(advance(departure, candidate[4]), candidate[3]) >= -1e-6:
                        return
                    raise self.conflict(candidate[1][1])
            if seconds_until(advance(beginning, candidate[4]), departure) < -1e-6:
                # E.g. an early restart: breakfast is handled by the next drive.
                return
            cursor = self._reserve(candidate, beginning, zone)

    def finish(self, arrival, zone):
        """Close any eligible deferred break before the final (possibly zero) leg ends."""
        now = arrival
        for _ in range(189):
            candidate = self._next(now, advance(now, 0.001), zone)
            if candidate is None:
                return now
            now = self._reserve(candidate, now, zone)
        raise MealScheduleConflict()
