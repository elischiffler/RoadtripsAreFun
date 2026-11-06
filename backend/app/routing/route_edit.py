"""Recalculate an explicit stop edit without planning AI or persistent writes."""

import math
from copy import deepcopy
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agent.departure import is_upcoming_departure
from app.catalog import repository
from app.catalog.identity import catalog_source_id, identity
from app.models.itinerary_models import Itinerary_Payload
from app.models.route_edit import EditGeometry, RouteEditRequest, RouteEditResponse, _coordinate
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import local_time
from app.models.trip_limits import MAX_STOPS
from app.routers.itinerary_api import build_itinerary
from app.routing.alternatives import _distance
from app.routing.base import PlanningError
from app.routing.catalog_calendars import refresh_for_timing
from app.routing.runtime import in_run, threaded
from app.routing.sources.mapbox import require_route_capacity
from app.routing.travel_timing import apply_timing
from app.routing.visit_calendar import calendar_eligible
from app.routing.visit_duration import fallback_duration


@in_run
async def preview_route_edit(
    payload: RouteEditRequest, *, route_call, timezone_at, catalog_lookup=None
):
    """Adapters are trusted Python arguments, never configurable HTTP endpoints."""
    route = payload.route
    stops = deepcopy(route.stops)
    start = route.departure_time
    if start is None or start.tzinfo is None or route.scheduling_policy is None:
        raise PlanningError(
            "This saved trip needs an upcoming departure and scheduling policy; replan it before editing",
            422,
        )
    if not is_upcoming_departure(start):
        raise PlanningError(
            "The trip departure has passed; choose a new departure before editing", 422
        )
    if payload.stop_index >= len(stops):
        raise PlanningError("Choose a current itinerary stop", 422)
    if payload.action == "replace" and stops[payload.stop_index]["type"] != "stop":
        raise PlanningError(
            "Only attraction stops can be replaced; hotels and destination are retained", 422
        )
    require_route_capacity(len(stops) + 1 + (payload.action == "add"))
    count = sum(stop["type"] == "stop" for stop in stops) + (payload.action == "add")
    if count > MAX_STOPS:
        raise PlanningError(f"This trip permits at most {MAX_STOPS} attraction stops", 422)
    for stop in stops:
        if stop["type"] == "hotel" and not stop.get("check_in_date"):
            raise PlanningError(
                "The saved hotel stay has no booking date; replan before editing", 422
            )
    sid = catalog_source_id(payload.provider_id)
    if sid is None:
        raise PlanningError("Choose a current catalog place", 422)
    lookup = repository.current_records if catalog_lookup is None else catalog_lookup
    try:
        facts = (await threaded("catalog", lookup, [sid])).get(sid)
    except Exception:
        raise PlanningError(
            "Current place access could not be verified; retry this edit", 503
        ) from None
    if not facts:
        raise PlanningError("This place is no longer available in the current catalog", 422)
    selected = {
        **facts,
        "provider_id": payload.provider_id,
        "source": identity(sid)[1],
        "type": "stop",
        "duration": 0,
    }
    try:
        _coordinate.validate_python(selected.get("coordinates"))
        if (
            not isinstance(selected.get("name"), str)
            or not selected["name"].strip()
            or not calendar_eligible(selected)
        ):
            raise ValueError("ineligible")
    except (ValueError, TypeError, AttributeError):
        raise PlanningError(
            "This place has no verified itinerary-ready access; choose another place", 422
        ) from None
    if (
        any(
            stop.get("provider_id") == payload.provider_id
            or _distance(stop["coordinates"], selected["coordinates"]) < 0.1
            for stop in stops
        )
        or _distance(route.coordinates[0], selected["coordinates"]) < 0.1
    ):
        raise PlanningError("This place is already in the trip", 422)
    selected["visit_duration"] = fallback_duration("missing_estimate").model_dump()
    if payload.action == "add":
        stops.insert(payload.stop_index, selected)
    else:
        stops[payload.stop_index] = selected
    for stop in stops:
        for key in (
            "arrival_time",
            "departure_time",
            "road_arrival_time",
            "wait_seconds",
            "availability",
            "travel_day",
            "deadline",
            "late_check_in_notice",
            "warning",
        ):
            stop.pop(key, None)
        if stop["type"] == "hotel":
            stop["evening_suggestions"] = []
    await refresh_for_timing(stops, catalog_lookup=lookup)
    if timezone_at is None:
        raise PlanningError("Arrival timezones could not be verified; retry this edit", 503)
    try:
        start_timezone = await timezone_at(list(route.coordinates[0]))
        zone = ZoneInfo(start_timezone)
        start = local_time(start, zone)
        for stop in stops:
            stop["timezone"] = await timezone_at(stop["coordinates"])
            ZoneInfo(stop["timezone"])
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise PlanningError(
            "Arrival timezones could not be verified; retry this edit", 503
        ) from None
    origin, destination = route.coordinates[0], stops[-1]["coordinates"]
    waypoints = ";".join(f"{s['coordinates'][1]},{s['coordinates'][0]}" for s in stops[:-1]) or None
    road = await route_call(*origin, *destination, waypoints)
    if (
        len(road.legs) != len(stops)
        or road.geometry is None
        or not all(math.isfinite(v) and v >= 0 for v in (road.distance, road.duration))
    ):
        raise PlanningError("Mapbox returned an incomplete edited route", 502)
    try:
        geometry = EditGeometry.model_validate(road.geometry.model_dump())
    except (ValueError, TypeError, AttributeError):
        raise PlanningError("Mapbox returned invalid edited route geometry", 502) from None
    for stop, leg in zip(stops, road.legs, strict=True):
        if not math.isfinite(leg.distance) or leg.distance < 0:
            raise PlanningError("Mapbox returned an invalid edited route leg", 502)
        stop.update(duration=leg.duration, distance=leg.distance)
    apply_timing(stops, start, route.scheduling_policy, start_timezone)
    result = Route(
        **{
            **route.model_dump(),
            "stops": stops,
            "coordinates": [list(origin)] + [s["coordinates"] for s in stops],
            "distance": road.distance,
            "duration": road.duration,
            "geometry": geometry.model_dump(),
            "steps": [],
            "start_timezone": start_timezone,
            "departure_time": start,
            "warnings": [s["warning"] for s in stops if s.get("warning")] or None,
        }
    )
    itinerary = await build_itinerary(
        Itinerary_Payload(route=result, include_meal_slots=payload.include_meal_slots),
        catalog_lookup=lookup,
    )
    return RouteEditResponse(route=result, itinerary=itinerary)
