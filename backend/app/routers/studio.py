"""Password-scoped visitor access to live trip planning, independent of Cognito."""

import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.agent.progress_stream import stream_turn
from app.routers import algorithm_lab as lab

# A stable deployment secret shares sessions across workers. Local sessions expire
# on server restart when no secret is configured.
SESSION_SECRET = os.environ.get("STUDIO_SESSION_SECRET") or secrets.token_hex(32)
ISSUER = "roadtrips-studio"
router = APIRouter(prefix="/studio", tags=["studio"], route_class=lab.LabRoute)


class AccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=128)


@router.post("/access")
def access(payload: AccessRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not hmac.compare_digest(payload.password.casefold().encode(), b"cp-sat"):
        raise HTTPException(401, "Incorrect Studio password.")
    now = datetime.now(UTC)
    expiry = now + timedelta(hours=8)
    token = jwt.encode(
        {"sub": f"studio:{uuid4()}", "iss": ISSUER, "aud": ISSUER, "iat": now, "exp": expiry},
        SESSION_SECRET,
        algorithm="HS256",
    )
    return {"token": token, "expires_at": expiry.timestamp()}


def require_studio_session(x_studio_session: str | None = Header(default=None)) -> str:
    try:
        if not x_studio_session or len(x_studio_session) > 2048:
            raise ValueError("Missing session")
        claims = jwt.decode(
            x_studio_session,
            SESSION_SECRET,
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=ISSUER,
            options={"require": ["sub", "iss", "aud", "iat", "exp"]},
        )
        subject = claims["sub"]
        if not subject.startswith("studio:"):
            raise ValueError("Invalid scope")
        UUID(subject.removeprefix("studio:"))
        return subject
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(401, "Enter the Studio password to continue.") from exc


@router.get("/presets")
async def presets(response: Response, user_id: str = Depends(require_studio_session)):
    return await lab.presets(response, user_id)


@router.post("/run")
async def run(
    payload: lab.LabRun, response: Response, user_id: str = Depends(require_studio_session)
):
    return await lab.run(payload, response, user_id)


@router.get("/runs")
async def runs(
    response: Response,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(require_studio_session),
):
    return await lab.runs(response, limit, offset, user_id)


@router.get("/runs/{run_id}/result")
async def result(run_id: UUID, response: Response, user_id: str = Depends(require_studio_session)):
    return await lab.saved_result(run_id, response, user_id)


@router.post("/run/stream")
async def streamed_run(payload: lab.LabRun, user_id: str = Depends(require_studio_session)):
    # Validate inputs and visitor access before sending streaming response headers.
    async def execute():
        result = await lab.run(payload, Response(), user_id)
        return RootModel[dict](result)

    return StreamingResponse(
        stream_turn(execute, stage_name="studio.run"),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
