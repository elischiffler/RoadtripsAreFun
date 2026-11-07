"""The actual-leg clock shared by final reroute validation and itinerary display."""

import math
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.daily_schedule import DailyRhythmClockError
from app.models.scheduling_policy import SchedulingPolicy, advance, local_time, seconds_until
from app.routing.base import PlanningError
from app.routing.daily_rhythm import rest_blocks
from app.routing.lodging import validate_stored_stay
from app.routing.meal_reservations import MealClock, MealScheduleConflict
from app.routing.trip_modes import (
    RhythmAvailabilityConflict,
    RhythmClockConflict,
    require_overnight_rhythm,
)
from app.routing.visit_calendar import VisitCalendarConflict, requires_calendar, solve_visit
from app.routing.visit_duration import visit_seconds


def apply_timing(
    stops,
    start: datetime,
    policy: SchedulingPolicy,
    start_timezone: str | None = None,
    *,
    reserve_meal_slots: bool = False,
    _nominal: bool = False,
):
    """Recompute all timing, including place-free breaks; ignore supplied break metadata."""
    if policy.daily_schedule and any(stop.get("type") == "hotel" for stop in stops):
        # Rebuild/edit callers must honor the same accommodation limitation as
        # candidate confirmation, even for previously supplied route JSON.
        require_overnight_rhythm(policy)
    clock = None
    if reserve_meal_slots:
        try:
            ZoneInfo(start_timezone)
            for stop in stops:
                ZoneInfo(stop.get("timezone"))
        except (ZoneInfoNotFoundError, TypeError, ValueError):
            raise PlanningError(
                "Meal reservations require verified route timezones; replan this trip", 422
            ) from None
        if not stops or stops[-1].get("type") != "end":
            raise PlanningError(
                "Meal reservations require a complete route with a final destination", 422
            )
        nominal = deepcopy(stops)
        apply_timing(nominal, start, policy, start_timezone, _nominal=True)
        departure = local_time(start, ZoneInfo(start_timezone)) if start_timezone else start
        clock = MealClock(
            departure, datetime.fromisoformat(nominal[-1]["arrival_time"]), policy.daily_schedule
        )
    try:
        _apply_timing(stops, start, policy, start_timezone, clock, validate_quotes=not _nominal)
    except DailyRhythmClockError:
        raise RhythmClockConflict() from None


def _apply_timing(stops, start, policy, start_timezone, clock, *, validate_quotes=True):
    now = start
    if start_timezone:
        zone = ZoneInfo(start_timezone)
        now = local_time(start, zone)
    try:
        travel_day = policy.travel_day_for(now)
    except ValueError as exc:
        raise PlanningError(str(exc), 422) from None
    for stop in stops:
        meal_index = len(clock.breaks) if clock else 0
        duration = stop["duration"]
        if not math.isfinite(duration) or duration < 0:
            raise PlanningError("Mapbox returned an invalid leg duration", 502)
        if stop["type"] == "stop" and requires_calendar(stop) and not stop.get("timezone"):
            raise VisitCalendarConflict(
                stop.get("provider_id", "unknown"), "arrival IANA timezone is unknown"
            )
        zone = ZoneInfo(stop["timezone"]) if stop.get("timezone") else now.tzinfo
        if policy.daily_schedule and duration > 1e-6:
            local_departure = now.astimezone(zone) if zone else now
            if not policy.daily_schedule.available(local_departure):
                # A timezone change can move the next leg's local clock back into
                # rest/sleep. Do not fabricate a safe roadside wait location.
                raise RhythmAvailabilityConflict()
        arrival = clock.drive(now, duration, zone) if clock else advance(now, duration)
        if zone is not None:
            arrival = arrival.astimezone(zone)
        final = stop["type"] == "end"
        if clock and final:
            arrival = clock.finish(arrival, zone)
        cutoff = policy.arrival_cutoff(final=final)
        deadline = policy.deadline(travel_day, zone, final=final)
        if stop["type"] == "stop":
            road_arrival = arrival
            arrival, availability = solve_visit(stop, arrival, deadline)
            opening_wait = max(0, seconds_until(road_arrival, arrival))
            if clock:
                for _ in range(4):
                    after_meals = clock.before_visit(
                        road_arrival, arrival, visit_seconds(stop), zone
                    )
                    if seconds_until(arrival, after_meals) <= 1e-6:
                        break
                    arrival, availability = solve_visit(stop, after_meals, deadline)
                    opening_wait += max(0, seconds_until(after_meals, arrival))
                else:
                    raise PlanningError(
                        "Meal and visit scheduling did not converge; replan this route", 422
                    )
            stop.update(
                road_arrival_time=road_arrival.isoformat(),
                wait_seconds=opening_wait,
                availability=availability,
            )
        departure = advance(arrival, visit_seconds(stop)) if stop["type"] == "stop" else arrival
        if seconds_until(departure, deadline) < -1e-6:
            if clock:
                raise MealScheduleConflict()
            raise PlanningError(
                f"Final route exceeds the daily driving window: {stop['name']} reaches "
                f"{departure.isoformat()} after the {cutoff} local cutoff. "
                "Choose an earlier departure, an earlier overnight, or explicitly allow later driving.",
                422,
            )
        if final and seconds_until(arrival, policy.deadline(travel_day, zone)) < 0:
            stop["warning"] = (
                "Final destination arrival is after the normal hotel cutoff; plan for a late arrival."
            )
        stop.update(
            arrival_time=arrival.isoformat(),
            travel_day=travel_day.isoformat(),
            deadline=deadline.isoformat(),
        )
        if stop["type"] == "hotel":
            departure = policy.restart(travel_day, zone)
            if policy.daily_schedule:
                if validate_quotes:
                    validate_stored_stay(stop, arrival, departure)
            else:
                stop.pop("lodging", None)
                booked = stop.get("check_in_date")
                if booked and booked != travel_day.isoformat():
                    raise PlanningError(
                        "Final detour changed the dated hotel stay; replan the overnight", 422
                    )
                stop["check_in_date"] = travel_day.isoformat()
            if seconds_until(arrival, departure) <= 0:
                raise PlanningError(
                    "Hotel arrival leaves no time before the chosen morning restart", 422
                )
            if (
                arrival.strftime("%H:%M") > policy.latest_hotel_arrival
                or arrival.date() > travel_day
            ):
                stop["late_check_in_notice"] = "Confirm late check-in with the hotel"
            blocks = (
                rest_blocks(arrival, departure, policy.daily_schedule)
                if policy.daily_schedule
                else None
            )
            if clock:
                awake_intervals = (
                    [
                        (
                            datetime.fromisoformat(b["arrival_time"]),
                            datetime.fromisoformat(b["departure_time"]),
                        )
                        for b in blocks
                        if b["kind"] == "rest"
                    ]
                    if blocks is not None
                    else None
                )
                clock.rest(arrival, departure, zone, awake_intervals=awake_intervals)
            if blocks is not None:
                stop["daily_rhythm_blocks"] = blocks
                if "lodging" not in stop:
                    stop["check_in_timing_notice"] = (
                        "Planned rest; confirm hotel check-in and checkout times."
                    )
            travel_day = policy.travel_day_for(departure)
        if clock:
            stop["meal_breaks"] = deepcopy(clock.breaks[meal_index:])
        stop["departure_time"] = departure.isoformat()
        now = departure
