"""Attraction discovery via the TripAdvisor Content API.

``find_stop`` is the per-point lookup the greedy planner uses. ``gather_candidates``
is the batch corridor collection the optimizer planners use — it samples points
along the route and pulls one attraction near each, tagging every candidate with
its along-route ``elapsed_time`` so a scheduler can place it later.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi import HTTPException
from geopy.distance import geodesic
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.models.routing_models.routing_models import MapBox
from app.models.routing_models.trip_advisor_models import (
    Trip_Advisor_Information,
    Trip_Advisor_Location_Search,
)
from app.routing import config
from app.routing.geometry import find_position

MapBox_route = MapBox.MapBox_Route

logger = logging.getLogger(__name__)

_REFERER = "https://rp-routing.onrender.com/"


async def find_stop(category: str, lat: str, lon: str, radius: int) -> dict[str, Any]:
    """
    Finds a nearby location of a specific category using the TripAdvisor API and returns its coordinates.

    Parameters:
    - category (str): Category of the location to search for (e.g., 'attractions').
    - lat (str): Latitude of the search location.
    - lon (str): Longitude of the search location.
    - radius (str): Search radius in miles.

    Returns:
    - Dict[str, Any]: Details of an attraction with a name and location.

    Raises:
    - HTTPException: For errors related to TripAdvisor requests or response processing.
    """
    nearby_search_url = "https://api.content.tripadvisor.com/api/v1/location/nearby_search"
    params = {
        "latLong": f"{lat}%2C{lon}",
        "key": config.TRIPADVISOR_API,
        "category": category,
        "radius": radius,
        "radiusUnit": "mi",
        "language": "en",
    }

    headers = {"Referer": _REFERER}

    try:
        response = requests.get(
            nearby_search_url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT
        )
        json_data = response.json()
        locations = Trip_Advisor_Location_Search.model_validate(json_data)
        lowest_rank = 999  # Set to be unrealistically high
        ideal_stop = None
        if len(locations.data) > 0:
            for location in locations.data:
                location_id = location.location_id
                rank, details = await get_details(location_id)
                # Check to see if a lower ranked
                if rank < lowest_rank:
                    lowest_rank = rank
                    ideal_stop = details
                if rank == 1:  # End loop early if highest rank is found
                    break
            if ideal_stop is not None:
                # Record the winning popularity rank on the returned stop so batch
                # callers (gather_candidates -> the knapsack objective) can weight
                # by it. The greedy planner simply ignores this extra key.
                ideal_stop["rank"] = lowest_rank
                return ideal_stop
        raise HTTPException(status_code=404, detail="No locations found")
    except RequestException as exception:
        # Log the full exception for debugging, but never surface str(exception) to
        # the client: it can contain the request URL, which carries the TripAdvisor
        # API key as a query param.
        logger.error("find_stop: TripAdvisor request failed: %s", exception)
        raise HTTPException(status_code=502, detail="TripAdvisor request failed")
    except ValidationError as exception:
        logger.error("find_stop: improper TripAdvisor response: %s", exception)
        raise HTTPException(status_code=502, detail="Improper TripAdvisor response")


async def get_details(location_id: str) -> tuple[int, dict[str, Any]]:
    """
    Retrieves detailed information about a location from the TripAdvisor API using its location ID.

    Parameters:
    - location_id (str): The ID of the location to retrieve details for.

    Returns:
    - Tuple[int, Dict[str, Any]]: The popularity rank and details of an attraction.

    Raises:
    - HTTPException: For errors related to TripAdvisor requests or response processing.

    """
    location_details_url = (
        f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/details"
    )
    params = {"key": config.TRIPADVISOR_API, "language": "en", "currency": "USD"}

    headers = {"Referer": _REFERER}

    response = requests.get(
        location_details_url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT
    )
    json_data = response.json()
    details = Trip_Advisor_Information.model_validate(json_data)

    try:
        lat = details.latitude
        lon = details.longitude
        name = details.name
        url = details.web_url
        address = details.address_obj.address_string
        ranking = details.ranking_data
        if ranking is not None:
            rank = int(ranking.ranking)
        else:
            rank = 999  # Rank is unrealistically high
        return rank, {
            "coordinates": [lat, lon],
            "name": name,
            "type": "stop",
            "url": url,
            "address": address,
        }
    # Catch any attributes that were not returned values and send back an empty response
    except AttributeError:
        return 999, {}


async def gather_candidates(
    route: MapBox_route, num_candidates: int, radius: int = 30
) -> list[dict[str, Any]]:
    """Collect attraction candidates evenly along the route corridor.

    Samples ``num_candidates`` points along the route (by elapsed drive time) and
    pulls the best-ranked attraction near each, skipping points where none is
    found. Each returned candidate carries an ``elapsed_time`` (seconds from the
    start) so an optimizer/scheduler can place it in time.

    Args:
        route: The raw single-leg initial route.
        num_candidates: How many evenly-spaced points to sample.
        radius: Search radius in miles per point.

    Returns:
        A list of attraction dicts (possibly shorter than ``num_candidates``),
        each augmented with an ``elapsed_time`` key.
    """
    if num_candidates <= 0:
        return []

    steps = route.legs[0].steps
    coordinates = route.geometry.coordinates
    duration = route.duration
    # Sample interior points at even fractions, avoiding the exact endpoints.
    interval = duration / (num_candidates + 1)

    candidates: list[dict[str, Any]] = []
    for i in range(1, num_candidates + 1):
        elapsed = interval * i
        lat, lon = find_position(coordinates, steps, elapsed)
        try:
            candidate = await find_stop("attractions", lat, lon, radius)
        except HTTPException as exception:
            if exception.status_code == 404:
                continue  # No attraction near this point; skip it.
            raise
        candidate["elapsed_time"] = elapsed
        # Attach a cheap off-route detour estimate (a geodesic proxy, no extra API
        # call): the straight-line distance from the on-route sample point to the
        # attraction, doubled for the out-and-back leg. It is only an approximation
        # of true driving detour, but it is monotonic with it — enough for a solver
        # to prefer closer stops and drop far ones under a detour budget. A future
        # pass can replace this with a real Mapbox re-route cost behind the same key.
        candidate["detour_meters"] = _detour_proxy_meters(
            (lat, lon), candidate.get("coordinates")
        )
        candidates.append(candidate)
    return candidates


def _detour_proxy_meters(
    route_point: tuple[float, float], attraction_coords: list[float] | None
) -> float:
    """Out-and-back geodesic detour proxy in meters.

    ``route_point`` is ``(lat, lon)`` on the driven line; ``attraction_coords`` is
    the attraction's own ``[lat, lon]``. Returns twice the straight-line distance
    (leave the route and rejoin). Returns ``0.0`` when coordinates are missing so a
    candidate without a usable location isn't penalized arbitrarily.
    """
    if not attraction_coords or len(attraction_coords) < 2:
        return 0.0
    try:
        one_way = geodesic(
            (route_point[0], route_point[1]),
            (attraction_coords[0], attraction_coords[1]),
        ).meters
    except (ValueError, TypeError):
        return 0.0
    return 2.0 * one_way
