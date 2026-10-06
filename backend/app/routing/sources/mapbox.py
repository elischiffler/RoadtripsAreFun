"""Asynchronous live Directions adapter; attempts and permits are per HTTP call."""

import httpx

from app.agent.progress import stage
from app.agent.provider_diagnostics import retry_async
from app.models.routing_models.routing_models import MapBox
from app.routing import config
from app.routing.run_metrics import increment
from app.routing.runtime import http_get, in_run, limited, singleflight

MapBox_route = MapBox.MapBox_Route


class UnusableRoadRoute(ValueError):
    public_message = "Mapbox could not find a usable road route for this location"
    retryable = False


@in_run
async def call_route(start_lat, start_lon, end_lat, end_lon, waypoints=None) -> MapBox_route:
    coordinates = f"{start_lon},{start_lat}"
    if waypoints:
        coordinates += f";{waypoints}"
    coordinates += f";{end_lon},{end_lat}"
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coordinates}"
    params = {
        "alternatives": "false",
        "geometries": "geojson",
        "language": "en",
        "overview": "full",
        "steps": "true",
        "access_token": config.MAPBOX_API,
    }

    async def request():
        async def attempt():
            with stage("mapbox.request"):
                increment("mapbox")
                response = await http_get(url, params=params, timeout=config.HTTP_TIMEOUT)
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") in ("NoRoute", "NoSegment"):
                    raise UnusableRoadRoute()
                data = MapBox.model_validate(payload)
                if not data.routes:
                    raise UnusableRoadRoute()
                return data.routes[0]

        return await retry_async(lambda: limited("mapbox", attempt))

    return await singleflight(("mapbox", coordinates), request)


__all__ = ["call_route", "UnusableRoadRoute", "httpx"]
