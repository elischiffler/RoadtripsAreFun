"""Explicit complete-candidate assessment, followed by an account-owned choice."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute

from app.agent.departure import is_upcoming_departure
from app.agent.progress import emit
from app.agent.progress_stream import stream_turn
from app.core.candidate_errors import CandidateHTTPError, public_candidate_error
from app.core.departure_errors import DepartureNotUpcomingHTTPError
from app.models.planning_candidates import (
    AssessmentRegistration,
    CandidateConfirmation,
    CandidateRequest,
    CandidateResponse,
    OneDayAssessment,
)
from app.models.routing_models.routing_models import Route
from app.routers import routing_api
from app.routing.base import DepartureNotUpcoming, PlanningError
from app.routing.catalog_calendars import refresh_for_timing
from app.routing.lodging import LodgingCoverageConflict
from app.routing.planning_candidates import store
from app.routing.route_preparation import candidate_stay_areas, preview_details
from app.routing.travel_timing import apply_timing
from app.routing.trip_modes import (
    ONE_DAY_SECONDS,
    DepartureOutsideRhythm,
    OneDayIneligible,
    RhythmAvailabilityConflict,
    RhythmClockConflict,
    UnsupportedOvernightRhythm,
    one_day_elapsed,
    require_one_day,
)
from app.utils.auth import require_authenticated_user


class CandidateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def controlled(request):
            try:
                response = await handler(request)
            except CandidateHTTPError as error:
                status, code, message = public_candidate_error(error)
                response = JSONResponse(
                    status_code=status, content={"code": code, "detail": message}
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return controlled


router = APIRouter(route_class=CandidateRoute)


def public_failure(error):
    if isinstance(error, CandidateHTTPError):
        raise error
    if isinstance(error, DepartureNotUpcoming):
        raise DepartureNotUpcomingHTTPError() from None
    if isinstance(error, LodgingCoverageConflict):
        raise CandidateHTTPError("lodging_stay_conflict") from None
    if isinstance(error, UnsupportedOvernightRhythm):
        raise CandidateHTTPError("unsupported_overnight_rhythm") from None
    if isinstance(error, RhythmAvailabilityConflict):
        raise CandidateHTTPError("rhythm_availability_conflict") from None
    if isinstance(error, RhythmClockConflict):
        raise CandidateHTTPError("rhythm_clock_conflict") from None
    if isinstance(error, DepartureOutsideRhythm):
        raise CandidateHTTPError("departure_outside_rhythm") from None
    if isinstance(error, OneDayIneligible):
        raise CandidateHTTPError("one_day_ineligible") from None
    if isinstance(error, PlanningError) and error.status_code == 422:
        raise CandidateHTTPError("candidate_cannot_fit") from None
    raise CandidateHTTPError("candidate_unavailable") from None


async def _assess(payload, owner, *, can_select=False, request=None):
    context = {}
    candidate = payload.model_copy(
        update={"trip_mode": "one_day", "hotel_rooms": None, "budget": 0}, deep=True
    )
    route = None
    # Road-only hints never decide eligibility. Actual candidate timing remains
    # authoritative for one-day feasibility, visits, local clocks and meals.
    areas = candidate_stay_areas(payload.initial_route, payload.start, payload.scheduling_policy)
    emit(
        "preparation.areas",
        **preview_details(
            "preparing", payload.initial_route.geometry.model_dump(), [], areas=areas
        ),
    )
    try:
        route = await routing_api.plan_final_route(
            candidate,
            user_id=owner,
            can_select_algorithm=can_select,
            candidate_context=context,
            assess_only=True,
        )
        elapsed = one_day_elapsed(route)
        if elapsed < ONE_DAY_SECONDS:
            require_one_day(route)
        assessment = OneDayAssessment(
            eligible=elapsed < ONE_DAY_SECONDS,
            elapsed_seconds=elapsed,
            reason_code=None if elapsed < ONE_DAY_SECONDS else "elapsed_limit",
            reason=None
            if elapsed < ONE_DAY_SECONDS
            else "This complete candidate takes 12 hours or more, including visits, waits and meals.",
        )
    except PlanningError as error:
        if isinstance(
            error, (RhythmAvailabilityConflict, RhythmClockConflict, DepartureOutsideRhythm)
        ):
            public_failure(error)
        if error.status_code != 422 or context.get("verified_candidates") is None:
            public_failure(error)
        assessment = OneDayAssessment(
            eligible=False,
            reason_code="candidate_cannot_fit",
            reason="No complete one-day candidate passed actual road, visit, meal and local driving-window checks. Consider overnight planning or revise your trip.",
        )
    except Exception as error:
        public_failure(error)
    if request is not None and await request.is_disconnected():
        raise CandidateHTTPError("candidate_cancelled")
    return store.add(owner, payload, context, assessment, route, areas=areas)


async def assess(payload, owner, *, can_select=False, request=None):
    record, leader = store.start_request(owner, payload)
    if not leader:
        return (await asyncio.shield(asyncio.wrap_future(record.future))).model_copy(deep=True)
    try:
        response = await _assess(payload, owner, can_select=can_select, request=request)
        store.end_request(record, response=response)
        return response
    except asyncio.CancelledError:
        store.cancel_request(owner, payload.request_id)
        raise
    except Exception as error:
        # Cache the typed public failure too. A retry of an uncertain assessment
        # ID cannot restart model work after an error or a lost response.
        store.end_request(record, error=error)
        raise


@router.post("/planning-candidates/requests")
async def register_request(
    value: AssessmentRegistration, owner: str = Depends(require_authenticated_user)
):
    expires = store.register(owner, value.request_id)
    return {"request_id": str(value.request_id), "expires_at": expires, "status": "ready"}


@router.delete("/planning-candidates/requests/{request_id}")
async def cancel_request(request_id: UUID, owner: str = Depends(require_authenticated_user)):
    store.cancel_request(owner, request_id)
    return {"status": "cancelled"}


@router.post("/planning-candidates", response_model=CandidateResponse)
async def check_options(
    payload: CandidateRequest,
    request: Request,
    owner: str = Depends(require_authenticated_user),
    x_cognito_id_token: str | None = Header(default=None),
):
    can_select = bool(routing_api.owner_routing_claims(owner, x_cognito_id_token))
    return await assess(payload, owner, can_select=can_select, request=request)


@router.post("/planning-candidates/stream")
async def stream_options(
    payload: CandidateRequest,
    request: Request,
    owner: str = Depends(require_authenticated_user),
    x_cognito_id_token: str | None = Header(default=None),
):
    can_select = bool(routing_api.owner_routing_claims(owner, x_cognito_id_token))

    async def run():
        return await assess(payload, owner, can_select=can_select)

    return StreamingResponse(
        stream_turn(run, stage_name="route.assessment"),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.delete("/planning-candidates/{token}")
async def cancel_options(token: str, owner: str = Depends(require_authenticated_user)):
    store.cancel(owner, token)
    return {"status": "cancelled"}


@router.post("/planning-candidates/{token}/confirm", response_model=Route)
async def confirm_options(
    token: str, value: CandidateConfirmation, owner: str = Depends(require_authenticated_user)
):
    entry, already = store.begin(owner, token, value)
    try:
        if not is_upcoming_departure(entry.payload.start):
            raise DepartureNotUpcoming()
        if (
            entry.payload.traveler_count is not None
            and value.traveler_count is not None
            and entry.payload.traveler_count != value.traveler_count
        ):
            raise CandidateHTTPError("candidate_inputs_changed")
        if already is not None:
            return already
        if value.trip_mode == "one_day":
            if not entry.response.one_day.eligible or entry.response.candidate_route is None:
                raise CandidateHTTPError("one_day_ineligible")
            route = entry.response.candidate_route.model_copy(deep=True)
            await refresh_for_timing(route.stops or [])
            apply_timing(
                route.stops or [],
                route.departure_time,
                route.scheduling_policy,
                route.start_timezone,
                reserve_meal_slots=route.reserve_meal_slots,
            )
            require_one_day(route)
        else:
            if entry.context.get("verified_candidates") is None:
                raise CandidateHTTPError("candidate_expired")
            payload = entry.payload.model_copy(
                update={
                    "trip_mode": "overnight",
                    "budget": value.budget,
                    "traveler_count": value.traveler_count,
                    "hotel_rooms": value.hotel_rooms,
                },
                deep=True,
            )
            # No new attraction discovery/ratings: only the stored verified pool.
            route = await routing_api.plan_final_route(
                payload, user_id=owner, candidate_context=entry.context.copy()
            )
        return store.finish(owner, token, value, route)
    except HTTPException:
        raise
    except Exception as error:
        public_failure(error)
    finally:
        store.release(owner, token)
