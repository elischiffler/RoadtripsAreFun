"""Ordinary account trip progress and read-only nearby browsing, all boundaries mocked."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.progress import stage
from app.models.routing_models.routing_models import Route
from app.routers import routing_api
from app.routing import PlanningError
from app.routing import alternatives as browsing
from app.utils.auth import require_authenticated_user


def _app(*, authenticated=True):
    app = FastAPI()
    app.include_router(routing_api.router)
    if authenticated:
        app.dependency_overrides[require_authenticated_user] = lambda: "fixture-account"
    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routing_api, "owner_routing_claims", lambda *_: None)
    # No main-app lifespan, database initialization or external provider is run.
    return TestClient(_app())


def _payload():
    return {
        "initial_route": {
            "weight_name": "auto",
            "weight": 3600,
            "duration": 3600,
            "distance": 50000,
            "legs": [],
            "geometry": {
                "type": "LineString",
                "coordinates": [[-105, 40], [-104.9, 39.7]],
            },
        },
        "num_stops": 1,
        "budget": 150,
        "start": "2027-06-01T09:00:00",
        "traveler_count": 1,
        "hotel_rooms": [{"adults": 1, "child_ages": []}],
    }


def _route():
    return Route(
        coordinates=[[40, -105], [39.7, -104.9]],
        distance=50000,
        duration=3600,
        steps=[],
        stops=[],
        geometry={"type": "LineString", "coordinates": [[-105, 40], [-104.9, 39.7]]},
        cost=0,
    )


def _place(provider_id="boulder:284", **changes):
    return {
        "provider_id": provider_id,
        "source": "boulder-osmp",
        "name": "A source-listed trailhead",
        "coordinates": [40, -105],
        "address": "A source address",
        "url": "https://example.org/source-place",
        "categories": ["daytime", "trailhead"],
        "source_attribution": "Retained source credit",
        "source_release": "reviewed-fixture-release",
        "source_updated_at": "2026-10-21",
        "source_provenance": [{"source_url": "https://example.org/source", "release": "r1"}],
        "unrelated_internal_field": "not a public response field",
        **changes,
    }


def test_stream_delivers_real_worker_events_then_route(client, monkeypatch):
    calls = []

    async def planned(payload, **kwargs):
        calls.append((payload, kwargs))
        with stage("route.final_reroute", waypoints=3):
            pass
        return _route()

    monkeypatch.setattr(routing_api, "plan_final_route", planned)
    response = client.post("/generate-final-route/stream", json=_payload())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["cache-control"] == "no-store"
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1] == {"type": "result", "response": _route().model_dump(mode="json")}
    reroutes = [event for event in events if event.get("stage") == "route.final_reroute"]
    assert [event["state"] for event in reroutes] == ["started", "completed"]
    assert reroutes[0]["waypoints"] == 3
    assert calls[0][1] == {"user_id": "fixture-account", "can_select_algorithm": False}
    assert calls[0][0].hotel_rooms[0].adults == 1


@pytest.mark.parametrize("owner", [False, True])
def test_stream_and_nonstream_preserve_owner_selection_contract(client, monkeypatch, owner):
    verified = []

    def claims(subject, id_token):
        verified.append((subject, id_token))
        return {"sub": subject} if owner else None

    monkeypatch.setattr(routing_api, "owner_routing_claims", claims)
    planner = AsyncMock(return_value=_route())
    monkeypatch.setattr(routing_api, "plan_final_route", planner)
    headers = {"X-Cognito-Id-Token": "fixture-identity-token"}
    payload = _payload() | {"algorithm": "requested-algorithm"}
    assert (
        client.post("/generate-final-route/stream", json=payload, headers=headers).status_code
        == 200
    )
    assert client.post("/generate-final-route", json=payload, headers=headers).status_code == 200
    assert verified == [("fixture-account", "fixture-identity-token")] * 2
    assert [call.kwargs["can_select_algorithm"] for call in planner.call_args_list] == [
        owner,
        owner,
    ]
    assert all(call.args[0].algorithm == "requested-algorithm" for call in planner.call_args_list)


def test_invalid_stream_payload_fails_before_worker_starts(client, monkeypatch):
    planner = AsyncMock(return_value=_route())
    monkeypatch.setattr(routing_api, "plan_final_route", planner)
    response = client.post("/generate-final-route/stream", json=_payload() | {"num_stops": -1})
    assert response.status_code == 422
    assert "Invalid route request" in response.json()["detail"]
    assert "application/x-ndjson" not in response.headers.get("content-type", "")
    assert client.post("/generate-final-route/stream", content="not-json").status_code == 422
    planner.assert_not_called()


@pytest.mark.parametrize(
    "failure,status",
    [(PlanningError("trip cannot fit", 422), 422), (RuntimeError("secret-provider-token"), 503)],
)
def test_stream_runtime_failures_preserve_status_without_private_details(
    client, monkeypatch, failure, status
):
    planner = AsyncMock(side_effect=failure)
    monkeypatch.setattr(routing_api, "plan_final_route", planner)
    response = client.post("/generate-final-route/stream", json=_payload())
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1] == {"type": "error", "status": status}
    assert not any(event["type"] == "result" for event in events)
    assert "secret-provider-token" not in response.text
    assert "trip cannot fit" not in response.text
    planner.assert_awaited_once()


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/generate-final-route/stream", _payload()),
        ("/route-alternatives", {"points": [[40, -105]]}),
    ],
)
def test_both_routes_require_account_auth_and_reject_studio_identity(monkeypatch, path, payload):
    planner = AsyncMock(return_value=_route())
    monkeypatch.setattr(routing_api, "plan_final_route", planner)
    nearby = []
    monkeypatch.setattr(browsing, "catalog_nearby", lambda *args, **kwargs: nearby.append(args))
    response = TestClient(_app(authenticated=False)).post(
        path,
        json=payload,
        headers={"X-Studio-Session": "visitor-session-does-not-authorize-account"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"
    planner.assert_not_called()
    assert nearby == []


def test_nearby_uses_held_catalog_boundary_deduplicates_and_preserves_source(client, monkeypatch):
    calls = []

    def nearby(point, categories, **kwargs):
        calls.append((point, categories, kwargs))
        return [_place("boulder:skip"), _place(), _place(), _place("boulder:second")]

    monkeypatch.setattr(browsing, "catalog_nearby", nearby)
    response = client.post(
        "/route-alternatives",
        json={"points": [[40, -105], [40, -105], [39.7, -104.9]], "exclude_ids": ["boulder:skip"]},
    )
    assert response.status_code == 200
    result = response.json()
    assert [place["id"] for place in result["places"]] == ["boulder:284", "boulder:second"]
    assert result["places"][0]["provider_id"] == "boulder:284"
    for field in (
        "coordinates",
        "source",
        "source_attribution",
        "source_provenance",
        "source_release",
        "source_updated_at",
    ):
        assert result["places"][0][field] == _place()[field]
    assert "unrelated_internal_field" not in result["places"][0]
    assert "not in your itinerary" in result["notice"]
    assert len(calls) == 2
    assert all(call[1] == ["daytime"] for call in calls)
    assert all(
        call[2] == {"radius_miles": 5, "limit": 12, "require_visit_calendar": True}
        for call in calls
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"points": []},
        {"points": [[40, -105]] * 9},
        {"points": [[91, 0]]},
        {"points": [[0, 181]]},
        {"points": [[True, 0]]},
        {"points": [["40", -105]]},
        {"points": [[40, -105, 1]]},
        {"points": [[40, -105]], "exclude_ids": ["x"] * 101},
        {"points": [[40, -105]], "exclude_ids": ["x" * 513]},
        {"points": [[40, -105]], "radius_miles": 1000},
    ],
)
def test_nearby_rejects_unbounded_or_invalid_inputs_before_catalog(client, monkeypatch, payload):
    called = []
    monkeypatch.setattr(browsing, "catalog_nearby", lambda *args, **kwargs: called.append(args))
    assert client.post("/route-alternatives", json=payload).status_code == 422
    assert called == []


def test_nearby_caps_results_and_skips_invalid_records_and_unsafe_urls(client, monkeypatch):
    calls = []

    def nearby(*args, **kwargs):
        calls.append(args)
        return [
            _place("boulder:bad-coordinates", coordinates=[900, 0]),
            _place("boulder:no-name", name=""),
            _place("boulder:unsafe-url", url="javascript:alert(1)"),
            *[_place(f"boulder:{index}") for index in range(20)],
        ]

    monkeypatch.setattr(browsing, "catalog_nearby", nearby)
    result = client.post("/route-alternatives", json={"points": [[40, -105], [41, -105]]}).json()
    assert len(result["places"]) == 12
    assert len(calls) == 1
    assert result["places"][0]["id"] == "boulder:unsafe-url"
    assert result["places"][0]["url"] is None


@pytest.mark.parametrize("coordinate", ["NaN", "Infinity", "1e400"])
def test_nonfinite_browse_coordinates_return_serializable_422(client, monkeypatch, coordinate):
    called = []
    monkeypatch.setattr(browsing, "catalog_nearby", lambda *args, **kwargs: called.append(args))
    response = client.post(
        "/route-alternatives",
        content='{"points":[[' + coordinate + ",0]]}",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "finite_number"
    assert "input" not in response.json()["detail"][0]
    assert called == []


def test_nearby_empty_and_unavailable_are_honest_without_mutating_route(client, monkeypatch):
    monkeypatch.setattr(browsing, "catalog_nearby", lambda *args, **kwargs: [])
    response = client.post("/route-alternatives", json={"points": [[40, -105]]})
    assert response.status_code == 200
    assert response.json()["places"] == []

    def unavailable(*args, **kwargs):
        raise RuntimeError("secret database connection details")

    monkeypatch.setattr(browsing, "catalog_nearby", unavailable)
    response = client.post("/route-alternatives", json={"points": [[40, -105]]})
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "Nearby places could not be loaded. Your route is unchanged."
    )
    assert "secret" not in response.text
