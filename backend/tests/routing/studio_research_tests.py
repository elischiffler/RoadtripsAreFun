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
        repeats=1,
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
    assert planned["counts"] == {"combinations": 30, "pipeline": 300, "solver": 6300, "total": 6600}
    assert len(planned["dataset"]) == len({row["provider_id"] for row in planned["dataset"]}) == 100
    assert planned == plan(Design())
    base = planned["variants"][0]["config"]
    for variant in planned["variants"][1:]:
        assert [key for key in base if base[key] != variant["config"][key]] == [
            variant["parameter"]
        ]
    for case in planned["cases"]:
        assert case["inputs"]["num_stops"] == case["target_days"] * case["stops_per_day"]
        assert case["inputs"]["traveler_count"] == 2
        assert case["inputs"]["evening_interests"] == []
    medium = next(row for row in planned["cases"] if row["trip"] == "medium-2d")
    tight = next(
        row
        for row in planned["cases"]
        if row["trip"] == "tight-2d"
        and row["persona"] == medium["persona"]
        and row["stops_per_day"] == medium["stops_per_day"]
    )
    assert {k: v for k, v in medium["inputs"].items() if k != "budget"} == {
        k: v for k, v in tight["inputs"].items() if k != "budget"
    }


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


def test_immutable_owner_plan_and_global_study_limit():
    key, access = make_study()
    with pytest.raises(HTTPException) as error:
        store.create(key, "different-owner", plan(minimal()), api.identity())
    assert error.value.status_code == 404
    changed = plan(minimal())
    changed["design"]["repeats"] = 2
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
    result = observation(envelope, 1000, solver_only=True)
    assert result["utility_mean"] == pytest.approx(0.6)
    assert result["utility_min"] == 0.4 and result["utility_max"] == 0.8
    assert result["utility_median"] == pytest.approx(0.6)
    assert result["extra_meters"] is None and result["budget_utilization"] is None
    envelope["error"] = {"code": "selection"}
    assert observation(envelope, 1000, solver_only=True)["utility_mean"] is None
    envelope = {
        "explanation": {},
        "run_record": {
            "metrics": {
                "trip_evaluation": {
                    "completed": True,
                    "stop_fulfillment": {"ratio": 0.5},
                    "utility": {"delivered": {"mean": 0.9}},
                    "schedule_compliance": {"violation_count": 0},
                    "hotel_costs": {
                        "quotes_complete": True,
                        "room_night_count": 0,
                        "above_target_total_usd": 0,
                    },
                }
            }
        },
    }
    result = observation(envelope, 1000)
    assert not result["completed"] and result["utility_mean"] is None
    assert result["budget_excess_usd"] is None


def test_live_utility_pool_uses_only_selected_delivered_and_assessed_candidates():
    envelope = {
        "explanation": {
            "candidates": [
                {"provider_id": "x", "selected": True, "utility": 0.4},
                {"provider_id": "x", "selected": False, "utility": 0.9},
            ]
        },
        "route": {"stops": [{"type": "stop", "provider_id": "x"}]},
        "run_record": {
            "metrics": {
                "trip_evaluation": {
                    "completed": True,
                    "stop_fulfillment": {"ratio": 1},
                    "schedule_compliance": {"violation_count": 0},
                    "utility": {"delivered": {"count": 1, "mean": 0.4}},
                }
            }
        },
    }
    assert observation(envelope, 1000)["utility_values"] == [0.4]
    envelope["run_record"]["metrics"]["trip_evaluation"]["utility"] = {}
    assert observation(envelope, 1000)["utility_values"] is None


async def test_worker_survives_without_browser_and_resume_never_repeats_finished_work(monkeypatch):
    key, _ = make_study(
        Design(trips=["short-1d"], personas=["nature"], stops_per_day=[1], repeats=3, solver=False)
    )
    called = []

    async def fake(case, study):
        called.append(case["id"])
        if len(called) == 1:
            store.state(key, "pausing")
        await asyncio.sleep(0.01)
        return {"outcome": "completed", "completed": True}

    monkeypatch.setattr(worker, "live_trial", fake)
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "paused"
    assert len(called) < 3
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "complete"
    assert len(called) == len(set(called)) == 3


async def test_repeated_storage_failure_pauses_unstarted_paid_runs(monkeypatch):
    key, _ = make_study(
        Design(trips=["short-1d"], personas=["nature"], stops_per_day=[1], repeats=10, solver=False)
    )

    async def failure(*args):
        await asyncio.sleep(0.01)
        raise HTTPException(503, "Storage unavailable")

    monkeypatch.setattr(worker, "live_trial", failure)
    store.claim(key)
    await worker.execute(key)
    assert store.study(key, trusted=True)["state"] == "paused"
    results = store.rows(key)
    assert 3 <= sum(row["state"] == "finished" for row in results) <= 4
    assert any(row["state"] == "pending" for row in results)


async def test_interrupted_live_work_is_reconciled_without_repaying(monkeypatch):
    key, _ = make_study()
    study = store.study(key, trusted=True)
    case = next(row for row in store.rows(key) if row["track"] == "pipeline")
    recorded = AsyncMock()
    monkeypatch.setattr(worker.lab, "recorded_run", recorded)
    monkeypatch.setattr(worker.lab.lab_runs, "record", lambda *args: {"status": "running"})
    result = await worker.live_trial(case, study)
    assert result["outcome"] == "interrupted"
    recorded.assert_not_called()


def test_source_change_refuses_mixing_and_real_solver_uses_exactly_100(monkeypatch):
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
    assert result["evidence"] == "synthetic_controlled_100"
    assert result["candidate_count"] == 100
    assert result["solver"]["configuration"]["workers"] == 1
    assert result["dataset_hash"] == planned["dataset_hash"]


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


async def test_solver_trials_run_before_provider_work_without_competing_for_timing(monkeypatch):
    key, _ = make_study()
    order = []
    monkeypatch.setattr(
        worker, "solver_trial", lambda *args: order.append("solver") or {"completed": True}
    )

    async def live(*args):
        order.append("live")
        return {"completed": True}

    monkeypatch.setattr(worker, "live_trial", live)
    store.claim(key)
    await worker.execute(key)
    assert order == ["solver", "live"]


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
