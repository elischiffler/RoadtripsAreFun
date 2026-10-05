"""Owner-only live provider experiments over the ordinary planning core."""

import asyncio
import logging
import traceback
from datetime import date, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.progress import emit, stage
from app.agent.provider_diagnostics import collecting_attempts, diagnostic, retry_async
from app.agent.trip_dates import (
    normalize_departure_time,
    resolve_departure,
    timezone_from_location,
)
from app.agent.trip_profile import MAX_STOPS, MIN_STOPS, Car, TripProfile
from app.crud import lab_runs
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route_Payload
from app.models.scheduling_policy import EveningInterest, SchedulingPolicy
from app.routers.itinerary_api import build_itinerary
from app.routers.routing_api import plan_final_route
from app.routing.base import PlanningError
from app.routing.config import geolocator
from app.routing.explanation import capture_explanation, record_explanation, record_stage
from app.routing.lab_presets import (
    BENCHMARKS,
    ENDPOINTS,
    PRESETS,
    preset_catalog,
)
from app.routing.occupancy import (
    MAX_CHILD_AGE,
    MAX_ROOM_GUESTS,
    MAX_ROOMS,
    HotelRooms,
    TravelerCount,
    require_occupancy,
)
from app.routing.run_metrics import aggregate_runs, compile_metrics, measuring
from app.routing.selection import owner_routing_claims
from app.routing.sources.mapbox import call_route
from app.routing.sources.persona_candidates import CandidateProviderError
from app.utils.auth import require_authenticated_user
from app.utils.geolocation_helpers import get_location

logger = logging.getLogger(__name__)


def storage_failure(operation, exc):
    logger.error(
        "Lab storage failure operation=%s exception_class=%s sqlstate=%s",
        operation,
        type(exc).__name__,
        getattr(exc, "pgcode", None),
    )


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
        # Complete overrides make experiments independent of account state.
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
    mode: Literal["live"] = "live"
    preset_id: str
    inputs: LabInputs
    batch_id: UUID | None = None
    repeat_index: int = Field(default=1, strict=True, ge=1, le=10)

    @model_validator(mode="after")
    def preset_rules(self):
        if self.preset_id not in PRESETS and self.preset_id not in BENCHMARKS:
            raise ValueError("Unknown preset")
        return self


@router.get("/presets")
async def presets(response: Response, user_id: str = Depends(require_lab_owner)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "schema_version": 1,
        "attributes": list(ATTRIBUTE_KEYS),
        "endpoints": [{"id": key, "label": value["label"]} for key, value in ENDPOINTS.items()],
        "presets": preset_catalog(),
        "benchmarks": [item for item in preset_catalog() if item["id"] in BENCHMARKS],
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


def _departure(inputs, zone):
    local = f"{inputs.departure_date.isoformat()}T{inputs.departure_time}"
    return resolve_departure(local, zone)


@router.post("/run")
async def run(payload: LabRun, response: Response, user_id: str = Depends(require_lab_owner)):
    response.headers["Cache-Control"] = "no-store"
    try:
        departure = _departure(
            payload.inputs,
            ENDPOINTS[payload.inputs.start_id].get("timezone", "America/Los_Angeles"),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    emit(
        "studio.inputs",
        requestedStops=payload.inputs.num_stops,
        travelers=payload.inputs.traveler_count,
        rooms=len(payload.inputs.hotel_rooms),
        budget=payload.inputs.budget,
        attributes=len(ATTRIBUTE_KEYS),
    )
    try:
        with stage("studio.storage_begin"):
            run_id = await asyncio.to_thread(
                lab_runs.begin, user_id, payload.model_dump(mode="json")
            )
    except Exception as exc:
        storage_failure("begin", exc)
        raise HTTPException(503, "Run storage is unavailable. No experiment was started.") from exc
    started = perf_counter()
    with measuring() as telemetry:
        envelope = await execute_run(payload, user_id, departure)
        metrics = compile_metrics(envelope, telemetry, (perf_counter() - started) * 1000)
    envelope["run_record"] = {"id": run_id, "saved": False, "metrics": metrics}
    try:
        with stage("studio.storage_finish"):
            await asyncio.to_thread(lab_runs.finish, user_id, run_id, envelope, metrics)
        envelope["run_record"]["saved"] = True
    except Exception as exc:
        storage_failure("finish", exc)
        envelope["run_record"]["warning"] = (
            "Could not confirm the result was saved. Check run history; unfinished records must not count as completed."
        )
    return envelope


@router.get("/runs")
async def runs(
    response: Response,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(require_lab_owner),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        rows = await asyncio.to_thread(lab_runs.history, user_id, limit, offset)
    except Exception as exc:
        storage_failure("history", exc)
        raise HTTPException(503, "Run history is unavailable.") from exc
    return {
        "runs": rows,
        "groups": aggregate_runs(rows),
        "page_summary": {
            "completed": sum(row.get("status") == "completed" for row in rows),
            "failed": sum(row.get("status") == "failed" for row in rows),
            "unfinished": sum(row.get("status") == "running" for row in rows),
            "completion_assessed": sum(
                row.get("status") in {"completed", "failed"} for row in rows
            ),
            "completion_rate": (
                sum(row.get("status") == "completed" for row in rows)
                / sum(row.get("status") in {"completed", "failed"} for row in rows)
            )
            if any(row.get("status") in {"completed", "failed"} for row in rows)
            else None,
        },
        "limit": limit,
        "offset": offset,
        "summary_scope": "this page only",
        "next_offset": offset + limit if len(rows) == limit else None,
    }


@router.get("/runs/{run_id}/result")
async def saved_result(run_id: UUID, response: Response, user_id: str = Depends(require_lab_owner)):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = await asyncio.to_thread(lab_runs.result, user_id, run_id)
    except Exception as exc:
        raise HTTPException(503, "Saved trip results are unavailable.") from exc
    if not result or not result.get("route"):
        raise HTTPException(404, "No saved route is available for this run.")
    return result


async def execute_run(payload, user_id, departure):
    inputs = payload.inputs
    weights = normalize_weights(inputs.persona_weights)
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
        "snapshot": {
            "id": f"live-{uuid4()}",
            "label": "Fresh live discovery",
            "source": "Live provider discovery",
        },
        "route": None,
        "itinerary": None,
        "error": None,
    }
    with capture_explanation() as explanation, collecting_attempts() as attempts:
        record_explanation(weights=weights)
        record_stage(
            "inputs",
            "complete",
            "Validated trip, occupancy, preferences and departure. Nothing is saved to chat or account.",
        )
        try:
            with stage("studio.endpoints"):
                start, destination = await asyncio.gather(
                    retry_async(lambda: resolve_endpoint(inputs.start_id)),
                    retry_async(lambda: resolve_endpoint(inputs.destination_id)),
                )
            departure = _departure(inputs, start["timezone"])
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
            with stage("studio.initial_route"):
                initial = await call_route(*start["coordinates"], *destination["coordinates"])
            envelope["direct_route"] = {"distance": initial.distance, "duration": initial.duration}
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
            with stage("studio.itinerary"):
                itinerary = await build_itinerary(
                    Itinerary_Payload(route=route, start_time=datetime.fromisoformat(departure))
                )
            envelope["itinerary"] = [day.model_dump(mode="json") for day in itinerary]
            record_stage(
                "itinerary", "complete", "Built itinerary from the actual validated route."
            )
        except Exception as exc:
            # Log code locations and exception type, never provider payloads or credentials.
            logger.error(
                "Lab planning failure exception_class=%s reason=%s frames=%s",
                type(exc).__name__,
                exc.detail
                if isinstance(exc, PlanningError)
                else str(exc)
                if isinstance(exc, CandidateProviderError)
                else "unclassified",
                [(frame.name, frame.lineno) for frame in traceback.extract_tb(exc.__traceback__)],
            )
            # Never return upstream request objects, credentials, or raw provider HTML.
            message = (
                exc.detail
                if isinstance(exc, PlanningError)
                else str(exc)
                if isinstance(exc, CandidateProviderError)
                else "The live planning stage failed. Check provider configuration and retry."
            )
            code = (
                str(exc.status_code)
                if isinstance(exc, PlanningError)
                else "provider_or_planning_failure"
            )
            envelope["error"] = {"code": code, "message": message, **diagnostic(exc)}
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
                detail = envelope["error"]["message"] if failure_pending else "Not reached."
                record_stage(name, status, detail)
                if failure_pending:
                    envelope["error"]["stage"] = name
                failure_pending = False
        envelope["stages"] = explanation.pop("stages")
        envelope["explanation"] = explanation
        envelope["attempts"] = attempts
    return envelope
