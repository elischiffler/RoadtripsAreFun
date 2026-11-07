"""Account-only candidate orchestration with real timing and mocked provider leaves."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.candidate_errors import ERRORS, CandidateHTTPError
from app.models.planning_candidates import CandidateRequest
from app.models.routing_models.routing_models import MapBox
from app.routers import planning_candidates as api
from app.routers import routing_api
from app.routing.base import PlanningError, PlanOptions, PlanResult
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.planning_candidates import CandidateStore
from app.utils.auth import require_authenticated_user
from tests.one_day_rhythm_tests import policy, route
from tests.reserved_meal_tests import ZONE, endpoint, moment, visit
from tests.routing_api.guided_flow_tests import _payload


def payload(**changes):
    body = _payload()
    body.pop("budget")
    body.pop("hotel_rooms")
    body.update(request_id=str(uuid4()), start="2035-06-01T09:00:00-07:00")
    body["scheduling_policy"] = {"late_driving": True}
    return body | changes


@pytest.fixture
def runtime(monkeypatch):
    cache = CandidateStore()
    monkeypatch.setattr(api, "store", cache)
    monkeypatch.setattr(routing_api, "owner_routing_claims", lambda *_: None)
    monkeypatch.setattr(
        routing_api, "load_account_persona", lambda _: SimpleNamespace(weights=None)
    )
    monkeypatch.setattr(
        routing_api,
        "_build_services",
        lambda: SimpleNamespace(timezone_at=AsyncMock(return_value=ZONE)),
    )
    monkeypatch.setattr(
        routing_api, "get_location", lambda **kwargs: SimpleNamespace(address="Fixture address")
    )
    monkeypatch.setattr(routing_api, "refresh_for_timing", AsyncMock())
    monkeypatch.setattr(api, "refresh_for_timing", AsyncMock())
    monkeypatch.setattr(routing_api, "enrich_evenings", AsyncMock())
    state = SimpleNamespace(
        calls=0, discovery=0, mode_calls=[], actual_leg_seconds=3600, stop=visit(0, 3600)
    )
    state.stop["coordinates"] = [39.8, -104.95]
    state.stop["address"] = "Fixture stop"

    async def plan(initial, options, services):
        state.calls += 1
        state.mode_calls.append(options)
        if options._verified_cp_sat_candidates is None:
            state.discovery += 1
            options._verified_cp_sat_candidates = [{"provider_id": "fixture:visit"}]
        return PlanResult(stopping_points=[deepcopy(state.stop)], total_cost=0)

    monkeypatch.setattr(routing_api, "get_planner", lambda _: SimpleNamespace(plan=plan))

    async def road(*args):
        initial = MapBox.MapBox_Route.model_validate(_payload()["initial_route"])
        return initial.model_copy(
            update={
                "duration": 2 * state.actual_leg_seconds,
                "legs": [
                    SimpleNamespace(duration=state.actual_leg_seconds, distance=1000)
                    for _ in range(2)
                ],
            }
        )

    monkeypatch.setattr(routing_api, "_call_route", road)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture-account"
    client = TestClient(app)
    return client, cache, state, app


def check(client, body):
    registered = client.post(
        "/planning-candidates/requests", json={"request_id": body["request_id"]}
    )
    assert registered.status_code == 200
    return client.post("/planning-candidates", json=body)


def test_assessment_needs_no_rooms_or_hotel_service_and_confirms_without_planning_again(runtime):
    client, cache, state, _ = runtime
    response = check(client, payload())
    assert response.status_code == 200, response.text
    candidate = response.json()
    assert candidate["one_day"]["eligible"] is True
    assert candidate["one_day"]["elapsed_seconds"] >= 3 * 3600
    assert candidate["candidate_route"]["trip_mode"] == "one_day"
    assert candidate["candidate_route"]["one_day_proof"]["status"] == "validated"
    assert not any(s["type"] == "hotel" for s in candidate["candidate_route"]["stops"])
    value = {"input_key": candidate["input_key"], "trip_mode": "one_day", "traveler_count": 1}
    confirmed = client.post(
        "/planning-candidates/" + candidate["candidate_id"] + "/confirm", json=value
    )
    assert confirmed.status_code == 200, confirmed.text
    assert state.calls == state.discovery == 1
    repeat = client.post(
        "/planning-candidates/" + candidate["candidate_id"] + "/confirm", json=value
    )
    assert repeat.json() == confirmed.json()
    assert state.calls == 1
    assert cache.entries[candidate["candidate_id"]].payload.start.tzinfo is not None


def test_actual_candidate_not_early_road_estimate_controls_eligibility_and_threshold(runtime):
    client, _, state, _ = runtime
    # Baseline remains 1h; actual roads + visit + reserved meals exceed 12h.
    state.actual_leg_seconds = 5.5 * 3600
    result = check(client, payload(start="2035-06-01T06:00:00-07:00")).json()
    assert result["one_day"]["eligible"] is False
    assert result["one_day"]["elapsed_seconds"] > 43200
    assert result["one_day"]["reason_code"] == "elapsed_limit"
    assert result["candidate_route"] is not None
    value = {"input_key": result["input_key"], "trip_mode": "one_day"}
    refused = client.post("/planning-candidates/" + result["candidate_id"] + "/confirm", json=value)
    assert refused.status_code == 422 and refused.json()["code"] == "one_day_ineligible"
    assert state.calls == 1


def test_overnight_requires_occupancy_then_reuses_only_verified_pool(runtime):
    client, _, state, _ = runtime
    result = check(client, payload()).json()
    url = "/planning-candidates/" + result["candidate_id"] + "/confirm"
    assert (
        client.post(
            url, json={"input_key": result["input_key"], "trip_mode": "overnight"}
        ).status_code
        == 422
    )
    assert state.calls == 1
    value = {
        "input_key": result["input_key"],
        "trip_mode": "overnight",
        "budget": 120,
        "traveler_count": 1,
        "hotel_rooms": [{"adults": 1, "child_ages": []}],
    }
    confirmed = client.post(url, json=value)
    assert confirmed.status_code == 200, confirmed.text
    assert state.calls == 2 and state.discovery == 1
    assert state.mode_calls[-1].trip_mode == "overnight"
    assert state.mode_calls[-1].hotel_rooms[0].adults == 1


def test_valid_wrapped_overnight_rhythm_is_allowed_but_unavailable_departure_still_rejects(runtime):
    client, _, state, _ = runtime
    body = payload(
        start="2035-06-01T20:00:00-07:00",
        scheduling_policy={"daily_schedule": policy((20, 8), (9, 17)).daily_schedule.model_dump()},
    )
    result = check(client, body).json()
    assert result["one_day"]["eligible"] is True
    confirm = {
        "input_key": result["input_key"],
        "trip_mode": "overnight",
        "budget": 100,
        "traveler_count": 1,
        "hotel_rooms": [{"adults": 1, "child_ages": []}],
    }
    rejected = client.post(
        "/planning-candidates/" + result["candidate_id"] + "/confirm", json=confirm
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["trip_mode"] == "overnight"
    assert state.calls == 2
    body = payload(start="2035-06-01T12:00:00-07:00", scheduling_policy=body["scheduling_policy"])
    invalid = check(client, body)
    assert invalid.status_code == 422 and invalid.json()["code"] == "departure_outside_rhythm"
    assert state.calls == 2


def test_same_request_id_deduplicates_and_changed_inputs_cancel_expiry_and_restart_never_replan(
    runtime, monkeypatch
):
    client, cache, state, _ = runtime
    body = payload()
    first = check(client, body).json()
    repeated = client.post("/planning-candidates", json=body)
    assert repeated.json() == first and state.calls == 1
    changed = client.post("/planning-candidates", json=body | {"num_stops": 2})
    assert changed.status_code == 409 and changed.json()["code"] == "candidate_inputs_changed"
    assert state.calls == 1
    client.delete("/planning-candidates/requests/" + body["request_id"])
    assert client.post("/planning-candidates", json=body).status_code == 410
    assert (
        client.post(
            "/planning-candidates/" + first["candidate_id"] + "/confirm",
            json={"input_key": first["input_key"], "trip_mode": "one_day"},
        ).status_code
        == 410
    )
    assert state.calls == 1
    body = payload()
    check(client, body)
    cache.now = lambda: datetime.now(UTC) + timedelta(minutes=16)
    assert client.post("/planning-candidates", json=body).status_code == 410
    assert state.calls == 2
    monkeypatch.setattr(api, "store", CandidateStore())
    assert client.post("/planning-candidates", json=body).status_code == 410
    assert state.calls == 2


def test_cross_account_or_studio_visitor_cannot_use_candidate(runtime):
    client, _, state, app = runtime
    body = payload()
    result = check(client, body).json()
    app.dependency_overrides[require_authenticated_user] = lambda: "different-account"
    assert client.post("/planning-candidates", json=body).status_code == 410
    assert (
        client.post(
            "/planning-candidates/" + result["candidate_id"] + "/confirm",
            json={"input_key": result["input_key"], "trip_mode": "one_day"},
        ).status_code
        == 410
    )
    assert state.calls == 1
    app.dependency_overrides.clear()
    assert (
        client.post(
            "/planning-candidates/requests",
            json={"request_id": str(uuid4())},
            headers={"X-Studio-Session": "visitor"},
        ).status_code
        == 401
    )


def test_provider_failure_is_redacted_cached_and_never_falsely_eligible(runtime, monkeypatch):
    client, _, state, _ = runtime
    fail = AsyncMock(side_effect=PlanningError("PRIVATE PROVIDER DETAILS", 502))
    monkeypatch.setattr(routing_api, "plan_final_route", fail)
    body = payload()
    response = check(client, body)
    assert response.status_code == 503 and response.json()["code"] == "candidate_unavailable"
    assert "PRIVATE" not in response.text
    assert client.post("/planning-candidates", json=body).json() == response.json()
    assert fail.await_count == 1


@pytest.mark.asyncio
async def test_simultaneous_assessments_share_one_inflight_task_and_cancel_tombstones(
    runtime, monkeypatch
):
    _, cache, _, _ = runtime
    gate = asyncio.Event()
    entered = asyncio.Event()
    count = 0
    planned = route([endpoint(3600)], moment("09:00", "2035-06-01"))
    planned.stops[-1]["departure_time"] = "2035-06-01T10:00:00-07:00"

    async def fake(payload, **kwargs):
        nonlocal count
        count += 1
        kwargs["candidate_context"]["verified_candidates"] = []
        entered.set()
        await gate.wait()
        return planned

    monkeypatch.setattr(routing_api, "plan_final_route", fake)
    body = CandidateRequest.model_validate(payload())
    cache.register("owner", body.request_id)
    first = asyncio.create_task(api.assess(body, "owner"))
    await entered.wait()
    second = asyncio.create_task(api.assess(body, "owner"))
    await asyncio.sleep(0)
    gate.set()
    a, b = await asyncio.gather(first, second)
    assert a.candidate_id == b.candidate_id and count == 1
    body = CandidateRequest.model_validate(payload())
    cache.register("owner", body.request_id)
    gate.clear()
    entered.clear()
    running = asyncio.create_task(api.assess(body, "owner"))
    await entered.wait()
    cache.cancel_request("owner", body.request_id)
    with pytest.raises(asyncio.CancelledError):
        await running
    with pytest.raises(CandidateHTTPError) as caught:
        await api.assess(body, "owner")
    assert caught.value.code == "candidate_cancelled" and count == 2


def test_bounded_capacity_and_unregistered_assessment_have_no_provider_work(runtime):
    client, cache, state, _ = runtime
    cache.maximum = 1
    assert client.post("/planning-candidates", json=payload()).status_code == 410
    check(client, payload())
    assert (
        client.post("/planning-candidates/requests", json={"request_id": str(uuid4())}).status_code
        == 503
    )
    assert state.calls == 1


def test_stream_carries_actual_candidate_preview_and_fixed_error_contract(runtime, monkeypatch):
    client, _, _, _ = runtime
    body = payload()
    client.post("/planning-candidates/requests", json={"request_id": body["request_id"]})
    response = client.post("/planning-candidates/stream", json=body)
    events = [json.loads(line) for line in response.text.splitlines()]
    preview = next(e for e in events if e.get("stage") == "route.preview")
    assert preview["phase"] == "checking" and preview["preview_only"] is True
    assert preview["geometry"]["coordinates"] and events[-1]["response"]["one_day"]["eligible"]
    assert events[-1]["type"] == "result"
    body = payload()
    # Generic HTTP errors cannot impersonate the typed allowlist.
    failure = HTTPException(422, "PRIVATE PROVIDER DETAILS")
    failure.code = "one_day_ineligible"
    monkeypatch.setattr(routing_api, "plan_final_route", AsyncMock(side_effect=failure))
    client.post("/planning-candidates/requests", json={"request_id": body["request_id"]})
    response = client.post("/planning-candidates/stream", json=body)
    last = json.loads(response.text.splitlines()[-1])
    assert last["status"] == 503 and last["code"] == "candidate_unavailable"
    assert "PRIVATE" not in response.text


@pytest.mark.asyncio
async def test_real_cp_sat_planner_one_day_does_not_require_hotel_provider():
    from app.routing.services import RoutingServices

    no_calls = AsyncMock(side_effect=AssertionError("No provider calls for zero-stop fixture"))
    services = RoutingServices(
        find_stop=no_calls,
        find_hotel=no_calls,
        find_position=lambda *_: [],
        get_price_range=lambda *_: None,
        cp_sat_candidates=no_calls,
        cp_sat_hotels=None,
        timezone_at=AsyncMock(return_value=ZONE),
    )
    initial = MapBox.MapBox_Route.model_validate(_payload()["initial_route"])
    result = await CPSatPlanner().plan(
        initial,
        PlanOptions(num_stops=0, budget=0, start=moment("09:00"), trip_mode="one_day"),
        services,
    )
    assert result.stopping_points == [] and result.total_cost == 0
    no_calls.assert_not_awaited()


@pytest.mark.parametrize("status,code", [(500, "one_day_ineligible"), (422, "unknown_code")])
def test_mutated_typed_error_status_or_code_cannot_leak_provider_detail(
    runtime, monkeypatch, status, code
):
    client, _, _, _ = runtime
    error = CandidateHTTPError("one_day_ineligible")
    error.status_code = status
    error.code = code
    error.detail = "PRIVATE PROVIDER DETAILS"
    monkeypatch.setattr(routing_api, "plan_final_route", AsyncMock(side_effect=error))
    body = payload()
    client.post("/planning-candidates/requests", json={"request_id": body["request_id"]})
    response = client.post("/planning-candidates/stream", json=body)
    last = json.loads(response.text.splitlines()[-1])
    assert last["status"] == 503 and last["code"] == "candidate_unavailable"
    assert last["detail"] == ERRORS["candidate_unavailable"][1]
    assert "PRIVATE" not in response.text


def test_input_key_mismatch_or_cancelled_completed_request_never_confirms(runtime):
    client, _, state, _ = runtime
    body = payload()
    result = check(client, body).json()
    url = "/planning-candidates/" + result["candidate_id"] + "/confirm"
    assert client.post(url, json={"input_key": "f" * 64, "trip_mode": "one_day"}).status_code == 409
    assert client.delete("/planning-candidates/requests/" + body["request_id"]).status_code == 200
    assert (
        client.post(
            url, json={"input_key": result["input_key"], "trip_mode": "one_day"}
        ).status_code
        == 410
    )
    assert state.calls == 1


@pytest.mark.parametrize("date", ["2027-11-06", "2027-03-13"])
def test_ambiguous_or_missing_relevant_cutoff_rejects_with_fixed422_before_planner(runtime, date):
    client, _, state, _ = runtime
    cutoff = 1 if "11-" in date else 2
    selected = policy((20, cutoff), (3, 10)).daily_schedule.model_dump()
    body = payload(
        start=f"{date}T20:00:00" + ("-07:00" if "11-" in date else "-08:00"),
        scheduling_policy={"daily_schedule": selected},
    )
    response = check(client, body)
    assert response.status_code == 422, response.text
    assert response.json() == {
        "code": "rhythm_clock_conflict",
        "detail": ERRORS["rhythm_clock_conflict"][1],
    }
    assert state.calls == state.discovery == 0


def test_westbound_unavailable_leg_has_actionable_fixed422_and_no_candidate_claim(
    runtime, monkeypatch
):
    client, _, state, _ = runtime

    async def zones(coords):
        return "America/Denver" if list(coords) == [40.0, -105.0] else "America/Los_Angeles"

    monkeypatch.setattr(routing_api, "_build_services", lambda: SimpleNamespace(timezone_at=zones))
    body = payload(
        start="2035-06-01T09:00:00-06:00",
        scheduling_policy={"daily_schedule": policy().daily_schedule.model_dump()},
    )
    response = check(client, body)
    assert response.status_code == 422, response.text
    assert response.json() == {
        "code": "rhythm_availability_conflict",
        "detail": ERRORS["rhythm_availability_conflict"][1],
    }
    assert "candidate_id" not in response.json()
    assert state.calls == 1


def test_party_inputs_are_bound_to_candidate_even_when_hotel_choice_changes(runtime):
    client, _, state, _ = runtime
    result = check(client, payload()).json()
    response = client.post(
        "/planning-candidates/" + result["candidate_id"] + "/confirm",
        json={
            "input_key": result["input_key"],
            "trip_mode": "overnight",
            "budget": 100,
            "traveler_count": 2,
            "hotel_rooms": [{"adults": 2, "child_ages": []}],
        },
    )
    assert response.status_code == 409 and response.json()["code"] == "candidate_inputs_changed"
    assert state.calls == 1


def test_candidate_retains_tentative_road_areas_separate_from_checked_timing(runtime):
    client, _, _, _ = runtime
    body = payload()
    body["initial_route"]["duration"] = 20 * 3600
    result = check(client, body)
    assert result.status_code == 200
    response = result.json()
    assert 0 < len(response["possible_overnight_areas"]) <= 3
    assert all(
        area["tentative"]
        and not area["hotel_quotes_checked"]
        and not area["availability_checked"]
        and area["clock_basis"] == "departure_wall_clock_estimate"
        for area in response["possible_overnight_areas"]
    )
    # The actual road/timing fixture remains the authority, independently of hints.
    assert response["one_day"]["eligible"] is True
