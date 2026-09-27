"""Disposable HTTP launch for a signed-token Roadtrips journey.

Mounted into the unmodified runtime image. Never copied into that image.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import jwt
import requests
import uvicorn
from app.core.config import settings

if not settings.LOCAL_PREVIEW or os.environ.get("JOURNEY_FIXTURE") != "isolated-only":
    raise RuntimeError("The journey launcher requires explicit isolated local mode")

from app.agent.providers import MentroGatewayProvider, SupabaseServiceAuth
from app.agent.schemas import LLMResponse
from app.main import app
from app.routers import location_api, routing_api
from app.utils import auth

key_path = Path("/fixtures") / (os.environ["JOURNEY_RUN_ID"] + ".public.pem")
public_key = key_path.read_bytes()
fixture_issuer = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_LOCALJOURNEY"
fixture_client = "localjourneyclient"


class FixtureJwks:
    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != "local-journey-key":
            raise jwt.InvalidTokenError("Unknown local fixture key")
        return SimpleNamespace(key=public_key)


# The production verifier still checks RS256, issuer, client, token use and time.
auth._cognito_settings = lambda: (fixture_issuer, fixture_client)
auth._jwks_client = lambda issuer: FixtureJwks() if issuer == fixture_issuer else None

# Only this disposable process opens business routes. The normal preview remains
# guarded. Startup has already validated its local DB/Mentro/Auth destinations.
settings.LOCAL_PREVIEW = False

LOCATIONS = {
    "San Luis Obispo, CA": (35.2828, -120.6596),
    "Santa Barbara, CA": (34.4208, -119.6982),
    "Denver, CO": (39.7392, -104.9903),
}


def fixture_location(*, geocoder, address=None, coords=None):
    if address is not None:
        if address not in LOCATIONS:
            return None
        lat, lon = LOCATIONS[address]
        return SimpleNamespace(address=address, latitude=lat, longitude=lon)
    if coords is not None:
        for name, (lat, lon) in LOCATIONS.items():
            if (
                abs(float(coords[0]) - lat) < 0.001
                and abs(float(coords[1]) - lon) < 0.001
            ):
                return SimpleNamespace(address=name, latitude=lat, longitude=lon)
    return None


location_api.get_location = fixture_location
routing_api.get_location = fixture_location


def fixture_mapbox(url, *, params, timeout):
    prefix = "https://api.mapbox.com/directions/v5/mapbox/driving/"
    if not url.startswith(prefix) or params.get("access_token") is not None:
        raise RuntimeError("Unapproved provider request")
    points = [
        tuple(map(float, pair.split(","))) for pair in url[len(prefix) :].split(";")
    ]
    if len(points) != 2 or points != [(-120.6596, 35.2828), (-119.6982, 34.4208)]:
        raise RuntimeError("Unseeded route request")
    start, end = points
    middle = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
    geometry = {"type": "LineString", "coordinates": [list(start), middle, list(end)]}
    step = {
        "distance": 160000.0,
        "duration": 7200.0,
        "intersections": [],
        "geometry": geometry,
        "maneuver": {
            "type": "depart",
            "instruction": "Drive south",
            "bearing_after": 180,
            "bearing_before": 0,
            "location": list(start),
        },
    }
    route = {
        "weight_name": "auto",
        "weight": 7200.0,
        "distance": 160000.0,
        "duration": 7200.0,
        "geometry": geometry,
        "legs": [
            {
                "weight": 7200.0,
                "duration": 7200.0,
                "distance": 160000.0,
                "summary": "US-101 S",
                "steps": [step],
            }
        ],
    }
    payload = {
        "code": "Ok",
        "uuid": "local-journey-route",
        "routes": [route],
        "waypoints": [],
    }
    return SimpleNamespace(json=lambda: json.loads(json.dumps(payload)))


# Mapbox's only transport is requests.get. Unexpected use fails closed.
requests.get = fixture_mapbox
SupabaseServiceAuth.configured = lambda self: True
SupabaseServiceAuth.get_token = lambda self: "local-fixture-token"

original_complete = MentroGatewayProvider.complete


def fixture_complete(self, messages, tools):
    request = next(
        (message.content for message in reversed(messages) if message.role == "user"),
        "",
    )
    if request in {"[fixture:remember]", "[fixture:recall]"}:
        if messages[-1].role == "tool":
            if request == "[fixture:remember]":
                return LLMResponse(
                    content="Preference saved.", provider="fixture:local"
                )
            found = "quiet routes" in messages[-1].content
            return LLMResponse(
                content="Prefers quiet routes." if found else "No saved preference.",
                provider="fixture:local",
            )
        call = (
            ("remember_fact", {"key": "route_preference", "value": "quiet routes"})
            if request == "[fixture:remember]"
            else ("recall_facts", {})
        )
        return LLMResponse(
            content="```tool\n"
            + json.dumps({"name": call[0], "arguments": call[1]})
            + "\n```",
            provider="fixture:local",
        )
    return original_complete(self, messages, tools)


MentroGatewayProvider.complete = fixture_complete

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
