"""Account-only progressive read hints, never a planner, quote or durable write."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.progress_stream import stream_turn
from app.models.route_preparation import RoutePreparationRequest
from app.routing.route_preparation import prepare_route
from app.utils.auth import require_authenticated_user

router = APIRouter()


@router.post("/route-preparation/stream", dependencies=[Depends(require_authenticated_user)])
async def route_preparation(payload: RoutePreparationRequest):
    return StreamingResponse(
        stream_turn(lambda: prepare_route(payload), stage_name="route.preparation"),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
