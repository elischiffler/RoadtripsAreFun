"""Owner authorization, shared live routing, and reproducible solver experiments."""

import copy
import itertools
import math
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent.persona import ATTRIBUTE_KEYS, AccountPersona, normalize_weights
from app.main import app
from app.routers import algorithm_lab as lab
from app.routers import routing_api
from app.routing.base import PlanningError
from app.routing.explanation import capture_explanation
from app.routing.lab_presets import preset_catalog, replay_candidates
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.profiles import AttributeRatings, crossmatch
from app.routing.selection import OWNER_EMAIL


@pytest.fixture(autouse=True)
def lab_storage(monkeypatch):
    monkeypatch.setattr(lab.lab_runs, "begin", lambda *args: "00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(lab.lab_runs, "finish", lambda *args: None)


@pytest.fixture
def headers(signed_token):
    return {
        "Authorization": f"Bearer {signed_token()}",
        "X-Cognito-Id-Token": signed_token(
            token_use="id", aud="fixture-client", email=OWNER_EMAIL, email_verified=True
        ),
    }


def request_body(mode="live", preset=0):
    selected = preset_catalog()[preset]
    result = {"mode": mode, "preset_id": selected["id"], "inputs": selected["inputs"]}
    if mode == "replay":
        result["snapshot_id"] = "teaching-v1"
    return result


@pytest.mark.parametrize("path,method", [("/presets", "get"), ("/run", "post")])
def test_lab_requires_access_token(path, method):
    response = getattr(TestClient(app), method)(
        f"/algorithm-lab{path}", **({"json": request_body()} if method == "post" else {})
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [None, {"email": "other@example.com"}, {"email_verified": False}, {"sub": "different-subject"}],
)
def test_owner_evidence_fails_closed(signed_token, claims):
    auth = {"Authorization": f"Bearer {signed_token()}"}
    if claims is not None:
        auth["X-Cognito-Id-Token"] = signed_token(
            **{
                "token_use": "id",
                "aud": "fixture-client",
                "email": OWNER_EMAIL,
                "email_verified": True,
                **claims,
            }
        )
    client = TestClient(app)
    assert client.get("/algorithm-lab/presets", headers=auth).status_code == 403
    assert client.post("/algorithm-lab/run", headers=auth, json=request_body()).status_code == 403


def test_catalog_only_exposes_live_trip_inputs(headers):
    catalog = TestClient(app).get("/algorithm-lab/presets", headers=headers)
    assert catalog.status_code == 200
    assert catalog.headers["cache-control"] == "no-store"
    assert catalog.json()["attributes"] == list(ATTRIBUTE_KEYS)
    assert "snapshots" not in catalog.json()


@pytest.mark.parametrize(
    "patch",
    [
        {"num_stops": 11},
        {"num_stops": 0},
        {"budget": -1},
        {"budget": "NaN"},
        {"traveler_count": 3},
        {"persona_weights": {"food": 1}},
        {"car_status": "provided"},
        {"start_id": "client invented"},
        {"coordinates": [1, 2]},
        {"departure_time": "26:00"},
    ],
)
def test_invalid_direct_inputs_rejected(headers, patch):
    body = request_body()
    body["inputs"].update(patch)
    response = TestClient(app).post("/algorithm-lab/run", headers=headers, json=body)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"preset_id": "unknown"},
        {"snapshot_id": None},
        {"snapshot_id": "teaching-v1"},
        {"mode": "replay"},
    ],
)
def test_invalid_mode_or_preset_rejected(headers, monkeypatch, patch):
    def forbidden(*args):
        raise AssertionError("Rejected requests must not start experiments")

    monkeypatch.setattr(lab.lab_runs, "begin", forbidden)
    body = request_body()
    body.update(patch)
    assert TestClient(app).post("/algorithm-lab/run", headers=headers, json=body).status_code == 422


def test_live_date_must_be_upcoming_before_provider_calls(headers, monkeypatch):
    async def forbidden(*args):
        raise AssertionError("Date rejection should precede providers")

    monkeypatch.setattr(lab, "resolve_endpoint", forbidden)
    body = request_body("live")
    body["inputs"]["departure_date"] = "2020-01-01"
    assert TestClient(app).post("/algorithm-lab/run", headers=headers, json=body).status_code == 422


@pytest.mark.parametrize("preset", [0, 1])
def test_solver_objective_matches_exhaustive_subsets(preset):
    weights = preset_catalog()[preset]["inputs"]["persona_weights"]
    candidates, points = replay_candidates("teaching-v1", weights)
    with capture_explanation() as result:
        CPSatPlanner._select(candidates, points, 2)
    eligible = [item for item in result["candidates"] if item["objective_coefficient"] is not None]
    feasible_totals = []
    for count in range(3):
        for subset in itertools.combinations(eligible, count):
            if len({item["slot"] for item in subset}) == count:
                feasible_totals.append(sum(item["objective_coefficient"] for item in subset))
    assert result["solver"]["objective_value"] == max(feasible_totals)


def test_score_preserves_existing_effective_weight_arithmetic():
    weights = normalize_weights({key: (index + 1) / 17 for index, key in enumerate(ATTRIBUTE_KEYS)})
    ratings = {key: 0.6000005 for key in ATTRIBUTE_KEYS}
    match = crossmatch(weights, ratings, already_normalized=True)
    assert match.utility == math.fsum(weights[key] * ratings[key] for key in ATTRIBUTE_KEYS)
    assert set(AttributeRatings.model_fields) == set(ATTRIBUTE_KEYS)


def test_explanations_distinguish_duplicates_threshold_and_cap():
    weights = preset_catalog()[0]["inputs"]["persona_weights"]
    candidates, points = replay_candidates("teaching-v1", weights)
    candidates += [copy.deepcopy(candidates[0]), {"provider_id": "broken"}]
    with capture_explanation() as result:
        CPSatPlanner._select(candidates, points, 1)
    reasons = {item["reason"] for item in result["candidates"]}
    assert {
        "selected",
        "eligible_not_selected",
        "below_utility_threshold",
        "duplicate_provider_id",
        "invalid_candidate",
    } <= reasons
    assert result["solver"]["selected_count"] == 1


@pytest.mark.parametrize("detour_invalid", [False, True])
def test_live_reuses_normal_pipeline_and_builds_itinerary(
    headers, monkeypatch, route, detour_invalid
):
    # Exercise the real plan_final_route orchestration, with deterministic provider
    # services and a no-attraction route. No provider or database is contacted.
    route.duration = route.legs[0].duration = route.legs[0].steps[0].duration = 3600
    monkeypatch.setattr(routing_api, "load_account_persona", lambda user: AccountPersona.default())
    monkeypatch.setattr(
        routing_api,
        "get_location",
        lambda **kwargs: SimpleNamespace(
            address="Fixture resolved address",
            raw={"annotations": {"timezone": {"name": "America/Los_Angeles"}}},
        ),
    )

    async def endpoint(key):
        return {
            "label": key,
            "coordinates": [
                route.geometry.coordinates[0 if key == "sf" else -1][1],
                route.geometry.coordinates[0 if key == "sf" else -1][0],
            ],
            "timezone": "America/Los_Angeles",
            "source": "fixture",
        }

    async def driving(*args):
        return route

    async def final_driving(*args):
        final = route.model_copy(deep=True)
        if detour_invalid:
            final.duration = final.legs[0].duration = 24 * 3600
        return final

    async def candidates(*args):
        return []

    monkeypatch.setattr(lab, "resolve_endpoint", endpoint)
    monkeypatch.setattr(lab, "call_route", driving)
    monkeypatch.setattr(routing_api, "_call_route", final_driving)
    monkeypatch.setattr(routing_api, "attraction_candidates", candidates)
    response = TestClient(app).post(
        "/algorithm-lab/run", headers=headers, json=request_body("live")
    )
    assert response.status_code == 200
    result = response.json()
    if detour_invalid:
        assert result["error"]["code"] == "422"
        assert result["route"] is None
        assert result["explanation"]["solver"]["status"] == "NOT_RUN"
        stages = {stage["name"]: stage["status"] for stage in result["stages"]}
        assert stages["scheduling"] == "complete"
        assert stages["reroute"] == "failed"
        assert stages["itinerary"] == "not_run"
        return
    assert result["error"] is None
    assert result["route"]["stops"][-1]["type"] == "end"
    assert result["itinerary"]
    assert all(stage["status"] == "complete" for stage in result["stages"])
    assert result["explanation"]["solver"]["status"] == "NOT_RUN"


def test_live_failure_is_not_replaced_with_replay(headers, monkeypatch):
    async def unavailable(key):
        raise PlanningError("Endpoint provider unavailable", 503)

    monkeypatch.setattr(lab, "resolve_endpoint", unavailable)
    result = (
        TestClient(app)
        .post("/algorithm-lab/run", headers=headers, json=request_body("live"))
        .json()
    )
    assert result["mode"] == "live"
    assert result["error"]["code"] == "503"
    assert result["error"]["message"] == "Endpoint provider unavailable"
    assert result["error"]["stage"] == "endpoints"
    assert result["error"]["causes"][0]["type"] == "PlanningError"
    assert result["route"] is None
    assert (
        next(stage for stage in result["stages"] if stage["name"] == "endpoints")["status"]
        == "failed"
    )


def test_storage_failure_blocks_provider_work(headers, monkeypatch, caplog):
    def unavailable(*args):
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(lab.lab_runs, "begin", unavailable)
    monkeypatch.setattr(lab.logger, "handlers", [caplog.handler])
    response = TestClient(app).post("/algorithm-lab/run", headers=headers, json=request_body())
    assert response.status_code == 503
    assert "secret" not in response.text
    assert "No experiment was started" in response.text
    assert "operation=begin exception_class=RuntimeError" in caplog.text
    assert "secret connection string" not in caplog.text


def test_failed_finalize_reports_unsaved_result(headers, monkeypatch):
    async def endpoint_unavailable(key):
        raise PlanningError("Endpoint unavailable", 503)

    monkeypatch.setattr(lab, "resolve_endpoint", endpoint_unavailable)

    def unavailable(*args):
        raise RuntimeError("database offline")

    monkeypatch.setattr(lab.lab_runs, "finish", unavailable)
    result = TestClient(app).post("/algorithm-lab/run", headers=headers, json=request_body()).json()
    assert result["run_record"]["saved"] is False
    assert result["error"]["code"] == "503"


def test_history_is_owner_scoped_paginated_and_private(headers, monkeypatch):
    calls = []
    monkeypatch.setattr(lab.lab_runs, "history", lambda *args: calls.append(args) or [])
    client = TestClient(app)
    assert client.get("/algorithm-lab/runs").status_code == 401
    response = client.get("/algorithm-lab/runs?limit=50&offset=100", headers=headers)
    assert response.status_code == 200
    assert calls == [("cognito-user-123", 50, 100)]
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["groups"] == []
    assert client.get("/algorithm-lab/runs?limit=501", headers=headers).status_code == 422


def test_benchmark_presets_are_validated_and_repeat_count_bounded(headers):
    client = TestClient(app)
    catalog = client.get("/algorithm-lab/presets", headers=headers).json()
    assert len(catalog["benchmarks"]) == 6
    all_presets = {preset["id"]: preset["inputs"] for preset in catalog["presets"]}
    profiles = {preset["id"]: preset["inputs"] for preset in catalog["benchmarks"]}
    assert profiles["medium-two-day"]["hotel_rooms"][0]["child_ages"] == [7, 12]
    assert len(profiles["long-multi-day"]["hotel_rooms"]) == 2
    assert profiles["dense-corridor"]["scheduling_policy"]["late_driving"] is True
    assert profiles["tight-budget"]["budget"] == 60
    assert len({item["departure_time"] for item in profiles.values()}) == 6
    assert len({tuple(item["persona_weights"].values()) for item in profiles.values()}) == 6
    for preset in catalog["benchmarks"]:
        lab.LabInputs.model_validate(preset["inputs"])
        assert preset["inputs"] == all_presets[preset["id"]]
    payload = request_body()
    payload["repeat_index"] = 11
    assert client.post("/algorithm-lab/run", headers=headers, json=payload).status_code == 422


def test_history_completion_summary_excludes_unfinished_rows(headers, monkeypatch):
    monkeypatch.setattr(
        lab.lab_runs,
        "history",
        lambda *args: [
            {"status": "completed", "metrics": None},
            {"status": "failed", "metrics": None},
            {"status": "running", "metrics": None},
        ],
    )
    summary = TestClient(app).get("/algorithm-lab/runs", headers=headers).json()["page_summary"]
    assert summary == {
        "completed": 1,
        "failed": 1,
        "unfinished": 1,
        "completion_assessed": 2,
        "completion_rate": 0.5,
    }


@pytest.mark.parametrize("available", [True, False])
def test_saved_trip_results_are_owner_scoped(headers, monkeypatch, available):
    calls = []
    artifact = {"route": {"stops": []}, "itinerary": [{"date": "2026-10-06"}]}

    def fetch(owner, run_id):
        calls.append((owner, str(run_id)))
        return artifact if available else None

    monkeypatch.setattr(lab.lab_runs, "result", fetch)
    path = "/algorithm-lab/runs/00000000-0000-0000-0000-000000000001/result"
    client = TestClient(app)
    assert client.get(path).status_code == 401
    response = client.get(path, headers=headers)
    assert response.status_code == (200 if available else 404)
    assert calls == [("cognito-user-123", "00000000-0000-0000-0000-000000000001")]
    if available:
        assert response.json() == artifact
        assert response.headers["cache-control"] == "no-store"


def test_planning_failure_logs_code_locations_without_provider_secrets(headers, monkeypatch):
    logged = []
    monkeypatch.setattr(lab.logger, "error", lambda *args: logged.append(args))

    async def unavailable(key):
        raise RuntimeError("secret provider credentials")

    monkeypatch.setattr(lab, "resolve_endpoint", unavailable)
    result = (
        TestClient(app)
        .post("/algorithm-lab/run", headers=headers, json=request_body("live"))
        .json()
    )
    assert result["error"]["code"] == "provider_or_planning_failure"
    assert logged[0][1] == "RuntimeError"
    assert any(name == "unavailable" for name, line in logged[0][3])
    assert "secret provider credentials" not in str(logged)
    assert "secret provider credentials" not in str(result)
