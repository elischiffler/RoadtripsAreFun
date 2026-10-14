"""Compatibility adapter for legacy planners using the versioned places catalog."""

from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from app.catalog import repository
from app.models.routing_models.routing_models import MapBox
from app.routing.geometry import find_position
from app.routing.run_metrics import increment
from app.routing.runtime import threaded

MapBox_route = MapBox.MapBox_Route


async def find_stop(category: str, lat: str, lon: str, radius: int) -> dict[str, Any]:
    """Return a nearby catalog attraction; radius is bounded at five miles.

    Rank reflects deterministic catalog order, not popularity or live reviews.
    Historical saved stops remain readable; unused provider-ID refresh is retired.
    """
    if category.lower() not in {"attraction", "attractions"}:
        raise HTTPException(400, "Only catalog attractions are supported")
    try:
        distance = float(radius)
        point = [float(lat), float(lon)]
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid catalog search") from None
    increment("catalog")
    try:
        records = await threaded(
            "catalog", repository.nearby, point, ["daytime"], radius_miles=min(distance, 5), limit=1
        )
    except Exception:
        raise HTTPException(503, "Places catalog lookup unavailable") from None
    if not records:
        raise HTTPException(404, "No catalog locations found")
    return {**records[0], "type": "stop", "rank": 1}


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
        radius: Search radius in miles per point (clamped to five miles).

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
