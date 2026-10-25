"""Research counts, capability isolation, durable scheduling and honest measures."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.research import store, worker
from app.research.design import Design, plan
from app.research.metrics import observation
from app.routers import studio_research as api
from app.routing.cp_sat_selection import SelectionConfig


@pytest.fixture(autouse=True)
def local_store(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_RESEARCH_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_RESEARCH_ENABLED", "true")
    monkeypatch.setenv("ROADTRIPS_REVISION", "fixture-revision")
    monkeypatch.setattr(api, "identity", lambda: {"source_snapshot_hash": "frozen"})
    monkeypatch.setattr(worker, "identity", lambda: {"source_snapshot_hash": "frozen"})
    monkeypatch.setattr(api, "_workers", {})


def minimal(**overrides):
    return Design(
        trips=["short-1d"],
        personas=["nature"],
        stops_per_day=[1],
        solver_repeats=1,
        quality_loss=[0.1],
        detour_weight=[1.0],
        **overrides,
    )


def make_study(design=None):
    key = str(uuid4())
    access = store.create(key, "studio:unit-owner", plan(design or minimal()), api.identity())
    return key, access


def test_matrix_and_one_factor_conditions_are_exact_and_paired():
    planned = plan(Design())
    assert planned["counts"] == {"combinations": 24, "captures": 24, "solver": 5040, "total": 5064}
    assert planned["dataset"]["kind"] == "real_capture_per_scenario"
    assert planned["dataset"]["candidate_limit"] is None
    assert planned == plan(Design())
    base = planned["variants"][0]["config"]
    assert base["time_limit_seconds"] == SelectionConfig().time_limit_seconds == 15
    for variant in planned["variants"][1:]:
        assert [key for key in base if base[key] != variant["config"][key]] == [
            variant["parameter"]
        ]
    for case in planned["cases"]:
        assert case["inputs"]["num_stops"] == case["target_days"] * case["stops_per_day"]
        assert "hotel_rooms" not in case["inputs"]
    assert all("budget" not in row["inputs"] for row in planned["cases"])
    assert set(planned["design"]["quality_loss"]) == {0, 0.05, 0.1, 0.2}
    assert set(planned["design"]["detour_weight"]) == {0, 0.25, 1, 4}


@pytest.mark.parametrize(
    "change",
    [
        {"repeats": 11},
        {"repeats": True},
        {"stops_per_day": [True]},
        {"quality_loss": [float("nan")]},
        {"quality_loss": [True]},
        {"detour_weight": [17]},
        {"trips": []},
        {"personas": ["nature", "nature"]},
        {"pipeline": False, "solver": False},
    ],
)
def test_invalid_designs_cannot_schedule_calls(change):
    with pytest.raises(ValidationError):
        Design(**change)


def test_api_requires_authorization_and_keeps_keys_out_of_results(monkeypatch):
    client = TestClient(app)
    payload = {"id": str(uuid4()), "design": minimal().model_dump(mode="json")}
    assert client.post("/studio/research/batches", json=payload).status_code == 401
    token = client.post("/studio/access", json={"password": "cp-sat"}).json()["token"]
    headers = {"X-Studio-Session": token}
    first = client.post("/studio/research/batches", headers=headers, json=payload)
    assert first.status_code == 201
    assert first.headers["cache-control"] == "no-store"
    assert (
        client.post("/studio/research/batches", headers=headers, json=payload).json()
        == first.json()
    )
    key = first.json()["key"]
    url = f"/studio/research/batches/{payload['id']}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers={"X-Studio-Batch-Key": "wrong"}).status_code == 404
    access = {"X-Studio-Batch-Key": key}
    data = client.get(url, headers=access).json()
    assert data["rows"] == [] and data["progress"] == {"pending": 2}
    assert key not in str(data) and "owner" not in data
    calls = []
    monkeypatch.setattr(
        api.subprocess,
        "Popen",
        lambda *a, **k: calls.append((a, k)) or SimpleNamespace(pid=None, poll=lambda: None),
    )
    assert client.post(f"{url}/start", headers=access).status_code == 200
    assert client.post(f"{url}/start", headers=access).status_code == 409
    assert len(calls) == 1
    assert calls[0][1]["start_new_session"] is True
    assert client.post(f"{url}/pause", headers=access).json()["state"] == "pausing"
    assert store.activate(payload["id"]) is False
    assert client.get(url, headers=access).json()["state"] == "paused"
    assert (
        client.get(f"{url}/export?format=json", headers=access).json()["protocol"]["counts"][
            "total"
        ]
        == 2
    )
    assert client.get(f"{url}/export?format=csv", headers=access).text.startswith("id,state,trip,")
    assert client.get(f"{url}/export?format=bad", headers=access).status_code == 422
    evidence = {"capture": {"hash": "test-only"}, "capture_evidence": {"error": None}}
    store.save(payload["id"], 0, "finished", evidence)
    chart = client.get(url, headers=access).json()["rows"][0]
    assert "capture" not in chart and "capture_evidence" not in chart
    exported = client.get(f"{url}/export?format=json", headers=access).json()
    assert exported["protocol"]["cases"][0]["capture"] == evidence["capture"]


def test_immutable_owner_plan_and_global_study_limit():
    key, access = make_study()
    with pytest.raises(HTTPException) as error:
        store.create(key, "different-owner", plan(minimal()), api.identity())
    assert error.value.status_code == 404
    changed = plan(minimal())
    changed["design"]["solver_repeats"] = 2
    with pytest.raises(HTTPException):
        store.create(key, "studio:unit-owner", changed, api.identity())
    store.claim(key)
    second, _ = make_study()
    with pytest.raises(HTTPException):
        store.claim(second)
    store.state(key, "complete")
    assert api.pause(store.study(key, access)) == {"state": "complete"}
    store.claim(second)
    assert store.study(second, trusted=True)["state"] == "starting"


def test_observations_do_not_invent_budget_or_utility_for_failed_or_partial_runs():
    envelope = {
        "explanation": {
            "solver": {"status": "FEASIBLE", "selected_count": 2, "requested_stops": 2},
            "candidates": [{"selected": True, "utility": 0.4}, {"selected": True, "utility": 0.8}],
        }
    }
    result = observation(envelope, 1000)
    assert result["utility_mean"] == pytest.approx(0.6)
    assert result["utility_min"] == 0.4 and result["utility_max"] == 0.8
    assert result["utility_median"] == pytest.approx(0.6)
    assert "extra_meters" not in result and "budget_utilization" not in result
    envelope["error"] = {"code": "selection"}
    assert observation(envelope, 1000)["utility_mean"] is None
    envelope.pop("error")
    envelope["explanation"]["solver"]["requested_stops"] = 4
    partial = observation(envelope, 1000)
    assert partial["completed"] and partial["fulfillment"] == 0.5
    assert partial["utility_mean"] == pytest.approx(0.6)


async def test_worker_survives_without_browser_and_resume_never_repeats_finished_work(monkeypatch):
    key, _ = make_study(
        Design(trips=["short-1d"], personas=["nature"], stops_per_day=[1, 2, 3], solver_repeats=1)
    )
    called = []

    async def fake(case, study):
        called.append(case["id"])
        if len(called) == 1:
            store.state(key, "pausing")
        await asyncio.sleep(0.01)
        return {"outcome": "completed", "completed": True}

    monkeypatch.setattr(worker, "capture_trial", fake)
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "paused"
    assert len(called) < 3
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "complete"
    assert len(called) == len(set(called)) == 3


async def test_repeated_storage_failure_pauses_unstarted_paid_runs(monkeypatch):
    key, _ = make_study(Design(solver_repeats=1))

    async def failure(*args):
        await asyncio.sleep(0.01)
        raise HTTPException(503, "Storage unavailable")

    monkeypatch.setattr(worker, "capture_trial", failure)
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "paused"
    results = store.rows(key)
    assert 3 <= sum(row["state"] == "finished" for row in results) <= 4
    assert any(row["state"] == "pending" for row in results)


async def test_interrupted_capture_is_not_repeated_and_saved_capture_is_reused(monkeypatch):
    key, _ = make_study()
    study = store.study(key, trusted=True)
    case = next(row for row in store.rows(key) if row["track"] == "capture")
    collected = AsyncMock(return_value={"runtime_seconds": 0, "error": {"code": "unit-test"}})
    monkeypatch.setattr(worker.preparation, "inputs", collected)
    first = await worker.capture_trial(case, study)
    assert await worker.capture_trial(case, study) == first
    collected.assert_awaited_once()
    # A started attempt without its final result cannot silently repeat provider work.
    next((store.directory() / key).glob("*.json")).unlink()
    result = await worker.capture_trial(case, study)
    assert result["outcome"] == "interrupted"
    collected.assert_awaited_once()


def test_source_change_refuses_mixing_and_solver_requires_real_capture(monkeypatch):
    key, access = make_study()
    study = store.study(key, access)
    monkeypatch.setattr(api, "identity", lambda: {"source_snapshot_hash": "changed"})
    with pytest.raises(HTTPException, match="") as error:
        api.start(study)
    assert error.value.status_code == 409
    planned = deepcopy(study["plan"])
    planned["variants"][0]["config"]["time_limit_seconds"] = 0.05
    case = next(row for row in store.rows(key) if row["track"] == "solver")
    result = worker.solver_trial(case, planned)
    assert result["outcome"] == "blocked"
    assert result["solver_status"] == "NOT_RUN"


def test_incremental_results_never_lose_late_lower_numbered_cases():
    key, _ = make_study()
    store.save(key, 1, "finished", {"outcome": "failed"})
    first, counts, cursor = store.changes(key)
    assert [row["id"] for row in first] == [1]
    assert counts == {"finished": 1, "pending": 1}
    assert store.changes(key, cursor)[0] == []
    store.save(key, 0, "finished", {"outcome": "completed"})
    second, _, later = store.changes(key, cursor)
    assert [row["id"] for row in second] == [0]
    assert later > cursor
    assert len(store.changes(key)[0]) == 2


async def test_real_capture_precedes_solver_trials_without_competing_for_timing(monkeypatch):
    key, _ = make_study()
    order = []
    monkeypatch.setattr(
        worker, "solver_trial", lambda *args: order.append("solver") or {"completed": True}
    )

    async def live(*args):
        order.append("live")
        return {"completed": True}

    monkeypatch.setattr(worker, "capture_trial", live)
    store.claim(key)
    await worker.execute(key)
    assert order == ["live", "solver"]


def test_execution_requires_opt_in_but_existing_results_and_pause_remain_available(monkeypatch):
    key, access = make_study()
    study = store.study(key, access)
    monkeypatch.setenv("STUDIO_RESEARCH_ENABLED", "false")
    with pytest.raises(HTTPException) as error:
        api.start(study)
    assert error.value.status_code == 503
    client = TestClient(app)
    headers = {"X-Studio-Batch-Key": access}
    assert client.get(f"/studio/research/batches/{key}", headers=headers).status_code == 200
    assert client.get("/studio/research/catalog").json()["execution_enabled"] is False
    assert client.post(f"/studio/research/batches/{key}/pause", headers=headers).status_code == 200


def test_existing_study_keeps_its_frozen_five_second_protocol():
    study_id = str(uuid4())
    historical = plan(minimal())
    for variant in historical["variants"]:
        variant["config"]["time_limit_seconds"] = 5.0
    access = store.create(study_id, "studio:unit-owner", historical, api.identity())
    current = plan(minimal())
    assert current["variants"][0]["config"]["time_limit_seconds"] == 15.0
    assert store.create(study_id, "studio:unit-owner", current, api.identity()) == access
    saved = store.study(study_id, access)
    assert saved["plan"]["variants"][0]["config"]["time_limit_seconds"] == 5.0


def test_new_study_captures_fresh_real_inputs_with_current_limit():
    historical = plan(minimal())
    for variant in historical["variants"]:
        variant["config"]["time_limit_seconds"] = 5.0
    previous_id = str(uuid4())
    previous_key = store.create(previous_id, "studio:unit-owner", historical, api.identity())
    store.state(previous_id, "paused")
    client = TestClient(app)
    url = f"/studio/research/batches/{previous_id}/rerun"
    payload = {"id": str(uuid4())}
    assert client.post(url, json=payload).status_code == 404
    access = {"X-Studio-Batch-Key": previous_key}
    assert client.post(url, json={"id": previous_id}, headers=access).status_code == 422
    unrelated_id, _ = make_study()
    assert client.post(url, json={"id": unrelated_id}, headers=access).status_code == 409
    response = client.post(url, json=payload, headers=access)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    replacement = response.json()
    assert client.post(url, json=payload, headers=access).json() == replacement
    fresh = store.study(replacement["id"], replacement["key"])
    assert fresh["plan"]["supersedes"] == previous_id
    assert fresh["plan"]["dataset_hash"] == historical["dataset_hash"]
    assert fresh["plan"]["counts"]["captures"] == 1
    assert fresh["plan"]["counts"]["solver"] == 1
    assert fresh["plan"]["variants"][0]["config"]["time_limit_seconds"] == 15
    assert {row["track"] for row in store.rows(fresh["id"])} == {"solver", "capture"}
    previous = store.study(previous_id, previous_key)
    assert previous["state"] == "paused"
    assert previous["plan"]["variants"][0]["config"]["time_limit_seconds"] == 5
    assert previous["plan"]["counts"]["captures"] == 1


def test_rerun_waits_for_active_work_and_requires_execution_opt_in(monkeypatch):
    previous_id, key = make_study()
    client = TestClient(app)
    url = f"/studio/research/batches/{previous_id}/rerun"
    access = {"X-Studio-Batch-Key": key}
    payload = {"id": str(uuid4())}
    store.state(previous_id, "pausing")
    assert client.post(url, json=payload, headers=access).status_code == 409
    store.state(previous_id, "paused")
    monkeypatch.setenv("STUDIO_RESEARCH_ENABLED", "false")
    assert client.post(url, json=payload, headers=access).status_code == 503
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 1
