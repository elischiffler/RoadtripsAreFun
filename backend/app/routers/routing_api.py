"""Routing HTTP endpoints (thin controller).

This router owns only the two HTTP endpoints and response assembly. The actual
route-planning *algorithm* lives behind the pluggable planner layer in
``app.routing`` (selected by name), and all external-API candidate sourcing lives
in ``app.routing.sources``. This module's job is to:

1. call Mapbox for the initial / final route,
2. build a :class:`RoutingServices` bundle,
3. pick a planner and run it,
4. shape the result into the :class:`Route` response.

Candidate-sourcing functions are re-exported at module level (``get_location``,
``find_google_hotels``, ``_get_nearby_city``, ``_find_hotel``,
``_get_amadeus_token``, ``requests``) so existing tests that patch
``app.routers.routing_api.<name>`` keep working, and so the injected services use
whatever those names resolve to at call time (including test patches).
"""

import logging
import os

import requests  # noqa: F401  (re-exported: tests patch app.routers.routing_api.requests.get)
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.models.routing_models.routing_models import MapBox, Route, Route_Payload
from app.routers.routing_fns.webscraping_fns import find_google_hotels  # noqa: F401
from app.routing import PlanningError, PlanOptions, RoutingServices, get_planner
from app.routing.config import geolocator  # shared reverse-geocoder
from app.routing.geometry import find_position as _find_position  # noqa: F401
from app.routing.pricing import get_price_range as _get_price_range  # noqa: F401
from app.routing.registry import DEFAULT_ALGORITHM
from app.routing.sources.attractions import find_stop as _find_stop  # noqa: F401
from app.routing.sources.attractions import gather_candidates as _gather_candidates
from app.routing.sources.hotels import find_hotel as _find_hotel  # noqa: F401
from app.routing.sources.hotels import get_amadeus_token as _get_amadeus_token  # noqa: F401
from app.routing.sources.hotels import get_nearby_city as _get_nearby_city  # noqa: F401
from app.routing.sources.mapbox import call_route as _call_route
from app.utils.geolocation_helpers import get_location  # noqa: F401  (patched in tests)

# Setup logging (for debugging)
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Type aliases kept for convenience / backwards compatibility.
Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step
MapBox_route = MapBox.MapBox_Route

router = APIRouter()


def _build_services() -> RoutingServices:
    """Assemble the dependency bundle for a planner run.

    References this module's names so tests patching
    ``app.routers.routing_api.<name>`` take effect.
    """
    return RoutingServices(
        find_stop=_find_stop,
        find_hotel=_find_hotel,
        find_position=_find_position,
        get_price_range=_get_price_range,
        gather_candidates=_gather_candidates,
    )


@router.get("/get-initial-route")
async def get_initial_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> MapBox_route:
    try:
        # Construct initial route without stops
        initial_route = await _call_route(start_lat, start_lon, end_lat, end_lon)
        return initial_route
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Improper Mapbox response: {str(exception)}")
    except (KeyError, ValueError) as exception:
        raise HTTPException(
            status_code=500, detail=f"Error processing Mapbox response: {str(exception)}"
        )


@router.post("/generate-final-route", response_model=Route)
async def get_final_route(request: Request) -> Route:
    """
    Retrieves a route from Mapbox API, adds intermediate stops via the selected
    planner, and returns the detailed route information.

    Parameters:
        - request (Request): A JSON payload containing data of the initial route, number of stops,
        budget, start date, and an optional ``algorithm`` name.

    Returns:
        - Route: Detailed route information including coordinates, distance, duration, and stops.

    Raises:
        - HTTPException: For errors related to Mapbox requests, planning, or response processing.
    """

    try:
        # Validate provided payload and use data to initialize variables
        json_data = await request.json()
        payload = Route_Payload.model_validate(json_data)
        initial_route = payload.initial_route
        start_lon, start_lat = initial_route.geometry.coordinates[0]
        end_lon, end_lat = initial_route.geometry.coordinates[-1]
        num_stops = payload.num_stops
        start = payload.start
        budget = payload.budget

        # Check for num_stops positive or zero
        if not isinstance(num_stops, int) or num_stops < 0:
            raise ValueError("Number of stops must be a non-negative integer")

        # Select the routing algorithm: request field > env var > default.
        algorithm = payload.algorithm or os.getenv("ROUTING_ALGORITHM", DEFAULT_ALGORITHM)
        planner = get_planner(algorithm)
        services = _build_services()
        options = PlanOptions(num_stops=num_stops, budget=budget, start=start)

        # Run the planner to find stopping points.
        result = await planner.plan(initial_route, options, services)
        stopping_points, total_cost = result.stopping_points, result.total_cost

        coordinates = []
        for stop in stopping_points:
            coordinates.append(stop["coordinates"])

        # Construct waypoints string and make new route with stopping points
        waypoints = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
        route = await _call_route(start_lat, start_lon, end_lat, end_lon, waypoints)
        distance, duration = route.distance, route.duration
        geometry = route.geometry
        steps = []

        idx = 0
        for leg in route.legs:
            # Add the duration to each stop
            if idx < len(stopping_points) and stopping_points[idx]["type"] != "generic":
                stopping_points[idx]["duration"] = (
                    leg.duration
                )  # For each stopping point add the duration to each
                if stopping_points[idx].get("address") is None:
                    location = get_location(
                        geocoder=geolocator, coords=stopping_points[idx]["coordinates"]
                    )
                    if location:
                        stopping_points[idx]["address"] = (
                            location.address
                        )  # Add the address to each
            else:
                location = get_location(geocoder=geolocator, coords=[end_lat, end_lon])
                # Include the duration to get to the end
                stopping_points.append(
                    {
                        "name": "Arrive at your destination",
                        "duration": leg.duration,
                        "type": "end",
                        "address": location.address if location else None,
                    }
                )
            idx += 1
        # NOTE: `steps` is intentionally left empty. Turn-by-turn Route_Step data is
        # not consumed by any client (the frontend and itinerary endpoint read `stops`
        # and `geometry`, never `steps`), so we skip building it. Populate this from
        # `leg.steps` here if a client ever needs per-maneuver instructions.
        # Add all stopping coordinates to a single variable
        coordinates = [[start_lat, start_lon]] + coordinates + [[end_lat, end_lon]]
        return Route(
            coordinates=coordinates,
            distance=distance,
            duration=duration,
            steps=steps,
            stops=stopping_points,
            geometry=geometry,
            cost=total_cost,
        )

    except PlanningError as exception:
        raise HTTPException(status_code=exception.status_code, detail=exception.detail)
    except HTTPException as exception:
        raise exception
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Improper Mapbox response: {str(exception)}")
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=502, detail=f"Unexpected value or key: {str(exception)}")


@router.get("/algorithms")
async def list_algorithms() -> dict:
    """List the routing algorithms available to select (for the dev-mode picker).

    Returns the registered planner names and the current default. Always enabled
    (read-only, no external calls) so the frontend can populate its settings popup.
    """
    from app.routing.registry import available_planners

    default = os.getenv("ROUTING_ALGORITHM", DEFAULT_ALGORITHM)
    return {"algorithms": available_planners(), "default": default}


@router.get("/benchmark")
async def benchmark(algorithms: str = None):
    """Run the offline planner benchmark and return a comparison table (JSON).

    Debug/analysis endpoint — disabled unless ``BENCHMARK_ENABLED=true`` in the
    environment, since it's for local comparison, not production traffic. Uses
    cached/deterministic candidate data (no external API calls).

    Query params:
        - algorithms (optional): comma-separated subset, e.g. ``greedy,ortools``.
          Defaults to every registered planner.
    """
    if os.getenv("BENCHMARK_ENABLED", "false").lower() != "true":
        raise HTTPException(
            status_code=404,
            detail="Benchmark endpoint disabled. Set BENCHMARK_ENABLED=true to enable.",
        )
    from app.routing.benchmark import run_benchmark

    algo_list = [a.strip() for a in algorithms.split(",")] if algorithms else None
    try:
        return await run_benchmark(algorithms=algo_list)
    except PlanningError as exception:
        raise HTTPException(status_code=exception.status_code, detail=exception.detail)
