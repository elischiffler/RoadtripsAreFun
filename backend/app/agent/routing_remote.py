"""Remote routing proxy (B1) — run IP-whitelisted routing on the deployed backend.

TripAdvisor / hotel / Mapbox calls only work from the deployed roadtrip
backend's whitelisted IP. For LOCAL development the agent's routing tools proxy
through that deployed backend's existing HTTP endpoints, so the whitelisted IP
does the external work and we get back the same objects the local functions
would produce.

Each function here mirrors a local routing capability but calls the remote
endpoint and re-validates the JSON into the SAME Pydantic model the local path
returns — so the tool handlers, the artifact store, and the stop-dict contract
are all unchanged regardless of which path runs.

Enabled by ``ROUTING_REMOTE_URL`` (the deployed backend base URL). When unset —
i.e. running ON the deployed backend — the tools use the local functions and
this module is never touched.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.models.itinerary_models import Itinerary_Day, Itinerary_Payload
from app.models.routing_models.routing_models import MapBox, Route, Route_Payload

logger = logging.getLogger(__name__)

# Generous read timeout: a full plan does several external API calls server-side.
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


def remote_enabled() -> bool:
    """True when routing should be proxied to the deployed backend."""
    return bool(settings.ROUTING_REMOTE_URL)


def _base() -> str:
    url = (settings.ROUTING_REMOTE_URL or "").rstrip("/")
    if not url:
        raise RuntimeError("ROUTING_REMOTE_URL is not set.")
    return url


def _auth(token: str | None) -> dict[str, str]:
    if not token:
        raise ValueError("Authenticated token is required for remote routing")
    return {"Authorization": f"Bearer {token}"}


async def call_route_remote(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float, token: str | None = None
) -> MapBox.MapBox_Route:
    """Proxy ``GET /get-initial-route`` and validate into a ``MapBox_Route``."""
    params = {
        "start_lat": start_lat,
        "start_lon": start_lon,
        "end_lat": end_lat,
        "end_lon": end_lon,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_base()}/get-initial-route", params=params, headers=_auth(token))
    resp.raise_for_status()
    return MapBox.MapBox_Route.model_validate(resp.json())


async def plan_final_route_remote(
    payload: Route_Payload, token: str | None = None, *, identity_token: str | None = None
) -> Route:
    """Proxy ``POST /generate-final-route`` and validate into a ``Route``.

    The deployed endpoint runs the planner (and all whitelisted TripAdvisor /
    hotel lookups) on its side; we re-validate its response into the same
    ``Route`` the local ``plan_final_route`` returns.
    """
    body = payload.model_dump(mode="json")
    headers = _auth(token)
    if identity_token:
        headers["X-Cognito-Id-Token"] = identity_token
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_base()}/generate-final-route", json=body, headers=headers)
    resp.raise_for_status()
    return Route.model_validate(resp.json())


async def build_itinerary_remote(
    data: Itinerary_Payload, token: str | None = None
) -> list[Itinerary_Day]:
    """Proxy ``POST /generate-itinerary`` and validate into ``Itinerary_Day``s."""
    body = data.model_dump(mode="json")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_base()}/generate-itinerary", json=body, headers=_auth(token))
    resp.raise_for_status()
    return [Itinerary_Day.model_validate(day) for day in resp.json()]
