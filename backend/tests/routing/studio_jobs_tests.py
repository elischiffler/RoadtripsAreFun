"""Disconnected/repeated browser requests must never duplicate provider work."""

import asyncio
import threading
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agent.progress import emit
from app.crud import lab_runs
from app.routing.studio_jobs import StudioJobs, saved_snapshot


@pytest.fixture
async def manager(monkeypatch):
    monkeypatch.setattr(lab_runs, "record", lambda *args: None)
    value = StudioJobs()
    yield value
    await value.shutdown()


async def wait_for(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_same_job_reconnects_and_finishes_once_without_any_subscriber(manager):
    release, started = threading.Event(), threading.Event()
    calls = []

    async def execute():
        calls.append(1)
        emit("route.model", candidates=4)
        started.set()
        await asyncio.to_thread(release.wait, 3)
        return {"route": {"stops": []}, "run_record": {"saved": True}}

    key = uuid4()
    try:
        assert (await manager.start("one", key, {"inputs": 1}, execute))["state"] == "running"
        await wait_for(started.is_set)
        assert (await manager.start("one", key, {"inputs": 1}, execute))["state"] == "running"
        # No open browser stream is needed. A later GET sees real progress and the same result.
        await wait_for(lambda: bool(manager.jobs[str(key)].progress.get("route.model")))
        assert any(
            event.get("candidates") == 4 for event in (await manager.get("one", key))["progress"]
        )
        release.set()
        await wait_for(lambda: manager.jobs[str(key)].terminal is not None)
        assert (await manager.get("one", key))["result"]["run_record"]["saved"]
        assert (await manager.start("one", key, {"inputs": 1}, execute))["state"] == "complete"
        assert calls == [1]
    finally:
        release.set()


async def test_job_owner_and_immutable_input_boundaries(manager):
    async def execute():
        await asyncio.sleep(1)
        return {}

    key = uuid4()
    await manager.start("one", key, {"inputs": 1}, execute)
    for operation in (
        manager.get("two", key),
        manager.cancel("two", key),
        manager.start("two", key, {"inputs": 1}, execute),
    ):
        with pytest.raises(HTTPException) as error:
            await operation
        assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        await manager.start("one", key, {"inputs": 2}, execute)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        await manager.start("one", uuid4(), {"inputs": 1}, execute)
    assert error.value.status_code == 409


async def test_cancel_before_start_blocks_a_late_post(manager):
    calls = []

    async def execute():
        calls.append(1)
        return {}

    key = uuid4()
    assert (await manager.cancel("one", key))["state"] == "cancelled"
    assert (await manager.start("one", key, {}, execute))["state"] == "cancelled"
    assert not calls


async def test_explicit_cancel_stops_work_and_does_not_report_completion(manager):
    started, stopped = threading.Event(), threading.Event()

    async def execute():
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()
        return {}

    key = uuid4()
    await manager.start("one", key, {}, execute)
    await wait_for(started.is_set)
    assert (await manager.cancel("one", key))["state"] == "cancelled"
    await wait_for(stopped.is_set)
    assert (await manager.get("one", key))["state"] == "cancelled"


async def test_completed_database_record_recovers_after_worker_memory_is_lost(manager, monkeypatch):
    key = uuid4()
    row = {
        "id": key,
        "status": "completed",
        "mode": "live",
        "input": {"num_stops": 2},
        "metrics": {"latency_ms": {"total": 7}},
        "result": {"route": {"stops": []}, "stages": None, "explanation": None},
    }
    owners = []
    monkeypatch.setattr(lab_runs, "record", lambda owner, run: owners.append((owner, run)) or row)
    data = await manager.get("one", key)
    assert data["result"]["snapshot"]["id"] == str(key)
    assert data["result"]["run_record"]["metrics"] == row["metrics"]
    assert data["result"]["stages"] == []
    assert owners == [("one", str(key))]

    async def forbidden():
        pytest.fail("A completed or interrupted record must not be rerun")

    assert (await manager.start("one", key, {}, forbidden))["state"] == "complete"
    row["status"] = "running"
    assert (await manager.start("one", key, {}, forbidden))["state"] == "interrupted"


def test_old_saved_replay_is_not_relabeled_as_live():
    result = saved_snapshot(
        {
            "id": uuid4(),
            "status": "completed",
            "mode": "replay",
            "input": {},
            "metrics": None,
            "result": {},
        }
    )["result"]
    assert result["mode"] == "replay"
    assert result["run_record"]["saved"]


async def test_provider_worker_failure_is_sanitized(manager):
    async def execute():
        raise RuntimeError("private provider credential")

    key = uuid4()
    await manager.start("one", key, {}, execute)
    await wait_for(lambda: manager.jobs[str(key)].terminal is not None)
    assert await manager.get("one", key) == {"state": "failed", "status": 503}


async def test_recorded_run_cancellation_during_insert_marks_the_eventual_row(monkeypatch):
    from fastapi import Response

    from app.routers import algorithm_lab as lab
    from app.routing.lab_presets import preset_catalog

    entered, release = threading.Event(), threading.Event()
    cancelled = []
    identifier = str(uuid4())

    def begin(owner, payload, run_id):
        assert run_id == identifier
        entered.set()
        release.wait(3)
        return run_id

    monkeypatch.setattr(lab_runs, "begin", begin)
    monkeypatch.setattr(lab_runs, "cancel", lambda *args: cancelled.append(args))
    item = preset_catalog()[0]
    payload = lab.LabRun(preset_id=item["id"], inputs=item["inputs"])
    task = asyncio.create_task(lab.recorded_run(payload, Response(), "one", job_id=identifier))
    try:
        await wait_for(entered.is_set)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled == [("one", identifier)]
    finally:
        release.set()


async def test_job_http_routes_authenticate_and_scope_all_operations(monkeypatch, manager):
    import httpx

    from app.main import app
    from app.routers import studio
    from app.routing.lab_presets import preset_catalog

    monkeypatch.setattr(studio, "jobs", manager)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        key = str(uuid4())
        item = preset_catalog()[0]
        body = {"id": key, "run": {"preset_id": item["id"], "inputs": item["inputs"]}}
        assert (await client.post("/studio/jobs", json=body)).status_code == 401
        assert (await client.get(f"/studio/jobs/{key}")).status_code == 401
        assert (await client.delete(f"/studio/jobs/{key}")).status_code == 401
        one = (await client.post("/studio/access", json={"password": "cp-sat"})).json()["token"]
        two = (await client.post("/studio/access", json={"password": "cp-sat"})).json()["token"]
        headers = {"X-Studio-Session": one}
        cancelled = await client.delete(f"/studio/jobs/{key}", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.headers["cache-control"] == "no-store"
        assert (await client.post("/studio/jobs", json=body, headers=headers)).json()[
            "state"
        ] == "cancelled"
        for method in (client.get, client.delete):
            assert (
                await method(f"/studio/jobs/{key}", headers={"X-Studio-Session": two})
            ).status_code == 404
        assert (
            await client.post("/studio/jobs", json=body, headers={"X-Studio-Session": two})
        ).status_code == 404
