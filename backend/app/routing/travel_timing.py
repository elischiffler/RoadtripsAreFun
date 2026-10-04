"""The actual-leg clock shared by final reroute validation and itinerary display."""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.scheduling_policy import SchedulingPolicy, advance, local_time, seconds_until
from app.routing.base import PlanningError


def apply_timing(
    stops, start: datetime, policy: SchedulingPolicy, start_timezone: str | None = None
):
    now = start
    if start_timezone:
        zone = ZoneInfo(start_timezone)
        now = local_time(start, zone)
    travel_day = now.date()
    for stop in stops:
        duration = stop["duration"]
        if not math.isfinite(duration) or duration < 0:
            raise PlanningError("Mapbox returned an invalid leg duration", 502)
        zone = ZoneInfo(stop["timezone"]) if stop.get("timezone") else now.tzinfo
        arrival = advance(now, duration)
        if zone is not None:
            arrival = arrival.astimezone(zone)
        final = stop["type"] == "end"
        cutoff = policy.arrival_cutoff(final=final)
        deadline = policy.deadline(travel_day, zone, final=final)
        departure = advance(arrival, 7200) if stop["type"] == "stop" else arrival
        if seconds_until(departure, deadline) < -1e-6:
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
            booked = stop.get("check_in_date")
            if booked and booked != travel_day.isoformat():
                raise PlanningError(
                    "Final detour changed the dated hotel stay; replan the overnight", 422
                )
            stop["check_in_date"] = travel_day.isoformat()
            departure = policy.restart(travel_day, zone)
            if seconds_until(arrival, departure) <= 0:
                raise PlanningError(
                    "Hotel arrival leaves no time before the chosen morning restart", 422
                )
            if (
                arrival.strftime("%H:%M") > policy.latest_hotel_arrival
                or arrival.date() > travel_day
            ):
                stop["late_check_in_notice"] = "Confirm late check-in with the hotel"
            travel_day = departure.date()
        stop["departure_time"] = departure.isoformat()
        now = departure
