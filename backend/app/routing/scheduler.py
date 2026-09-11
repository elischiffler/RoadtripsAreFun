"""Shared day-by-day trip scheduler.

This is the *scheduling* half of route planning, factored out of the greedy
planner so every algorithm schedules identically and planners differ only in
*selection* (which attractions to visit).

Scheduling = walking the initial single-leg route in simulated time, and at each
step deciding whether to end the day at an overnight hotel or stop for an
attraction. The daily driving window, the ~2h attraction detour, the hotel retry
loop, and the running cost/price-range updates all live here.

The one thing that varies between algorithms is *which attraction goes at a given
segment boundary*. That is abstracted behind a ``StopProvider``:

* The greedy planner passes the live ``services.find_stop`` — so it discovers the
  best nearby attraction on the fly, exactly as before (this function is a
  verbatim extraction of the former ``_add_stops``, so greedy's output is
  unchanged).
* The OR-Tools planner passes a provider that returns its pre-selected
  attractions in order, ignoring the search coordinates — so its knapsack-chosen
  set is scheduled by this same loop.

Because the loop is identical, the only difference in the produced trips is the
attraction set, which is exactly what a fair benchmark should isolate.
"""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Any, Callable

from fastapi import HTTPException

from app.models.routing_models.routing_models import MapBox
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route

# Same shape as services.find_stop: (category, lat, lon, radius) -> attraction dict.
# Raising HTTPException(404) signals "no attraction here" and triggers the same
# radius-doubling retry the greedy algorithm has always used.
StopProvider = Callable[[str, float, float, int], Awaitable[dict[str, Any]]]


async def schedule_route(
    route: MapBox_route,
    num_stops: int,
    date: datetime,
    budget: float,
    daily_start: int,
    daily_end: int,
    services: RoutingServices,
    stop_provider: StopProvider,
) -> tuple[list[dict[str, Any]], float]:
    """Walk ``route`` in simulated time, inserting attractions and hotels.

    This is the exact loop the greedy planner used (formerly ``_add_stops``); the
    only change is that the attraction lookup goes through ``stop_provider``
    instead of a hard-coded ``services.find_stop`` call.

    Args:
        route: The raw single-leg initial route.
        num_stops: Number of attraction stops to place.
        date: Trip start datetime.
        budget: Total hotel budget.
        daily_start / daily_end: Daily driving window (hours).
        services: Injected sourcing/geometry/pricing helpers (hotels + position + pricing).
        stop_provider: Supplies the attraction for a given segment boundary.

    Returns:
        ``(stopping_points, total_cost)`` — the ordered stops and summed hotel cost.
    """
    stopping_points = []
    interval = route.duration / (
        num_stops + 1
    )  # Divide trip up into segments for finding stops in seconds
    # Stop looking for hotels if within the last 4 hours of the trip (Latest you could get there is 8pm)
    end_hotel_search = route.duration - 3600 * 4
    end_stop_search = (
        route.duration - 1800
    )  # Stop looking for attractions within the last 30 minutes of trip
    current_time = date.hour * 3600  # Initialize the current time of the day in seconds
    steps = route.legs[0].steps  # Only one leg in the initial route
    coordinates = route.geometry.coordinates  # Get all coordinates of the route
    current_day = 1  # Initialize number of days in route
    total_time = 0  # Total time traveled to the destination
    time_till_stop = interval  # Track the time until next stop
    driving_interval = daily_end - daily_start

    price_range = services.get_price_range(
        remaining_budget=budget,  # Get an initial price range for the hotels
        duration_left=route.duration,
        stops_left=num_stops,
        daily_drive_time=driving_interval,
    )
    total_cost = 0  # Initialize value to track cost

    # Add stopping places until the trip is over
    for _ in range(num_stops + 1):
        # Check whether the daily end or the next stop comes first
        while total_time < end_hotel_search and current_time + time_till_stop >= (daily_end * 3600):
            time_traveled = (daily_end * 3600) - current_time  # Calculate time traveled that day
            # If you just finished a stop and the time is later than the daily_end look for hotel at current location
            if time_traveled < 0:
                time_traveled = 0
            total_time += time_traveled  # Add the time traveled toward the next stop that day
            date += timedelta(seconds=time_traveled)
            time_till_stop -= (
                time_traveled  # Remove the amount of time traveled in the day from time to the stop
            )
            hotel_lat, hotel_lon = services.find_position(
                coordinates, steps, total_time
            )  # figure out the location at 5PM
            attempts = 12  # 12 attempts (6 hours) to find a hotel before raising an error
            while attempts > 0:
                try:
                    stopping_points.append(
                        await services.find_hotel(hotel_lat, hotel_lon, price_range, date)
                    )  # Append a found hotel
                    break
                except HTTPException as exception:
                    if exception.status_code == 404:  # Handle a not found error occurring
                        attempts -= 1  # subtract an attempt
                        if attempts == 0:
                            raise exception  # Raise an error after 3 tries
                        total_time += 1800  # Increase total drive time by 30 minutes
                        time_till_stop -= 1800  # Decrease time till stop by 30 minutes
                        date += timedelta(seconds=1800)  # Increase the datetime
                        current_time += 1800
                        hotel_lat, hotel_lon = services.find_position(
                            coordinates, steps, total_time
                        )  # Find the new position after driving
                    else:
                        raise exception
            total_cost += stopping_points[-1]["price"]  # Add the cost of the hotel to the total
            # Recalculate a price range for the next hotel
            price_range = services.get_price_range(
                remaining_budget=budget - total_cost,
                duration_left=route.duration - total_time,
                stops_left=num_stops,
                daily_drive_time=driving_interval,
            )
            current_day += 1  # increment the days that have passed
            current_time = (
                3600 * daily_start
            )  # set the current time to be the desired start time the next day
            date = (date + timedelta(days=1)).replace(
                hour=daily_start, minute=0, second=0, microsecond=0
            )  # New day

        # Ensure we are within the route duration and not looking past 9 pm for a stop
        if (
            (total_time + time_till_stop < end_stop_search)
            and current_time < (21 * 3600)
            and num_stops > 0
        ):
            total_time += time_till_stop  # Increment the total time by time traveled to stop
            current_time += time_till_stop + (
                3600 * 2
            )  # Current time includes distance and time spent at stop
            date += timedelta(
                hours=2, seconds=time_till_stop
            )  # Allocate two hours detours per stop/ increment for the time to drive to the location
            time_till_stop = interval  # Reset the time to the next stop
            attempts = 2  # 2 attempts before raising an error to find a stop to limit API calls
            search_radius = 30  # Set the attraction search radius in miles
            while attempts > 0:
                try:
                    current_lat, current_lon = services.find_position(
                        coordinates, steps, total_time
                    )  # Find the next stop position
                    stopping_points.append(  # Add the stop to the list
                        await stop_provider("attractions", current_lat, current_lon, search_radius)
                    )
                    break  # Exit the loop
                except HTTPException as exception:
                    if exception.status_code == 404:
                        attempts -= 1
                        if attempts == 0:
                            raise exception
                        search_radius += search_radius  # Double the search radius
                        total_time += 3600  # Redo the search an hour later
                        # Decrement the time until the next stop by an hour (next stop comes sooner)
                        time_till_stop -= 3600
                        date += timedelta(seconds=3600)  # Increase the datetime
                        current_time += 3600  # Increment the current time counter
                    else:
                        raise exception
            num_stops -= 1  # Decrement the number of stops
    return stopping_points, total_cost
