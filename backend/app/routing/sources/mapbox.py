"""Mapbox Directions API client.

The only place a driving route is fetched. Both the initial (no-waypoint) route
and the final re-route through chosen stops go through :func:`call_route`.
"""

from __future__ import annotations

import requests

from app.models.routing_models.routing_models import MapBox
from app.routing import config

MapBox_route = MapBox.MapBox_Route


async def call_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float, waypoints: str = None
) -> MapBox_route:
    """
    Calls the Mapbox Directions API to get a route between start and end points, optionally including waypoints.

    Parameters:
    - start_lat (float): Latitude of the starting point.
    - start_lon (float): Longitude of the starting point.
    - end_lat (float): Latitude of the destination point.
    - end_lon (float): Longitude of the destination point.
    - waypoints (str, optional): Semicolon-separated list of waypoints to include in the route.

    Returns:
    - MapBox_route: The route object containing route details.

    Raises:
    - HTTPException: For errors related to the Mapbox API request or response.
    """
    call_route_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat}"
    if waypoints:
        call_route_url += f";{waypoints}"
    call_route_url += f";{end_lon},{end_lat}"
    params = {
        "alternatives": "false",
        "geometries": "geojson",
        "language": "en",
        "overview": "full",
        "steps": "true",
        "access_token": config.MAPBOX_API,
    }

    response = requests.get(call_route_url, params=params)
    json_data = response.json()
    data = MapBox.model_validate(json_data)
    route = data.routes[
        0
    ]  # TODO can change the index for different routes (0 is recommended route)
    return route
