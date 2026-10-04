"""Drive-time scheduling for attractions assigned to CP-SAT query points."""

from __future__ import annotations

import math
from datetime import UTC
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from geopy.distance import geodesic

from app.agent.progress import emit
from app.models.routing_models.routing_models import MapBox
from app.models.scheduling_policy import advance, local_time, seconds_until
from app.routing.base import PlanningError, PlanOptions
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route
_VISIT_SECONDS = 2 * 3600
_MAX_HOTEL_ATTEMPTS = 6
_RETRY_DRIVE_SECONDS = 1800
_MAX_HOTELS = 30
_MAX_OVERNIGHTS = 60


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
    """Prefer hotels around the target, retaining every selected daytime stop.

    Initial corridor times are estimates. Final Mapbox legs must pass the same
    local deadline before this plan can be returned to the traveler.
    """
    policy = options.scheduling_policy
    now = options.start
    coordinates, steps = route.geometry.coordinates, route.legs[0].steps

    async def zone_at(position):
        if services.timezone_at is not None:
            return ZoneInfo(await services.timezone_at(list(position)))
        # Injected offline services/benchmarks may use a fixed fixture clock.
        # Live services always supply a provider-backed IANA resolver.
        return now.tzinfo or UTC

    start_zone = await zone_at([coordinates[0][1], coordinates[0][0]])
    now = local_time(now, start_zone)
    travel_day = now.date()
    if seconds_until(now, policy.deadline(travel_day, start_zone)) <= 0:
        raise PlanningError("Departure must precede the chosen local driving cutoff", 400)
    if services.cp_sat_hotels is None:
        raise PlanningError("CP-SAT verified hotel service is not configured", 503)

    query_count = min(30, max(6, 3 * options.num_stops)) if options.num_stops else 0
    events = [
        (route.duration * (index + 1) / (query_count + 1), candidate)
        for index, candidate in selected
    ]
    events.append((route.duration, None))
    elapsed, total_cost, overnights = 0.0, 0.0, 0
    stops = []
    end_zone = await zone_at([coordinates[-1][1], coordinates[-1][0]])

    for event_index, (target, attraction) in enumerate(events):
        while True:
            drive_left = max(0.0, target - elapsed)
            visit = _VISIT_SECONDS if attraction is not None else 0
            position = (
                attraction["coordinates"]
                if attraction
                else [coordinates[-1][1], coordinates[-1][0]]
            )
            event_zone = await zone_at(position)
            remaining_visits = sum(item is not None for _, item in events[event_index:])
            finish_seconds = route.duration - elapsed + remaining_visits * _VISIT_SECONDS
            can_finish = (
                finish_seconds <= seconds_until(now, policy.deadline(travel_day, end_zone)) + 1e-6
            )
            event_limit = (
                policy.deadline(travel_day, event_zone)
                if can_finish
                else policy.at(travel_day, policy.preferred_hotel_arrival, event_zone)
            )
            if drive_left + visit <= seconds_until(now, event_limit) + 1e-6:
                elapsed = target
                now = advance(now, drive_left + visit).astimezone(event_zone)
                if attraction is not None:
                    stops.append(
                        {
                            "provider_id": attraction["provider_id"],
                            "name": attraction["name"],
                            "type": "stop",
                            "coordinates": list(attraction["coordinates"]),
                            "address": attraction.get("address"),
                            "url": attraction.get("url"),
                            "timezone": getattr(event_zone, "key", None),
                        }
                    )
                break

            if overnights >= _MAX_OVERNIGHTS:
                raise PlanningError("CP-SAT trip exceeds the overnight limit", 400)
            segment_start = elapsed
            # Refine the target using its actual local zone before bounded searches.
            preferred_drive = max(
                0.0,
                seconds_until(
                    now, policy.at(travel_day, policy.preferred_hotel_arrival, now.tzinfo)
                ),
            )
            for _ in range(3):
                trial = min(drive_left, preferred_drive)
                position = services.find_position(coordinates, steps, elapsed + trial)
                zone = await zone_at(position)
                preferred_drive = max(
                    0.0,
                    seconds_until(now, policy.at(travel_day, policy.preferred_hotel_arrival, zone)),
                )
            base_drive = min(drive_left, preferred_drive)
            price_range = services.get_price_range(
                remaining_budget=options.budget - total_cost,
                duration_left=max(0.0, route.duration - elapsed - base_drive),
                stops_left=remaining_visits,
                daily_drive_time=seconds_until(
                    policy.at(travel_day, policy.morning_restart, zone),
                    policy.deadline(travel_day, zone),
                )
                / 3600,
            )
            hotel = None
            tried = set()
            # Include the hard cutoff as an availability fallback, while keeping
            # six searches and the original 2.5h earlier fallback.
            cutoff_offset = seconds_until(now, policy.deadline(travel_day, zone)) - base_drive
            for offset in (0, -1800, 1800, -3600, cutoff_offset, -9000):
                trial_drive = min(drive_left, max(0.0, base_drive + offset))
                trial_elapsed = segment_start + trial_drive
                if trial_elapsed in tried:
                    continue
                tried.add(trial_elapsed)
                position = services.find_position(coordinates, steps, trial_elapsed)
                zone = await zone_at(position)
                arrival = advance(now, trial_drive).astimezone(zone)
                if seconds_until(arrival, policy.deadline(travel_day, zone)) < -1e-6:
                    continue
                attempt = len(tried)
                emit("route.overnight", "started", day=overnights + 1, attempt=attempt)
                try:
                    candidates = await services.cp_sat_hotels(
                        position, travel_day, price_range, options.weights or {}
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
                    attempt=attempt,
                    candidates=len(candidates),
                )
                usable = []
                for item in candidates:
                    if not _usable_hotel(item):
                        continue
                    # Live source verifies the requested dated offer. Also guard
                    # adapters that supply a different explicit booking date.
                    if (
                        item.get("check_in_date")
                        and str(item["check_in_date"]) != travel_day.isoformat()
                    ):
                        continue
                    hotel_zone = await zone_at(item["coordinates"])
                    if (
                        seconds_until(
                            advance(now, trial_drive), policy.deadline(travel_day, hotel_zone)
                        )
                        >= -1e-6
                    ):
                        usable.append((item, hotel_zone))
                if usable:
                    hotel, zone = min(
                        usable,
                        key=lambda pair: (
                            pair[0]["price"] > options.budget,
                            -pair[0]["utility"],
                            pair[0]["price"],
                            geodesic(pair[0]["coordinates"], position).meters,
                            pair[0]["provider_id"],
                        ),
                    )
                    arrival = advance(now, trial_drive).astimezone(zone)
                    elapsed = trial_elapsed
                    break
            if hotel is None:
                raise PlanningError(
                    "No verified hotel is available near the preferred arrival within the local cutoff; try an earlier departure or a different overnight area",
                    404,
                )
            stops.append(
                {
                    "provider_id": hotel["provider_id"],
                    "name": hotel["name"],
                    "type": "hotel",
                    "coordinates": list(hotel["coordinates"]),
                    "address": hotel.get("address"),
                    "url": hotel.get("url"),
                    "price": hotel["price"],
                    "timezone": getattr(zone, "key", None),
                    "check_in_date": travel_day.isoformat(),
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
            now = policy.restart(travel_day, zone)
            if seconds_until(arrival, now) <= 0:
                raise PlanningError(
                    "Hotel arrival leaves no time before the chosen morning restart", 422
                )
            travel_day = now.date()
    return stops, total_cost
