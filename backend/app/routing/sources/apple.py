"""Apple Maps Server directions in the historical road exchange shape."""

import asyncio
import math
import time
from pathlib import Path

import httpx
import jwt

from app.agent.progress import stage
from app.agent.provider_diagnostics import retry_async
from app.models.trip_limits import ROAD_MAX_COORDINATES
from app.routing import config
from app.routing.base import MapBox_route, PlanningError
from app.routing.run_metrics import increment
from app.routing.runtime import http_get, in_run, joined, limited, singleflight

APPLE_API = "https://maps-api.apple.com/v1"
PROVIDER = "apple_directions"
_token = None
_token_lock = asyncio.Lock()
_cooldown_until = 0.0


class UnusableRoadRoute(PlanningError):
    public_message = "Apple Maps could not find a usable road route for this location."
    retryable = False

    def __init__(self):
        super().__init__(self.public_message, 422)


class AppleQuotaExceeded(ValueError):
    public_message = "Apple Maps directions are temporarily limited. Try again later."
    retryable = False


def require_route_capacity(coordinate_count):
    if coordinate_count > ROAD_MAX_COORDINATES:
        raise PlanningError(
            f"Route transport capacity exceeded: {coordinate_count} coordinates including "
            f"attractions, hotels and endpoints; this planner allows {ROAD_MAX_COORDINATES}. "
            "Reduce the requested attractions or use a shorter trip.",
            422,
        )


def _signing_token():
    team, key_id = config.APPLE_MAPS_TEAM_ID, config.APPLE_MAPS_KEY_ID
    key, key_file = config.APPLE_MAPS_PRIVATE_KEY, config.APPLE_MAPS_PRIVATE_KEY_FILE
    if not team or not key_id or bool(key) == bool(key_file):
        raise PlanningError("Apple Maps Server directions are not configured.", 503)
    try:
        pem = Path(key_file).read_text() if key_file else key.replace("\\n", "\n")
        issued = int(time.time())
        return jwt.encode(
            {"iss": team, "iat": issued, "exp": issued + 900, "scope": "server_api"},
            pem,
            algorithm="ES256",
            headers={"kid": key_id, "typ": "JWT"},
        )
    except (OSError, ValueError, TypeError, jwt.PyJWTError):
        raise PlanningError("Apple Maps Server credentials could not be loaded.", 503) from None


async def _apple_request(endpoint, token, params=None):
    async def attempt():
        global _cooldown_until
        if time.monotonic() < _cooldown_until:
            raise AppleQuotaExceeded()
        with stage(PROVIDER + (".token" if endpoint == "token" else ".request")):
            increment(PROVIDER)
            response = await http_get(
                f"{APPLE_API}/{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=config.HTTP_TIMEOUT,
            )
            if response.status_code == 429:
                try:
                    wait = float(response.headers.get("Retry-After", "300"))
                except ValueError:
                    wait = 300
                _cooldown_until = time.monotonic() + max(60, min(86400, wait))
                raise AppleQuotaExceeded()
            if response.status_code >= 500 or response.status_code == 408:
                response.raise_for_status()
            return response

    return await retry_async(lambda: limited(PROVIDER, attempt))


async def _access_token(rejected=None):
    global _token
    async with _token_lock:
        if _token is not None and _token[0] != rejected and time.monotonic() < _token[1]:
            return _token[0]
        reply = await _apple_request("token", _signing_token())
        if reply.status_code != 200:
            raise PlanningError("Apple Maps Server authorization failed.", 503)
        try:
            data = reply.json()
            token, expires = data["accessToken"], data["expiresInSeconds"]
            if (
                not isinstance(token, str)
                or not token
                or isinstance(expires, bool)
                or not isinstance(expires, int)
                or expires <= 5
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise PlanningError(
                "Apple Maps Server authorization returned an invalid token.", 503
            ) from None
        _token = (token, time.monotonic() + expires - min(60, expires / 2))
        return token


def _point(latitude, longitude):
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, int | float)
        or not isinstance(longitude, int | float)
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("Invalid road coordinates")
    return float(latitude), float(longitude)


def _measure(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("Invalid directions measurement")
    return value


def _indexed(rows, index):
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError("Invalid directions path index")
    return rows[index]


def _append_contiguous(line, segment):
    if not segment or (line and line[-1] != segment[0]):
        raise ValueError("Discontinuous road geometry")
    line.extend(segment[1:] if line else segment)


def _decode_leg(payload):
    if payload["routes"] == []:
        raise UnusableRoadRoute()
    route = payload["routes"][0]
    steps = []
    line = []
    for index in route["stepIndexes"]:
        step = _indexed(payload["steps"], index)
        path = [
            list(reversed(_point(point["latitude"], point["longitude"])))
            for point in _indexed(payload["stepPaths"], step["stepPathIndex"])
        ]
        _append_contiguous(line, path)
        steps.append(
            {
                "intersections": [],
                "name": step.get("instructions"),
                "duration": _measure(step["durationSeconds"]),
                "distance": _measure(step["distanceMeters"]),
                "geometry": {"type": "LineString", "coordinates": path},
            }
        )
    if len(line) < 2:
        raise UnusableRoadRoute()
    duration = _measure(route["durationSeconds"])
    return {
        "summary": route.get("name") or "",
        "distance": _measure(route["distanceMeters"]),
        "duration": duration,
        "weight": duration,
        "steps": steps,
    }, line


async def _leg(origin, destination):
    async def directions():
        token = await _access_token()
        params = {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "transportType": "Automobile",
            "lang": "en",
        }
        reply = await _apple_request("directions", token, params)
        if reply.status_code == 401:
            token = await _access_token(rejected=token)
            reply = await _apple_request("directions", token, params)
        if reply.status_code in {400, 404}:
            raise UnusableRoadRoute()
        if reply.status_code != 200:
            raise PlanningError("Apple Maps directions authorization failed.", 503)
        try:
            return _decode_leg(reply.json())
        except UnusableRoadRoute:
            raise
        except (ValueError, KeyError, IndexError, TypeError):
            raise PlanningError("Apple Maps returned an invalid road route.", 502) from None

    return await singleflight((PROVIDER, origin, destination), directions)


@in_run
async def call_route(start_lat, start_lon, end_lat, end_lon, waypoints=None) -> MapBox_route:
    waypoint_items = waypoints.split(";") if waypoints else []
    require_route_capacity(len(waypoint_items) + 2)
    try:
        points = [_point(start_lat, start_lon)]
        for entry in waypoint_items:
            longitude, latitude = entry.split(",")
            points.append(_point(float(latitude), float(longitude)))
        points.append(_point(end_lat, end_lon))
    except (ValueError, TypeError):
        raise PlanningError("Choose valid road coordinates.", 422) from None
    if any(a == b for a, b in zip(points, points[1:], strict=False)):
        raise PlanningError("Choose different locations for consecutive stops.", 422)
    try:
        results = await joined([_leg(a, b) for a, b in zip(points, points[1:], strict=False)])
    except AppleQuotaExceeded:
        raise PlanningError(AppleQuotaExceeded.public_message, 503) from None
    except httpx.HTTPError:
        raise PlanningError("Apple Maps directions are temporarily unavailable.", 503) from None

    # Independently snapped Apple legs may disagree on which access road serves a
    # stop. Without an Apple-provided connection, the plan cannot verify that
    # driving time. Detour checks can skip that candidate, as with a missing road.
    line = []
    for _, path in results:
        if line and line[-1] != path[0]:
            raise UnusableRoadRoute()
        _append_contiguous(line, path)

    legs = [leg for leg, _ in results]
    duration = sum(leg["duration"] for leg in legs)
    return MapBox_route(
        directions_provider="apple",
        weight_name="duration",
        weight=duration,
        duration=duration,
        distance=sum(leg["distance"] for leg in legs),
        legs=legs,
        waypoints=[
            {"name": "", "location": [longitude, latitude]} for latitude, longitude in points
        ],
        geometry={"type": "LineString", "coordinates": line},
    )
