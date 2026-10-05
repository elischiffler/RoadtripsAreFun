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


@pytest.fixture
def headers(signed_token):
    return {
        "Authorization": f"Bearer {signed_token()}",
        "X-Cognito-Id-Token": signed_token(
            token_use="id", aud="fixture-client", email=OWNER_EMAIL, email_verified=True
        ),
    }


def request_body(mode="replay", preset=0):
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


def test_replay_is_frozen_rescored_and_never_uses_live_dependencies(headers, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not call provider or database")

    for name in ("resolve_endpoint", "call_route", "plan_final_route", "build_itinerary"):
        monkeypatch.setattr(lab, name, forbidden)
    monkeypatch.setattr(routing_api, "load_account_persona", forbidden)
    client = TestClient(app)
    catalog = client.get("/algorithm-lab/presets", headers=headers)
    assert catalog.status_code == 200
    assert catalog.headers["cache-control"] == "no-store"
    assert catalog.json()["attributes"] == list(ATTRIBUTE_KEYS)
    outputs = [
        client.post("/algorithm-lab/run", headers=headers, json=request_body(preset=i)).json()
        for i in (0, 1)
    ]
    assert all(result["error"] is None for result in outputs)
    assert all(result["route"] is None and result["itinerary"] is None for result in outputs)
    first, second = [result["explanation"] for result in outputs]
    assert [c["attribute_ratings"] for c in first["candidates"]] == [
        c["attribute_ratings"] for c in second["candidates"]
    ]
    assert {c["provider_id"] for c in first["candidates"] if c["selected"]} != {
        c["provider_id"] for c in second["candidates"] if c["selected"]
    }
    assert first["solver"]["status"] == "OPTIMAL"
    assert first["solver"]["objective_value"] == first["solver"]["best_bound"]
    assert first["solver"]["selected_count"] == 2
    assert all(
        stage["status"] == "not_run"
        for stage in outputs[0]["stages"]
        if stage["name"] in {"scheduling", "reroute", "itinerary"}
    )
    for candidate in first["candidates"]:
        assert candidate["utility"] == pytest.approx(
            sum(item["contribution"] for item in candidate["contributions"])
        )
        assert "synthetic" in candidate["provenance"]["identity_source"]


def test_empty_fixture_does_not_claim_solver_ran(headers):
    body = request_body()
    body["snapshot_id"] = "empty-v1"
    result = TestClient(app).post("/algorithm-lab/run", headers=headers, json=body).json()
    assert result["explanation"]["solver"]["status"] == "NOT_RUN"
    assert result["explanation"]["solver"]["objective_value"] is None
    assert all(
        item["reason"] == "below_utility_threshold" for item in result["explanation"]["candidates"]
    )


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
    [{"preset_id": "unknown"}, {"snapshot_id": None}, {"snapshot_id": "unknown"}, {"mode": "live"}],
)
def test_invalid_mode_or_preset_rejected(headers, patch):
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
    assert result["error"] == {"code": "503", "message": "Endpoint provider unavailable"}
    assert result["route"] is None
    assert (
        next(stage for stage in result["stages"] if stage["name"] == "endpoints")["status"]
        == "failed"
    )
