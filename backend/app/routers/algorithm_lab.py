"""Owner-only experiments over the ordinary planning core; never saves a chat."""

import asyncio
from datetime import date, datetime
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.trip_dates import (
    _localize,
    normalize_departure_time,
    resolve_departure,
    timezone_from_location,
)
from app.agent.trip_profile import MAX_STOPS, MIN_STOPS, Car, TripProfile
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route_Payload
from app.models.scheduling_policy import EveningInterest, SchedulingPolicy
from app.routers.itinerary_api import build_itinerary
from app.routers.routing_api import plan_final_route
from app.routing.base import PlanningError
from app.routing.config import geolocator
from app.routing.explanation import capture_explanation, record_explanation, record_stage
from app.routing.lab_presets import ENDPOINTS, PRESETS, SNAPSHOTS, preset_catalog, replay_candidates
from app.routing.occupancy import (
    MAX_CHILD_AGE,
    MAX_ROOM_GUESTS,
    MAX_ROOMS,
    HotelRooms,
    TravelerCount,
    require_occupancy,
)
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.selection import owner_routing_claims
from app.routing.sources.mapbox import call_route
from app.routing.sources.persona_candidates import CandidateProviderError
from app.utils.auth import require_authenticated_user
from app.utils.geolocation_helpers import get_location


class LabRoute(APIRoute):
    """Do not reflect raw inputs (including NaN) in validation responses."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                detail = [
                    {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
                ]
                raise HTTPException(status_code=422, detail=detail) from exc

        return validated


router = APIRouter(prefix="/algorithm-lab", tags=["algorithm-lab"], route_class=LabRoute)


def require_lab_owner(
    user_id: str = Depends(require_authenticated_user),
    x_cognito_id_token: str | None = Header(default=None),
) -> str:
    if owner_routing_claims(user_id, x_cognito_id_token) is None:
        raise HTTPException(
            status_code=403, detail="Algorithm Lab requires the verified owner account"
        )
    return user_id


class LabInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_id: str
    destination_id: str
    departure_date: date
    departure_time: str
    num_stops: int = Field(strict=True, ge=MIN_STOPS, le=MAX_STOPS)
    traveler_count: TravelerCount
    hotel_rooms: HotelRooms
    budget: float
    car_status: Literal["skipped", "provided"]
    car: Car | None = None
    persona_weights: dict[str, float]
    scheduling_policy: SchedulingPolicy
    evening_interests: list[EveningInterest] = Field(default_factory=list, max_length=3)

    @field_validator("start_id", "destination_id")
    @classmethod
    def endpoint(cls, value):
        if value not in ENDPOINTS:
            raise ValueError("Choose an endpoint from the server catalog")
        return value

    @field_validator("departure_time")
    @classmethod
    def clock(cls, value):
        return normalize_departure_time(value)

    @field_validator("persona_weights", mode="before")
    @classmethod
    def weights(cls, value):
        # Complete overrides make fixture comparisons independent of account state.
        normalize_weights(value)
        return value

    @model_validator(mode="after")
    def trip_rules(self):
        if self.start_id == self.destination_id:
            raise ValueError("Choose different starting and destination locations")
        TripProfile.model_validate(self.trip_fields())
        require_occupancy(self.traveler_count, self.hotel_rooms)
        return self

    def trip_fields(self):
        return self.model_dump(exclude={"start_id", "destination_id", "departure_date"})


class LabRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["live", "replay"]
    preset_id: str
    inputs: LabInputs
    snapshot_id: Literal["teaching-v1", "empty-v1"] | None = None

    @model_validator(mode="after")
    def mode_rules(self):
        if self.preset_id not in PRESETS:
            raise ValueError("Unknown preset")
        if (self.mode == "replay") != (self.snapshot_id is not None):
            raise ValueError("Replay requires a fixture snapshot; live must omit snapshot_id")
        return self


@router.get("/presets")
async def presets(response: Response, user_id: str = Depends(require_lab_owner)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "schema_version": 1,
        "attributes": list(ATTRIBUTE_KEYS),
        "endpoints": [{"id": key, "label": value["label"]} for key, value in ENDPOINTS.items()],
        "presets": preset_catalog(),
        "snapshots": SNAPSHOTS,
        "limits": {
            "min_stops": MIN_STOPS,
            "max_stops": MAX_STOPS,
            "max_rooms": MAX_ROOMS,
            "max_guests_per_room": MAX_ROOM_GUESTS,
            "max_child_age": MAX_CHILD_AGE,
        },
    }


async def resolve_endpoint(endpoint_id):
    location = await asyncio.to_thread(
        get_location, geocoder=geolocator, address=ENDPOINTS[endpoint_id]["label"]
    )
    if location is None or not (zone := timezone_from_location(location)):
        raise PlanningError(
            "The endpoint provider could not resolve the chosen city and timezone", 503
        )
    return {
        "label": location.address,
        "coordinates": [location.latitude, location.longitude],
        "timezone": zone,
        "source": "OpenCage geocoded server catalog selection",
    }


def _departure(inputs, zone, live):
    local = f"{inputs.departure_date.isoformat()}T{inputs.departure_time}"
    if live:
        return resolve_departure(local, zone)
    return _localize(datetime.fromisoformat(local), ZoneInfo(zone)).isoformat()


@router.post("/run")
async def run(payload: LabRun, response: Response, user_id: str = Depends(require_lab_owner)):
    response.headers["Cache-Control"] = "no-store"
    inputs = payload.inputs
    # Reject invalid live dates before incurring any provider requests. All catalog
    # cities have the same timezone; re-resolve using provider timezone below.
    try:
        departure = _departure(inputs, "America/Los_Angeles", payload.mode == "live")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    weights = normalize_weights(inputs.persona_weights)
    snapshot = next((item for item in SNAPSHOTS if item["id"] == payload.snapshot_id), None)
    envelope = {
        "schema_version": 1,
        "mode": payload.mode,
        "input_snapshot": {
            **inputs.model_dump(mode="json"),
            "start_date": departure,
            "effective_weights": weights,
            "weights_source": "Complete trip override; account persona is not changed",
            "car_usage": "Recorded only; car is not part of CP-SAT selection or this Lab's cost estimate",
        },
        "snapshot": snapshot
        or {
            "id": f"live-{uuid4()}",
            "label": "Fresh live discovery",
            "source": "Live provider discovery; not replayable as a server fixture",
        },
        "route": None,
        "itinerary": None,
        "error": None,
    }
    with capture_explanation() as explanation:
        record_explanation(weights=weights)
        record_stage(
            "inputs",
            "complete",
            "Validated trip, occupancy, preferences and departure. Nothing is saved to chat or account.",
        )
        try:
            if payload.mode == "replay":
                candidates, points = replay_candidates(payload.snapshot_id, weights)
                record_stage(
                    "endpoints", "not_run", "Fixture coordinates; no live endpoint verification."
                )
                record_stage(
                    "initial_route", "not_run", "Selection-only fixture; no road route is claimed."
                )
                record_stage(
                    "candidates",
                    "complete",
                    "Frozen synthetic attributes, rescored with this trip profile.",
                )
                CPSatPlanner._select(candidates, points, inputs.num_stops)
                record_stage(
                    "selection",
                    "complete",
                    "Same CP-SAT model as live planning; see solver status.",
                )
            else:
                start, destination = await asyncio.gather(
                    resolve_endpoint(inputs.start_id), resolve_endpoint(inputs.destination_id)
                )
                departure = _departure(inputs, start["timezone"], True)
                trip = TripProfile.model_validate(
                    {
                        **inputs.trip_fields(),
                        "start_address": start["label"],
                        "start_coords": start["coordinates"],
                        "start_timezone": start["timezone"],
                        "destination_address": destination["label"],
                        "destination_coords": destination["coordinates"],
                        "start_date": departure,
                    }
                )
                envelope["input_snapshot"].update(
                    start=start,
                    destination=destination,
                    start_date=departure,
                    trip_profile=trip.model_dump(mode="json"),
                )
                record_stage(
                    "endpoints",
                    "complete",
                    "Resolved the explicitly selected catalog cities with the provider.",
                )
                initial = await call_route(*start["coordinates"], *destination["coordinates"])
                record_stage("initial_route", "complete", "Mapbox base driving route received.")
                route = await plan_final_route(
                    Route_Payload(
                        initial_route=initial,
                        num_stops=trip.num_stops,
                        budget=trip.budget,
                        start=datetime.fromisoformat(departure),
                        persona_weights=inputs.persona_weights,
                        scheduling_policy=trip.scheduling_policy,
                        start_timezone=trip.start_timezone,
                        traveler_count=trip.traveler_count,
                        hotel_rooms=trip.hotel_rooms,
                        evening_interests=trip.evening_interests,
                    ),
                    user_id=user_id,
                )
                envelope["route"] = route.model_dump(mode="json")
                itinerary = await build_itinerary(
                    Itinerary_Payload(route=route, start_time=datetime.fromisoformat(departure))
                )
                envelope["itinerary"] = [day.model_dump(mode="json") for day in itinerary]
                record_stage(
                    "itinerary", "complete", "Built itinerary from the actual validated route."
                )
        except Exception as exc:
            # Never return upstream request objects, credentials, or raw provider HTML.
            message = (
                exc.detail
                if isinstance(exc, PlanningError)
                else str(exc)
                if isinstance(exc, CandidateProviderError)
                else "The live planning stage failed. Check provider configuration and retry; no replay was substituted."
            )
            code = (
                str(exc.status_code)
                if isinstance(exc, PlanningError)
                else "provider_or_planning_failure"
            )
            envelope["error"] = {"code": code, "message": message}
        completed = {item["name"] for item in explanation["stages"]}
        failure_pending = envelope["error"] is not None
        for name in (
            "endpoints",
            "initial_route",
            "candidates",
            "selection",
            "scheduling",
            "reroute",
            "itinerary",
        ):
            if name not in completed:
                status = "failed" if failure_pending else "not_run"
                detail = (
                    envelope["error"]["message"]
                    if failure_pending
                    else "Not run; replay demonstrates selection only."
                    if payload.mode == "replay"
                    else "Not reached."
                )
                record_stage(name, status, detail)
                failure_pending = False
        envelope["stages"] = explanation.pop("stages")
        envelope["explanation"] = explanation
    return envelope
