"""Attraction discovery via the Tripadvisor **Terra** Partner API.

Terra replaced the deprecated Content API. The key differences this module
absorbs so the rest of the routing layer is unaffected:

* Base URL ``terra.tripadvisor.com/api`` (the old ``api.content.tripadvisor.com``
  host no longer resolves) and header auth (``X-API-Key``) instead of a ``key``
  query param.
* ``GET /locations/nearby`` returns the *full* Location inline, so ``find_stop``
  no longer needs a per-result details fanout — one call gives name,
  coordinates, address, and url. This is both simpler and far fewer API calls.
* Terra has no per-location popularity *rank* integer; results come pre-sorted by
  rating (``sort=rating,desc``). ``find_stop`` therefore derives the ``rank`` key
  downstream depends on from the result's position (1 = best), preserving the
  "lower is better" semantics of the objective/knapsack.
* Terra caps the nearby radius at 5 miles; requested radii are clamped.

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
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.models.routing_models.routing_models import MapBox
from app.models.routing_models.trip_advisor_models import (
    Terra_Location,
    Terra_Page_Nearby_Location,
)
from app.routing import config
from app.routing.geometry import find_position

MapBox_route = MapBox.MapBox_Route

logger = logging.getLogger(__name__)


def _auth_headers() -> dict[str, str]:
    """Standard Terra request headers: header-based API key + JSON accept."""
    return {
        config.TRIPADVISOR_API_KEY_HEADER: config.TRIPADVISOR_API or "",
        "accept": "application/json",
    }


def _clamp_radius(radius: float) -> float:
    """Clamp a requested radius (miles) to Terra's 5-mile nearby-search ceiling.

    The old Content API accepted 25-30mi; Terra rejects anything over 5.0 with a
    400 constraint violation, so we cap rather than let the request fail.
    """
    try:
        value = float(radius)
    except (TypeError, ValueError):
        return config.TRIPADVISOR_MAX_RADIUS_MI
    return min(value, config.TRIPADVISOR_MAX_RADIUS_MI)


def _raise_for_status(response: requests.Response) -> None:
    """Turn a non-2xx Terra response into a clear HTTPException before parsing.

    Terra returns errors as ``application/problem+json`` with a 2xx-shaped body
    the (permissive) Location models would otherwise swallow into an empty result.
    Guarding here means an unauthorized key or a bad request surfaces a real error
    instead of a silent "no attraction found".

    * 401/403 -> a clear "key unauthorized" message. A dead/unauthorized key was
      the true root cause of the old generic 502 "Improper TripAdvisor response".
    * any other non-2xx -> a generic upstream 502. The response body is not echoed
      to the client (it can restate request params).
    """
    if 200 <= response.status_code < 300:
        return
    if response.status_code in (401, 403):
        logger.error(
            "Tripadvisor Terra auth failure (%s): key unauthorized", response.status_code
        )
        raise HTTPException(status_code=502, detail="TripAdvisor API key unauthorized")
    logger.error("Tripadvisor Terra request returned %s", response.status_code)
    raise HTTPException(status_code=502, detail="TripAdvisor request failed")


def _location_to_stop(location: Terra_Location) -> dict[str, Any] | None:
    """Map a Terra Location to the fixed stop-dict contract, or ``None`` if it
    lacks usable coordinates.

    The returned shape is exactly what the scheduler, itinerary endpoint, CRUD,
    and frontend expect: ``name``, ``type`` ("stop"), ``coordinates`` [lat, lon],
    plus ``url`` and ``address``. (``rank`` is stamped on by the caller.)
    """
    coords = location.coordinates
    if coords is None or coords.latitude is None or coords.longitude is None:
        return None
    return {
        "coordinates": [coords.latitude, coords.longitude],
        "name": location.primary_name(),
        "type": "stop",
        "url": location.web_url(),
        "address": location.formatted_address(),
    }


async def find_stop(category: str, lat: str, lon: str, radius: int) -> dict[str, Any]:
    """
    Finds a nearby location of a specific category using the Tripadvisor Terra API
    and returns it as a stop dict.

    Terra's nearby search returns the full Location inline and pre-sorted by rating
    (best first), so this makes a single request and takes the top result — no
    per-result details fanout as the old Content API required.

    Parameters:
    - category (str): Old-style category (e.g. 'attractions'); mapped to Terra's
      enum (ATTRACTION/RESTAURANT/HOTEL).
    - lat (str): Latitude of the search center.
    - lon (str): Longitude of the search center.
    - radius (int): Search radius in miles (clamped to Terra's 5-mile max).

    Returns:
    - Dict[str, Any]: An attraction stop dict (name, type, coordinates, url,
      address, rank).

    Raises:
    - HTTPException: 404 if no location is found; 502 for upstream/parse failures
      or an unauthorized key.
    """
    nearby_search_url = f"{config.TRIPADVISOR_BASE_URL}/locations/nearby"
    params = {
        "lat": lat,
        "lon": lon,
        "radius": _clamp_radius(radius),
        "unit": "MI",
        "category": config.TRIPADVISOR_CATEGORY_MAP.get(category.lower(), category),
        # Terra defaults to rating,desc, but be explicit so best-first ordering
        # (which we rely on to derive rank) is deterministic.
        "sort": "rating,desc",
    }
    headers = _auth_headers()

    try:
        response = requests.get(
            nearby_search_url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT
        )
        _raise_for_status(response)
        json_data = response.json()
        page = Terra_Page_Nearby_Location.model_validate(json_data)

        # Results are pre-sorted best-first, so walk in order and take the first
        # entry with usable coordinates. Its 1-based position becomes the ``rank``
        # (1 = best) that the objective/knapsack weights by.
        rank = 0
        for entry in page.data:
            if entry.location is None:
                continue
            rank += 1
            stop = _location_to_stop(entry.location)
            if stop is not None:
                stop["rank"] = rank
                return stop

        raise HTTPException(status_code=404, detail="No locations found")
    except RequestException as exception:
        # Log the full exception for debugging, but never surface str(exception) to
        # the client: it can contain the request URL and query params.
        logger.error("find_stop: Terra request failed: %s", exception)
        raise HTTPException(status_code=502, detail="TripAdvisor request failed")
    except ValidationError as exception:
        logger.error("find_stop: improper Terra response: %s", exception)
        raise HTTPException(status_code=502, detail="Improper TripAdvisor response")


async def get_details(location_id: str) -> tuple[int, dict[str, Any]]:
    """
    Retrieves a single location's details from the Tripadvisor Terra API by ID.

    Kept for direct by-id lookups and API compatibility. ``find_stop`` no longer
    calls this — Terra's nearby response already carries the full Location, so the
    old N+1 details fanout is gone.

    Parameters:
    - location_id (str): The Terra Location ID to retrieve.

    Returns:
    - Tuple[int, Dict[str, Any]]: A popularity rank (from ``rankings`` when
      present, else a neutral fallback) and the stop dict. Returns
      ``(999, {})`` if the location lacks usable coordinates.

    Raises:
    - HTTPException: 502 for upstream/parse failures or an unauthorized key.
    """
    location_details_url = f"{config.TRIPADVISOR_BASE_URL}/locations/{location_id}"
    # ``locale`` is optional and, when sent, must be a full locale (e.g. "en-US")
    # not a bare language ("en" 400s). Omit it and let Terra use its default locale,
    # matching the nearby call.
    headers = _auth_headers()

    try:
        response = requests.get(
            location_details_url, headers=headers, timeout=config.HTTP_TIMEOUT
        )
        _raise_for_status(response)
        json_data = response.json()
        location = Terra_Location.model_validate(json_data)
    except RequestException as exception:
        logger.error("get_details: Terra request failed: %s", exception)
        raise HTTPException(status_code=502, detail="TripAdvisor request failed")
    except ValidationError as exception:
        logger.error("get_details: improper Terra response: %s", exception)
        raise HTTPException(status_code=502, detail="Improper TripAdvisor response")

    stop = _location_to_stop(location)
    if stop is None:
        # Rank is unrealistically high so a coordinate-less result never wins.
        return 999, {}

    # Terra rarely populates ``rankings``; use it when present, else a neutral rank.
    rank = 999
    if location.rankings:
        for ranking in location.rankings:
            if isinstance(ranking.rank, int) and ranking.rank > 0:
                rank = ranking.rank
                break
    stop["rank"] = rank
    return rank, stop


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
        radius: Search radius in miles per point (clamped to Terra's max).

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
        candidates.append(candidate)
    return candidates
