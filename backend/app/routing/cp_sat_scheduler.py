"""Drive-time scheduling for attractions assigned to CP-SAT query points."""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from geopy.distance import geodesic

from app.agent.progress import emit
from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route
_VISIT_SECONDS = 2 * 3600
_MAX_HOTEL_ATTEMPTS = 6
_RETRY_DRIVE_SECONDS = 1800
_MAX_HOTELS = 30
_MAX_OVERNIGHTS = 60


def _clock_seconds(value) -> float:
    return value.hour * 3600 + value.minute * 60 + value.second


def _usable_hotel(hotel: Any) -> bool:
    if not isinstance(hotel, dict):
        return False
    coords = hotel.get("coordinates")
    price = hotel.get("price")
    utility = hotel.get("utility")
    return (
        isinstance(hotel.get("provider_id"), str)
        and bool(hotel["provider_id"])
        and isinstance(hotel.get("name"), str)
        and bool(hotel["name"])
        and isinstance(coords, (list, tuple))
        and len(coords) == 2
        and all(isinstance(c, (float, int)) and math.isfinite(c) for c in coords)
        and -90 <= coords[0] <= 90
        and -180 <= coords[1] <= 180
        and isinstance(price, (float, int))
        and math.isfinite(price)
        and price >= 0
        and isinstance(utility, (float, int))
        and math.isfinite(utility)
        and 0 <= utility <= 1
    )


async def schedule_cp_sat_route(
    route: MapBox_route,
    selected: list[tuple[int, dict[str, Any]]],
    options: PlanOptions,
    services: RoutingServices,
) -> tuple[list[dict[str, Any]], float]:
    """Drive to each selected slot, ending days at provider-verified hotels."""
    if not 0 <= options.daily_start < options.daily_end <= 24:
        raise PlanningError("Invalid daily drive window", 400)
    if selected and options.daily_end - options.daily_start < 2:
        raise PlanningError("Daily window cannot fit a two-hour attraction visit", 400)
    now = options.start
    if not options.daily_start * 3600 <= _clock_seconds(now) < options.daily_end * 3600:
        raise PlanningError("Trip start must be within the daily drive window", 400)
    if services.cp_sat_hotels is None:
        raise PlanningError("CP-SAT verified hotel service is not configured", 503)

    query_count = min(30, max(6, 3 * options.num_stops)) if options.num_stops else 0
    events = [
        (route.duration * (index + 1) / (query_count + 1), candidate)
        for index, candidate in selected
    ]
    events.append((route.duration, None))
    elapsed = 0.0
    total_cost = 0.0
    stops: list[dict[str, Any]] = []
    overnights = 0
    coordinates = route.geometry.coordinates
    steps = route.legs[0].steps
    daily_seconds = options.daily_end * 3600

    for target, attraction in events:
        while True:
            drive_left = max(0.0, target - elapsed)
            visit = _VISIT_SECONDS if attraction is not None else 0
            available = daily_seconds - _clock_seconds(now)
            if drive_left + visit <= available + 1e-6:
                elapsed = target
                now += timedelta(seconds=drive_left + visit)
                if attraction is not None:
                    stops.append(
                        {
                            "provider_id": attraction["provider_id"],
                            "name": attraction["name"],
                            "type": "stop",
                            "coordinates": list(attraction["coordinates"]),
                            "address": attraction.get("address"),
                            "url": attraction.get("url"),
                        }
                    )
                break

            # Drive as far as the next selected slot permits before searching
            # backward along this day's segment for a usable overnight stay.
            if overnights >= _MAX_OVERNIGHTS:
                raise PlanningError("CP-SAT trip exceeds the overnight limit", 400)
            segment_start = elapsed
            drive_today = min(max(available, 0.0), drive_left)
            overnight_elapsed = elapsed + drive_today
            overnight_time = now + timedelta(seconds=drive_today)
            remaining_stops = sum(item is not None for _, item in events if _ >= target)
            price_range = services.get_price_range(
                remaining_budget=options.budget - total_cost,
                duration_left=max(0.0, route.duration - overnight_elapsed),
                stops_left=remaining_stops,
                daily_drive_time=options.daily_end - options.daily_start,
            )

            hotel = None
            for attempt in range(_MAX_HOTEL_ATTEMPTS):
                trial_elapsed = max(
                    segment_start, overnight_elapsed - attempt * _RETRY_DRIVE_SECONDS
                )
                position = services.find_position(coordinates, steps, trial_elapsed)
                check_in = (
                    overnight_time - timedelta(seconds=overnight_elapsed - trial_elapsed)
                ).date()
                emit("route.overnight", "started", day=overnights + 1, attempt=attempt + 1)
                try:
                    candidates = await services.cp_sat_hotels(
                        position, check_in, price_range, options.weights or {}
                    )
                except HTTPException as exc:
                    if exc.status_code != 404:
                        raise
                    candidates = []
                if not isinstance(candidates, list) or len(candidates) > _MAX_HOTELS:
                    raise PlanningError("Verified hotel candidate limit exceeded", 502)
                emit(
                    "route.overnight",
                    day=overnights + 1,
                    attempt=attempt + 1,
                    candidates=len(candidates),
                )
                usable = [item for item in candidates if _usable_hotel(item)]
                if usable:
                    max_price = options.budget
                    hotel = min(
                        usable,
                        key=lambda item: (
                            item["price"] > max_price,
                            -item["utility"],
                            item["price"],
                            geodesic(item["coordinates"], position).meters,
                            item["provider_id"],
                        ),
                    )
                    elapsed = trial_elapsed
                    break
                if trial_elapsed == segment_start:
                    break
            if hotel is None:
                raise PlanningError("No verified hotel is available for an overnight stop", 404)
            stops.append(
                {
                    "provider_id": hotel["provider_id"],
                    "name": hotel["name"],
                    "type": "hotel",
                    "coordinates": list(hotel["coordinates"]),
                    "address": hotel.get("address"),
                    "url": hotel.get("url"),
                    "price": hotel["price"],
                    **(
                        {
                            "warning": f"Hotel {hotel['name']} costs ${hotel['price']:.0f}, above the ${options.budget:.0f} nightly target."
                        }
                        if hotel["price"] > options.budget
                        else {}
                    ),
                }
            )
            total_cost += hotel["price"]
            overnights += 1
            now = (overnight_time + timedelta(days=1)).replace(
                hour=options.daily_start, minute=0, second=0, microsecond=0
            )
    return stops, total_cost
