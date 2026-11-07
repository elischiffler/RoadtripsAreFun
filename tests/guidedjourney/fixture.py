"""Test-only HTTP bootstrap: signed synthetic auth and provider fixtures, real app/DB.

Not imported by application code or included in a production image. The runner
supplies a new disposable PostgreSQL instance; startup refuses every other host.
"""

import asyncio
import importlib
import itertools
import json
import math
import os
import socket
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

target = urlparse(os.environ.get("DATABASE_URL", ""))
if (
    target.hostname not in {"postgres", "127.0.0.1", "localhost"}
    or target.path != "/roadtrips"
    or target.username != "postgres"
    or target.password != "disposable-guided-only"
    or os.environ.get("GUIDED_JOURNEY_FIXTURE") != "disposable-local-only"
    or target.scheme != "postgresql"
    or target.query
    or target.fragment
    or target.port not in ({None, 5432} if target.hostname == "postgres" else {6543})
):
    raise RuntimeError(
        "Guided fixture requires its disposable local roadtrips database"
    )
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["COGNITO_USER_POOL_ID"] = "us-west-1_fixture"
os.environ["COGNITO_APP_CLIENT_ID"] = "localfixture"
os.environ["STUDIO_RESEARCH_DATABASE"] = "false"
os.environ["PLACE_TRAITS_CACHE_ENABLED"] = "false"
os.environ["SUPABASE_URL"] = "http://127.0.0.1:9009"
os.environ["SUPABASE_ANON_KEY"] = "synthetic-anon-key"
os.environ["MENTRO_GATEWAY_URL"] = "http://127.0.0.1:9009"
os.environ["MENTRO_SERVICE_EMAIL"] = "fixture@example.test"
os.environ["MENTRO_SERVICE_PASSWORD"] = "fixture-only"
os.environ.pop("LOCAL_PREVIEW", None)
os.environ.pop("ROADTRIPS_DATABASE_TARGET", None)
os.environ.pop("ROUTING_REMOTE_URL", None)

# Block accidental Python provider connections; libpq is confined by Compose's
# internal network and the exact database URL check above.
real_connect = socket.socket.connect
real_connect_ex = socket.socket.connect_ex
real_dns = socket.getaddrinfo
blocked_network = []


def local_dns(host, *args, **kwargs):
    if host not in {None, "postgres", "localhost", "127.0.0.1", "::1"}:
        blocked_network.append("dns")
        raise OSError("Guided fixture prohibits external DNS")
    return real_dns(host, *args, **kwargs)


def local_connect(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6} and address[0] not in {
        "127.0.0.1",
        "::1",
    }:
        blocked_network.append("socket")
        raise OSError("Guided fixture prohibits provider sockets")
    return real_connect(sock, address)


socket.getaddrinfo = local_dns
socket.socket.connect = local_connect


def local_connect_ex(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6} and address[0] not in {
        "127.0.0.1",
        "::1",
    }:
        blocked_network.append("socket_ex")
        raise OSError("Guided fixture prohibits provider sockets")
    return real_connect_ex(sock, address)


socket.socket.connect_ex = local_connect_ex
backend_root = (
    Path("/app")
    if Path("/app/app/main.py").is_file()
    else Path(__file__).resolve().parents[2] / "backend"
)
sys.path.insert(0, str(backend_root))

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False
import jwt
import psycopg2
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

with (
    psycopg2.connect(
        os.environ["DATABASE_URL"], sslmode="disable"
    ) as marker_connection,
    marker_connection.cursor() as marker_cursor,
):
    marker_cursor.execute("SELECT marker FROM guided_journey_fixture_marker")
    if marker_cursor.fetchall() != [("disposable-local-only",)]:
        raise RuntimeError("Refusing a database without the isolated journey marker")

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
jwk.update(kid="guided-fixture", use="sig", alg="RS256")
jwt.PyJWKClient.fetch_data = lambda self: {"keys": [jwk]}

# Preserve production entry-point initialization before injecting source seams.
app = importlib.import_module("app.main").app

from app.agent.persona import ATTRIBUTE_KEYS
from app.catalog import repository
from app.models.routing_models.routing_models import MapBox
from app.routers import location_api, routing_api
from app.routing import alternatives
from app.routing.planners import cp_sat

counts = {
    "login": 0,
    "roads": 0,
    "catalog": 0,
    "ratings": 0,
    "durations": 0,
    "gateway_auth": 0,
    "gateway_requests": 0,
    "solver": 0,
    "hotel_requests": 0,
    "browse": 0,
    "current_facts": 0,
    "requests": [],
    "stream_events": [],
}


def location(*, coords=None, address=None, exactly_one=True, **kwargs):
    del kwargs
    start = address is None or "Boulder" in address
    lat, lon = coords if coords else ([40.0, -105.0] if start else [40.4, -104.0])
    result = SimpleNamespace(
        address="Boulder, Colorado" if start else "Fort Morgan, Colorado",
        latitude=lat,
        longitude=lon,
        raw={"annotations": {"timezone": {"name": "America/Denver"}}},
    )
    return result if exactly_one else [result]


async def roads(start_lat, start_lon, end_lat, end_lon, waypoints=None):
    counts["roads"] += 1
    points = [[start_lon, start_lat]]
    if waypoints:
        points += [
            [float(part) for part in point.split(",")] for point in waypoints.split(";")
        ]
    points.append([end_lon, end_lat])
    lengths = [math.dist(a, b) for a, b in itertools.pairwise(points)]
    durations = [length / math.hypot(1, 0.4) * 7200 for length in lengths]
    return MapBox.MapBox_Route(
        geometry={"type": "LineString", "coordinates": points},
        duration=sum(durations),
        distance=sum(lengths) * 100000,
        weight=sum(durations),
        weight_name="duration",
        legs=[
            {
                "duration": duration,
                "distance": length * 100000,
                "weight": duration,
                "steps": [],
                "admins": [],
                "summary": "Synthetic provider road",
            }
            for length, duration in zip(lengths, durations)
        ],
    )


def catalog_page(point, *args, **kwargs):
    del args, kwargs
    counts["catalog"] += 1
    identifier = f"{point[0]:.6f}:{point[1]:.6f}"
    return repository.CatalogPage(
        [
            {
                "provider_id": f"fixture:{identifier}",
                "name": f"Synthetic overlook {identifier}",
                "coordinates": list(point),
                "address": "Synthetic address",
                "categories": ["daytime"],
                "source": "synthetic-test-fixture",
                "source_provenance": [],
            }
        ],
        None,
    )


# Frozen source facts are a repository/provider seam, not a planner or route-edit
# stub. Real browse admission, current-fact refresh, geometry, timing and CRUD run.
EDIT_PLACE = {
    "provider_id": "overture:guided-edit",
    "name": "Synthetic edit stop",
    "coordinates": [40.168, -104.58],
    "address": "Synthetic edit address",
    "categories": ["daytime"],
    "source": "overture",
    "source_release": "synthetic-test-fixture",
    "source_attribution": "Synthetic catalog fixture",
    "source_provenance": [],
}


def nearby(*args, **kwargs):
    counts["browse"] += 1
    return [deepcopy(EDIT_PLACE)]


def current_records(source_ids, *args, **kwargs):
    counts["current_facts"] += 1
    return {sid: deepcopy(EDIT_PLACE) for sid in source_ids if sid == "guided-edit"}


async def hotels(*args, **kwargs):
    counts["hotel_requests"] += 1
    raise AssertionError(
        "Short guided fixture unexpectedly requested an overnight hotel"
    )


original_select = cp_sat.select_attractions


def counted_select(*args, **kwargs):
    counts["solver"] += 1
    return original_select(*args, **kwargs)


cp_sat.select_attractions = counted_select
location_api.get_location = location
routing_api.get_location = location
routing_api._call_route = roads
routing_api.hotel_candidates = hotels
repository.nearby_page = catalog_page
repository.nearby = nearby
alternatives.catalog_nearby = nearby
repository.current_records = current_records


@app.middleware("http")
async def record_requests(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        counts["requests"].append(
            {"method": request.method, "path": request.url.path, "status": 500}
        )
        raise
    if not request.url.path.startswith("/fixture/"):
        counts["requests"].append(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            }
        )
    if (
        request.url.path
        in {"/generate-final-route/stream", "/planning-candidates/stream"}
        and response.status_code == 200
    ):
        original = response.body_iterator

        async def observe_stream():
            pending = ""
            async for chunk in original:
                pending += chunk.decode() if isinstance(chunk, bytes) else chunk
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    if line.strip():
                        event = json.loads(line)
                        counts["stream_events"].append(
                            {
                                "type": event.get("type"),
                                "status": event.get("status"),
                                "code": event.get("code"),
                            }
                        )
                yield chunk

        response.body_iterator = observe_stream()
    return response


@app.get("/fixture/report")
def report():
    from app.crud.chat_crud import _get_conn, _put_conn

    connection = _get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM chats WHERE user_id = %s", ("guided-traveler",)
            )
            stored = cursor.fetchone()[0]
            cursor.execute(
                "SELECT chat_data, chat_log FROM chats WHERE user_id = %s ORDER BY chat_id",
                ("guided-traveler",),
            )
            trips = [{"data": row[0], "log": row[1]} for row in cursor.fetchall()]
            cursor.execute(
                """SELECT mem_key, mem_value FROM chat_memory
                   WHERE user_id = %s AND chat_id = '' AND mem_type = %s
                   ORDER BY mem_key""",
                ("guided-traveler", "preference_profile"),
            )
            profiles = [{"id": row[0], **row[1]} for row in cursor.fetchall()]
    finally:
        _put_conn(connection)
    # Only this disposable synthetic account exists here. Never expose a real
    # auth token; snapshots let browser assertions verify actual durable state.
    return counts | {
        "stored_trips": stored,
        "trips": trips,
        "profiles": profiles,
        "blocked_network": blocked_network,
    }


identity = FastAPI()
identity.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8082"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@identity.post("/")
async def authenticate(request: Request):
    body = await request.json()
    if (
        body.get("AuthFlow") != "USER_PASSWORD_AUTH"
        or body.get("ClientId") != "localfixture"
    ):
        return JSONResponse({"__type": "NotAuthorizedException"}, status_code=400)
    if body.get("AuthParameters") != {
        "USERNAME": "traveler@example.test",
        "PASSWORD": "fixture-only",
    }:
        return JSONResponse({"__type": "NotAuthorizedException"}, status_code=400)
    counts["login"] += 1
    now = datetime.now(UTC)
    claims = {
        "iss": "https://cognito-idp.us-west-1.amazonaws.com/us-west-1_fixture",
        "sub": "guided-traveler",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    sign = lambda extra: jwt.encode(
        claims | extra, key, algorithm="RS256", headers={"kid": "guided-fixture"}
    )
    return {
        "AuthenticationResult": {
            "AccessToken": sign({"token_use": "access", "client_id": "localfixture"}),
            "IdToken": sign(
                {
                    "token_use": "id",
                    "aud": "localfixture",
                    "email": "traveler@example.test",
                    "email_verified": True,
                }
            ),
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
        }
    }


providers = FastAPI()


@providers.post("/auth/v1/token")
async def service_auth(request: Request):
    assert request.query_params.get("grant_type") == "password"
    assert request.headers.get("apikey") == "synthetic-anon-key"
    assert await request.json() == {
        "email": "fixture@example.test",
        "password": "fixture-only",
    }
    counts["gateway_auth"] += 1
    return {"access_token": "fixture-gateway-token", "expires_in": 3600}


@providers.post("/api/chat/stream-full")
async def gateway(request: Request):
    counts["gateway_requests"] += 1
    assert request.headers.get("authorization") == "Bearer fixture-gateway-token"
    raw = await request.body()
    assert len(raw) <= 256 * 1024
    body = json.loads(raw)
    assert set(body) == {"messages"}
    messages = body["messages"]
    assert 1 <= len(messages) <= 50
    assert all(
        set(message) == {"role", "content"}
        and message["role"] in {"system", "user", "assistant"}
        and isinstance(message["content"], str)
        and 0 < len(message["content"]) <= 32000
        for message in messages
    )
    assert sum(len(message["content"]) for message in messages) <= 128000
    prompt = messages[-1]["content"]
    if "Rate only these source-record names, preserving each exactly: " in prompt:
        names = json.loads(
            prompt.split(
                "Rate only these source-record names, preserving each exactly: ", 1
            )[1]
        )
        content = {
            "candidates": [
                {"name": name, "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.8)}
                for name in names
            ]
        }
        counts["ratings"] += 1
    elif "Return only strict JSON" in prompt and '"estimates"' in prompt:
        contexts = json.loads(prompt.rsplit("\n", 1)[1])
        content = {
            "estimates": [
                {"provider_id": context["place"]["provider_id"], "minutes": 45}
                for context in contexts
            ]
        }
        counts["durations"] += 1
    else:
        raise AssertionError(
            "Unexpected provider prompt; this fixture never contacts live AI"
        )
    event = {
        "content": json.dumps(content),
        "provider": "synthetic-gateway",
        "tier": "fixture",
    }
    return Response(
        "event: end\ndata: " + json.dumps(event) + "\n\n",
        media_type="text/event-stream",
    )


async def main():
    await asyncio.gather(
        uvicorn.Server(
            uvicorn.Config(app, host="0.0.0.0", port=8002, log_level="warning")
        ).serve(),
        uvicorn.Server(
            uvicorn.Config(identity, host="0.0.0.0", port=8999, log_level="warning")
        ).serve(),
        uvicorn.Server(
            uvicorn.Config(providers, host="127.0.0.1", port=9009, log_level="warning")
        ).serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
