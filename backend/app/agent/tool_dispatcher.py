"""Contract 3 — the real tool dispatcher (design doc §5, Stream A-tools).

:class:`AppToolDispatcher` wraps the app's *existing* capabilities as thin
adapters and advertises them to the model via :meth:`specs`. It satisfies the
async :class:`~app.agent.tools.ToolDispatcher` Protocol: :meth:`dispatch` routes
a tool name to a handler, coerces the model-supplied arguments, and returns a
:class:`ToolResult`.

Design rules honored here:

- **Thin adapters, no reimplementation.** Route-shaping and itinerary-splitting
  are *not* copied in — they reuse the already-factored core functions the
  routers call (``routing_api.plan_final_route`` and
  ``itinerary_api.build_itinerary``), so the fixed stop-dict contract
  (``name`` / ``type`` / ``coordinates`` ``[lat, lon]`` / ``price``) lives in
  exactly one place.
- **Never raise out of dispatch.** Every handler runs inside a guard that
  captures ``HTTPException`` / ``RequestException`` / ``ValidationError`` /
  ``KeyError`` / ``ValueError`` / generic ``Exception`` as
  ``ToolResult(ok=False, error=...)`` so the agent loop can feed the failure
  back to the model instead of blowing up the turn.
- **State-mutating tools emit an ``action``.** ``generate_final_route`` and
  ``generate_itinerary`` include ``"action"`` in their result so ``run_turn``'s
  ``_collect_action`` promotes it to a typed :class:`AgentAction`.
- **Coordinates are ``[lat, lon]``** at this boundary (Mapbox's ``[lon, lat]``
  order stays inside ``sources/mapbox``).
- **Async vs sync.** ``call_route`` / ``plan_final_route`` / ``build_itinerary``
  / ``get_car_details`` / ``get_gas_price`` are awaited; ``get_location`` is sync
  and called directly.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.agent import routing_remote
from app.agent.memory import MemoryFact
from app.agent.schemas import ToolCall, ToolResult, ToolSpec
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile, TripProfileUpdate
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import MapBox, Route_Payload
from app.routers.car_api import get_car_details, get_gas_price
from app.routers.itinerary_api import build_itinerary
from app.routers.routing_api import plan_final_route
from app.routing.config import geolocator
from app.routing.sources.mapbox import call_route
from app.utils.geolocation_helpers import get_location

logger = logging.getLogger(__name__)

# Handler signature: takes the (already-validated) argument dict + the context,
# returns a JSON-serializable result dict. Handlers may raise; dispatch guards.
Handler = Callable[[dict[str, Any], ToolContext], Awaitable[dict[str, Any]]]


def _km(meters: float) -> int:
    """Meters -> whole kilometers, for compact human summaries."""
    return round((meters or 0) / 1000)


def _hours(seconds: float) -> str:
    """Seconds -> a short 'Hh Mm' duration string."""
    total_min = int((seconds or 0) // 60)
    return f"{total_min // 60}h {total_min % 60}m"


def _as_latlon_pair(value: Any) -> tuple[float, float] | None:
    """Coerce a ``[lat, lon]`` value (list, or JSON-string of a list) to floats.

    Models emit coordinate pairs as a real array, or (a known quirk) as a JSON
    *string* like ``"[35.28, -120.66]"``. Returns ``(lat, lon)`` or ``None`` if it
    isn't a usable two-number pair.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _endpoint(args: dict[str, Any], side: str, coord_keys: list[str]) -> tuple[float, float] | None:
    """Resolve one endpoint (``side`` = "start"/"end") from the many shapes models emit.

    Tolerated, in priority order:
      * flat scalars: ``{side}_lat`` + ``{side}_lon``
      * a ``[lat, lon]`` array (or JSON-string of one) under any of ``coord_keys``
        (e.g. ``start_coords`` / ``end_coords`` / ``destination_coords``)
      * a nested object ``{side}: {latitude|lat, longitude|lon}`` or
        ``{side}: {coordinates: [lat, lon]}``
      * a bare ``[lat, lon]`` array (or JSON-string) directly under ``{side}``
    """
    # Flat scalars: start_lat/start_lon.
    lat, lon = args.get(f"{side}_lat"), args.get(f"{side}_lon")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    # Array (or stringified array) under a *_coords-style key.
    for key in coord_keys:
        pair = _as_latlon_pair(args.get(key))
        if pair:
            return pair

    # Nested object or bare array under start/end.
    nested = args.get(side)
    if isinstance(nested, dict):
        n_lat = nested.get("latitude", nested.get("lat"))
        n_lon = nested.get("longitude", nested.get("lon"))
        if n_lat is not None and n_lon is not None:
            try:
                return float(n_lat), float(n_lon)
            except (TypeError, ValueError):
                pass
        pair = _as_latlon_pair(nested.get("coordinates"))
        if pair:
            return pair
    else:
        pair = _as_latlon_pair(nested)
        if pair:
            return pair

    return None


def _extract_endpoints(args: dict[str, Any]) -> tuple[float, float, float, float]:
    """Pull (start_lat, start_lon, end_lat, end_lon) from the many shapes models emit.

    Accepts flat scalars, ``*_coords`` arrays (matching the trip-profile
    convention), nested ``start``/``end`` objects, and bare ``[lat, lon]`` arrays
    (including JSON-stringified ones). This tolerance matters because the model
    copies coordinates from ``validate_location`` (which returns
    ``latitude``/``longitude``) and from the trip profile (which stores
    ``start_coords``/``destination_coords`` as ``[lat, lon]``), so it reasonably
    passes any of these shapes.
    """
    start = _endpoint(args, "start", ["start_coords"])
    end = _endpoint(args, "end", ["end_coords", "destination_coords", "dest_coords"])
    if start and end:
        return start[0], start[1], end[0], end[1]

    raise ValueError(
        "get_initial_route needs start AND end coordinates. Provide flat "
        "start_lat/start_lon/end_lat/end_lon, or start_coords/end_coords as "
        "[lat, lon] arrays, or nested start{latitude,longitude} and "
        "end{latitude,longitude}. Validate each location first if you don't have "
        "its coordinates yet."
    )


class AppToolDispatcher:
    """Real :class:`~app.agent.tools.ToolDispatcher` over existing capabilities."""

    def __init__(self) -> None:
        # name -> handler. Kept explicit (rather than reflection) so the tool
        # surface is auditable at a glance and matches specs() 1:1.
        self._handlers: dict[str, Handler] = {
            "validate_location": self._validate_location,
            "get_initial_route": self._get_initial_route,
            "generate_final_route": self._generate_final_route,
            "generate_itinerary": self._generate_itinerary,
            "get_car_budget": self._get_car_budget,
            "recall_facts": self._recall_facts,
            "remember_fact": self._remember_fact,
            "get_trip_profile": self._get_trip_profile,
            "update_trip_profile": self._update_trip_profile,
        }

    # ------------------------------------------------------------------ #
    # Advertised tool specs (§5 registry)
    # ------------------------------------------------------------------ #

    def specs(self) -> list[ToolSpec]:
        """The tools advertised to the model (JSON-Schema parameters)."""
        return [
            ToolSpec(
                name="validate_location",
                description=(
                    "Resolve a free-text address or a [lat, lon] coordinate pair to a "
                    "canonical address with latitude and longitude. Provide either "
                    "`address` or `coordinates`."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Free-text address to geocode.",
                        },
                        "coordinates": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "A [lat, lon] pair to reverse-geocode.",
                        },
                    },
                },
            ),
            ToolSpec(
                name="get_initial_route",
                description=(
                    "Fetch the driving route between two points. Returns a "
                    "`route_handle` (an opaque id) plus distance/duration — pass the "
                    "route_handle to generate_final_route. Provide coordinates EITHER as "
                    "flat numbers (start_lat/start_lon/end_lat/end_lon) OR as [lat, lon] "
                    "arrays (start_coords/end_coords). Use the latitude/longitude from "
                    "validate_location, or the start_coords/destination_coords stored on "
                    "the trip profile."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "start_lat": {"type": "number"},
                        "start_lon": {"type": "number"},
                        "end_lat": {"type": "number"},
                        "end_lon": {"type": "number"},
                        "start_coords": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "[lat, lon] of the start (alternative to start_lat/start_lon).",
                        },
                        "end_coords": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "[lat, lon] of the destination (alternative to end_lat/end_lon).",
                        },
                    },
                },
            ),
            ToolSpec(
                name="generate_final_route",
                description=(
                    "Plan the full multi-day trip: insert attraction/hotel stops into the "
                    "initial route. Takes the `route_handle` from get_initial_route. "
                    "num_stops/budget/algorithm default from the traveler's profile if "
                    "omitted. Returns a new `route_handle` (pass it to "
                    "generate_itinerary). Mutates trip state."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "route_handle": {
                            "type": "string",
                            "description": "The route_handle returned by get_initial_route.",
                        },
                        "num_stops": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Number of attraction stops to insert.",
                        },
                        "budget": {
                            "type": "number",
                            "description": "Nightly hotel budget in dollars.",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Optional planner name (e.g. 'greedy', 'ortools').",
                        },
                    },
                    "required": ["route_handle"],
                },
            ),
            ToolSpec(
                name="generate_itinerary",
                description=(
                    "Turn a finalized route into a day-by-day itinerary with arrival times "
                    "and addresses. Takes the `route_handle` returned by "
                    "generate_final_route. Mutates itinerary state."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "route_handle": {
                            "type": "string",
                            "description": "The route_handle returned by generate_final_route.",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Optional ISO-8601 trip start datetime.",
                        },
                    },
                    "required": ["route_handle"],
                },
            ),
            ToolSpec(
                name="get_car_budget",
                description=(
                    "Estimate fuel cost for a trip: looks up the car's combined MPG and the "
                    "current national average gas price. Optionally divides by trip distance "
                    "(meters) to estimate total fuel cost."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "make": {"type": "string"},
                        "model": {"type": "string"},
                        "year": {"type": "integer"},
                        "distance_meters": {
                            "type": "number",
                            "description": "Optional trip distance in meters to price the fuel.",
                        },
                    },
                    "required": ["make", "model", "year"],
                },
            ),
            ToolSpec(
                name="recall_facts",
                description=(
                    "Recall durable facts we know about this traveler (home city, "
                    "preferences, budget style, car, etc.)."
                ),
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="remember_fact",
                description=(
                    "Store a durable free-form fact the user stated that does NOT fit a "
                    "trip-profile field. For this trip's details (start, destination, "
                    "stops, budget, dates, car), use update_trip_profile instead."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                        "confidence": {"type": "number", "default": 1.0},
                    },
                    "required": ["key", "value"],
                },
            ),
            ToolSpec(
                name="get_trip_profile",
                description=(
                    "Read the current trip profile for THIS chat: everything gathered so "
                    "far (start, destination, number of stops, nightly hotel budget, start "
                    "date, car). Consult this BEFORE asking the traveler for something you "
                    "may already have."
                ),
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="update_trip_profile",
                description=(
                    "Record trip details into THIS chat's trip profile as the traveler "
                    "confirms them (start, destination, number of stops, nightly hotel "
                    "budget, start date, car). Call this whenever you learn or confirm a "
                    "trip detail — e.g. when the user gives the starting location or "
                    "destination. Only include the fields you learned; others are left "
                    "unchanged. Prefer storing coordinates from validate_location "
                    "alongside the address."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "start_address": {
                            "type": "string",
                            "description": "Where the trip starts (address or city).",
                        },
                        "start_coords": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "[lat, lon] of the start (from validate_location).",
                        },
                        "destination_address": {
                            "type": "string",
                            "description": "Where the trip is headed (address or city).",
                        },
                        "destination_coords": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "[lat, lon] of the destination.",
                        },
                        "num_stops": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Number of attraction stops.",
                        },
                        "budget": {
                            "type": "number",
                            "description": "Nightly hotel budget in dollars.",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional ISO-8601 trip start date/time.",
                        },
                        "car_year": {"type": "integer"},
                        "car_make": {"type": "string"},
                        "car_model": {"type": "string"},
                    },
                },
            ),
        ]

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #

    async def dispatch(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """Route ``call`` to its handler; never raises (failures -> ok=False)."""
        handler = self._handlers.get(call.name)
        if handler is None:
            return ToolResult(name=call.name, ok=False, error=f"Unknown tool: {call.name!r}")

        arguments = call.arguments if isinstance(call.arguments, dict) else {}
        try:
            result = await handler(arguments, ctx)
            return ToolResult(name=call.name, ok=True, result=result)
        except HTTPException as exception:
            # Surface the upstream detail (already scrubbed of secrets by sources).
            return ToolResult(name=call.name, ok=False, error=str(exception.detail))
        except RequestException as exception:
            logger.warning("tool %s: upstream request failed: %s", call.name, exception)
            return ToolResult(name=call.name, ok=False, error="Upstream request failed.")
        except ValidationError as exception:
            return ToolResult(name=call.name, ok=False, error=f"Invalid arguments: {exception}")
        except (KeyError, ValueError) as exception:
            return ToolResult(
                name=call.name, ok=False, error=f"Invalid or missing argument: {exception}"
            )
        except Exception as exception:  # noqa: BLE001 — dispatch must never raise
            logger.exception("tool %s: unexpected failure", call.name)
            return ToolResult(name=call.name, ok=False, error=f"Tool failed: {exception}")

    # ------------------------------------------------------------------ #
    # Handlers (thin adapters)
    # ------------------------------------------------------------------ #

    async def _validate_location(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        address = args.get("address")
        coordinates = args.get("coordinates")
        if not address and not coordinates:
            raise ValueError("Provide either 'address' or 'coordinates'.")
        # get_location is synchronous — call it directly.
        location = get_location(
            geocoder=geolocator,
            address=address,
            coords=list(coordinates) if coordinates else None,
        )
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
        return {
            "address": location.address,
            "latitude": location.latitude,
            "longitude": location.longitude,
        }

    async def _resolve_initial_route(
        self, args: dict[str, Any], ctx: ToolContext, trip: TripProfile
    ):
        """Resolve the initial route for generate_final_route.

        Resolution order:
          1. A ``route_handle`` that resolves in THIS turn's artifact store
             (same-turn chaining — the fast path).
          2. An inline ``initial_route`` object the model passed directly.
          3. Rebuild from the trip profile's ``start_coords`` /
             ``destination_coords`` — the cross-turn fallback.

        Why (3) exists: the ``ArtifactStore`` lives for a single ``run_turn``, but
        the model normally calls ``get_initial_route`` in one turn and
        ``generate_final_route`` in a LATER turn (after gathering stops/budget from
        the user). By then the earlier turn's handle is gone, so a handle-only
        contract fails with "needs route_handle". Rebuilding the initial route
        from the coordinates already stored on the profile makes the multi-turn
        flow self-healing and produces the SAME ``MapBox_Route`` object.
        """
        # 1. Handle that resolves in this turn's store.
        handle = args.get("route_handle") or args.get("initial_route_handle")
        if isinstance(handle, str) and ctx.artifacts.has(handle):
            obj = ctx.artifacts.get(handle)
            if isinstance(obj, MapBox.MapBox_Route):
                return obj
            return MapBox.MapBox_Route.model_validate(obj)

        # 2. Inline object fallback.
        inline = args.get("initial_route")
        if inline is not None:
            return MapBox.MapBox_Route.model_validate(inline)

        # 3. Rebuild from the trip profile's stored endpoints (cross-turn).
        start = _as_latlon_pair(trip.start_coords)
        end = _as_latlon_pair(trip.destination_coords)
        if start and end:
            logger.info(
                "generate_final_route: route_handle unresolved (%r); rebuilding the "
                "initial route from the trip profile's coordinates.",
                handle,
            )
            if routing_remote.remote_enabled():
                return await routing_remote.call_route_remote(start[0], start[1], end[0], end[1])
            return await call_route(start[0], start[1], end[0], end[1])

        raise ValueError(
            "generate_final_route needs an initial route. Call get_initial_route "
            "first, or record the start and destination coordinates on the trip "
            "profile (validate_location then update_trip_profile) so it can be rebuilt."
        )

    def _resolve_route_for_itinerary(self, args: dict[str, Any], ctx: ToolContext):
        """Resolve the planned Route from a handle, or an inline object fallback."""
        handle = args.get("route_handle")
        if isinstance(handle, str):
            obj = ctx.artifacts.get(handle)
            # build_itinerary wants a validatable route payload; a stored Route
            # model is dumped back to a dict so Itinerary_Payload can validate it.
            return obj.model_dump() if hasattr(obj, "model_dump") else obj
        inline = args.get("route")
        if inline is not None:
            return inline
        raise ValueError("generate_itinerary needs route_handle (from generate_final_route).")

    async def _get_initial_route(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        start_lat, start_lon, end_lat, end_lon = _extract_endpoints(args)
        # Proxy to the deployed backend (whitelisted IP) in local dev; run
        # locally on the deployed backend itself. Same MapBox_Route either way.
        if routing_remote.remote_enabled():
            route = await routing_remote.call_route_remote(start_lat, start_lon, end_lat, end_lon)
        else:
            route = await call_route(start_lat, start_lon, end_lat, end_lon)
        # Store the heavy Mapbox route server-side; hand the model only a handle
        # + a compact summary so the geometry never enters the LLM context.
        handle = ctx.artifacts.put("initial_route", route)
        return {
            "route_handle": handle,
            "distance_meters": route.distance,
            "duration_seconds": route.duration,
            "summary": (
                f"Initial route ready ({_km(route.distance)} km, "
                f"{_hours(route.duration)}). Pass route_handle='{handle}' to "
                "generate_final_route."
            ),
        }

    async def _generate_final_route(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        # Load the trip profile first — it supplies num_stops/budget defaults AND
        # the coordinates used to rebuild the initial route when the route_handle
        # from an earlier turn is no longer in this turn's artifact store.
        trip = self._load_trip_profile(ctx)
        # Resolve the initial route: this-turn handle → inline object → rebuild
        # from the trip's stored coordinates. The model never carries the raw
        # Mapbox geometry either way.
        initial_route = await self._resolve_initial_route(args, ctx, trip)

        # num_stops / budget default from THIS chat's trip profile when the model
        # omits them (e.g. the user gave a stop count earlier in the chat); an
        # explicit arg always wins. Everything below is coerced + validated by
        # Route_Payload, so trip-sourced values stay safe.
        num_stops = args.get("num_stops")
        if num_stops is None:
            num_stops = trip.num_stops
        if num_stops is None:
            raise ValueError("num_stops is required (none provided and none recorded on the trip).")

        budget = args.get("budget")
        if budget is None:
            budget = trip.budget
        if budget is None:
            raise ValueError("budget is required (none provided and none recorded on the trip).")

        payload_data: dict[str, Any] = {
            "initial_route": initial_route,
            "num_stops": int(num_stops),
            "budget": float(budget),
        }
        if args.get("algorithm"):
            payload_data["algorithm"] = args["algorithm"]
        start = args.get("start") or trip.start_date
        if start:
            payload_data["start"] = start
        payload = Route_Payload.model_validate(payload_data)
        # Proxy planning (and its whitelisted TripAdvisor/hotel calls) to the
        # deployed backend in local dev; run locally on the deployed backend.
        if routing_remote.remote_enabled():
            route = await routing_remote.plan_final_route_remote(payload)
        else:
            route = await plan_final_route(payload)
        # Store the planned Route; hand the model a handle + summary. The FULL
        # route still rides to the frontend via `route` (promoted onto the
        # action payload by run_turn), so Map/Itinerary render.
        handle = ctx.artifacts.put("route", route)
        stop_count = len([s for s in (route.stops or []) if s.get("type") == "stop"])
        return {
            "action": "route_updated",
            "route_handle": handle,
            "cost": route.cost,
            "stop_count": stop_count,
            "summary": (
                f"Trip planned: {stop_count} stop(s), ${route.cost:.0f} hotels, "
                f"{_km(route.distance)} km. Pass route_handle='{handle}' to "
                "generate_itinerary."
            ),
            # Full payload for the frontend (trimmed out of the model-visible
            # message by run_turn — see _MODEL_HIDDEN_KEYS).
            "route": route.model_dump(),
            "stops": route.stops,
        }

    async def _generate_itinerary(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        # Resolve the planned route from its handle (fallback: inline `route`).
        route_obj = self._resolve_route_for_itinerary(args, ctx)
        payload_data: dict[str, Any] = {"route": route_obj}
        if args.get("start_time"):
            payload_data["start_time"] = args["start_time"]
        payload = Itinerary_Payload.model_validate(payload_data)
        # Itinerary building is pure (no whitelisted external calls), but proxy
        # it too when remote is enabled to keep the routing path uniform.
        if routing_remote.remote_enabled():
            days = await routing_remote.build_itinerary_remote(payload)
        else:
            days = await build_itinerary(payload)
        return {
            "action": "itinerary_updated",
            "itinerary": [day.model_dump() for day in days],
        }

    async def _get_car_budget(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        # Fall back to the trip's stored car when make/model/year are omitted.
        make, model, year = args.get("make"), args.get("model"), args.get("year")
        if not (make and model and year):
            trip = self._load_trip_profile(ctx)
            if trip.car:
                make = make or trip.car.make
                model = model or trip.car.model
                year = year or trip.car.year
        if not (make and model and year):
            raise ValueError(
                "make, model, and year are required (none provided and no car on the trip)."
            )
        details = await get_car_details(model=str(model), make=str(make), year=int(year))
        mpg = details["combination_mpg"]
        gas_price = await get_gas_price()
        result: dict[str, Any] = {
            "combination_mpg": mpg,
            "gas_price": gas_price,
        }
        distance_meters = args.get("distance_meters")
        if distance_meters is not None:
            # meters -> miles; gallons = miles / mpg; cost = gallons * price.
            miles = float(distance_meters) / 1609.344
            gallons = miles / mpg if mpg else 0.0
            result["estimated_fuel_cost"] = round(gallons * gas_price, 2)
        return result

    async def _recall_facts(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if ctx.memory is None:
            raise ValueError("No memory store is available.")
        facts = ctx.memory.load_facts(ctx.user_id)
        return {"facts": [fact.model_dump(mode="json") for fact in facts]}

    async def _remember_fact(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if ctx.memory is None:
            raise ValueError("No memory store is available.")
        fact = MemoryFact(
            key=str(args["key"]),
            value=str(args["value"]),
            confidence=float(args.get("confidence", 1.0)),
            source_chat_id=ctx.chat_id,
        )
        ctx.memory.upsert_facts(ctx.user_id, [fact])
        return {"remembered": fact.model_dump(mode="json")}

    # ------------------------------------------------------------------ #
    # Trip profile (the per-chat validated trip-data model the AI fills in)
    # ------------------------------------------------------------------ #

    def _load_trip_profile(self, ctx: ToolContext) -> TripProfile:
        """Load this chat's validated trip profile (empty if none / no store)."""
        if ctx.memory is None:
            return TripProfile()
        return TripProfile.from_json(ctx.memory.load_trip_profile(ctx.user_id, ctx.chat_id))

    async def _get_trip_profile(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        trip = self._load_trip_profile(ctx)
        return {"trip_profile": trip.model_dump(mode="json", exclude_none=True)}

    async def _update_trip_profile(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if ctx.memory is None:
            raise ValueError("No memory store is available.")
        # Validate the partial update (raises ValidationError -> caught by dispatch).
        update = TripProfileUpdate.model_validate(args)
        current = self._load_trip_profile(ctx)
        merged = current.merged_with(update)
        # Persist the whole trip profile as the single per-chat 'trip' row.
        ctx.memory.save_trip_profile(ctx.user_id, ctx.chat_id, merged.to_json())
        profile_dict = merged.model_dump(mode="json", exclude_none=True)
        # Emit an action so the frontend can reflect the gathered trip data live
        # (and persist a ChatData snapshot -> the [DB] updateUserData log).
        return {"action": "trip_profile_updated", "trip_profile": profile_dict}
