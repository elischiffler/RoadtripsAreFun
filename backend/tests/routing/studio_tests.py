"""Visitor password sessions cannot cross history or Cognito boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import algorithm_lab as lab
from app.routers import studio
from app.routing.lab_presets import preset_catalog

client = TestClient(app)


def unlock(password="cp-sat"):
    response = client.post("/studio/access", json={"password": password})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return {"X-Studio-Session": response.json()["token"]}


@pytest.mark.parametrize("password", ["cp-sat", "CP-SAT", "Cp-SaT"])
def test_case_insensitive_visitor_access(password):
    response = client.get("/studio/presets", headers=unlock(password))
    assert response.status_code == 200
    assert len(response.json()["presets"]) == 9


@pytest.mark.parametrize("password", ["wrong", "cp_sat", "", "x" * 129])
def test_wrong_password_does_not_issue_session(password):
    response = client.post("/studio/access", json={"password": password})
    assert response.status_code in {401, 422}
    assert "token" not in response.json()
    if password:
        assert password not in str(response.json())


@pytest.mark.parametrize(
    "path,method",
    [
        ("presets", "get"),
        ("runs", "get"),
        (f"runs/{uuid4()}/result", "get"),
        ("run", "post"),
        ("run/stream", "post"),
    ],
)
def test_every_studio_endpoint_requires_session(path, method):
    item = preset_catalog()[0]
    kwargs = (
        {"json": {"preset_id": item["id"], "inputs": item["inputs"]}} if method == "post" else {}
    )
    assert getattr(client, method)(f"/studio/{path}", **kwargs).status_code == 401


@pytest.mark.parametrize("kind", ["expired", "tampered", "account-subject", "wrong-audience"])
def test_bad_sessions_fail_closed(kind):
    now = datetime.now(UTC)
    claims = {
        "sub": f"studio:{uuid4()}",
        "iss": studio.ISSUER,
        "aud": studio.ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    if kind == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif kind == "account-subject":
        claims["sub"] = "owner"
    elif kind == "wrong-audience":
        claims["aud"] = "chat"
    token = jwt.encode(
        claims, "another-secret" if kind == "tampered" else studio.SESSION_SECRET, algorithm="HS256"
    )
    assert client.get("/studio/presets", headers={"X-Studio-Session": token}).status_code == 401


def test_studio_token_cannot_authorize_owner_api():
    token = unlock()["X-Studio-Session"]
    assert (
        client.get(
            "/algorithm-lab/presets", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )


def test_history_and_results_are_scoped_to_individual_visitor(monkeypatch):
    owners = []
    monkeypatch.setattr(lab.lab_runs, "history", lambda owner, *args: owners.append(owner) or [])
    run_id = uuid4()
    monkeypatch.setattr(
        lab.lab_runs,
        "result",
        lambda owner, *args: {"route": {"owner": owner}} if owner == owners[0] else None,
    )
    first, second = unlock(), unlock()
    assert client.get("/studio/runs", headers=first).status_code == 200
    assert client.get("/studio/runs", headers=second).status_code == 200
    assert owners[0] != owners[1]
    assert all(owner.startswith("studio:") for owner in owners)
    assert client.get(f"/studio/runs/{run_id}/result", headers=first).status_code == 200
    assert client.get(f"/studio/runs/{run_id}/result", headers=second).status_code == 404


def test_visitor_run_uses_shared_live_planner_and_scoped_storage(monkeypatch):
    calls = []
    monkeypatch.setattr(
        lab.lab_runs, "begin", lambda owner, payload: calls.append((owner, payload)) or str(uuid4())
    )
    monkeypatch.setattr(lab.lab_runs, "finish", lambda owner, *args: calls.append(owner))

    async def execute(payload, owner, departure):
        calls.append(owner)
        return {
            "mode": "live",
            "route": None,
            "error": None,
            "explanation": {},
            "input_snapshot": payload.inputs.model_dump(mode="json"),
        }

    monkeypatch.setattr(lab, "execute_run", execute)
    item = preset_catalog()[0]
    response = client.post(
        "/studio/run",
        headers=unlock(),
        json={"mode": "live", "preset_id": item["id"], "inputs": item["inputs"]},
    )
    assert response.status_code == 200
    assert response.json()["run_record"]["saved"]
    assert calls[0][0] == calls[1] == calls[2]
    assert calls[0][1]["mode"] == "live"


def test_stream_validates_access_and_inputs_before_stream_headers():
    assert client.post("/studio/run/stream", json={}).status_code == 401
    response = client.post("/studio/run/stream", headers=unlock(), json={})
    assert response.status_code == 422
    assert "application/x-ndjson" not in response.headers["content-type"]


def test_stream_forwards_actual_progress_and_preserves_saved_envelope(monkeypatch):
    import json

    from app.agent.progress import emit

    async def run(payload, response, owner):
        emit("route.model", candidates=8, eligible=4, requestedStops=2)
        return {"route": {"stops": []}, "run_record": {"saved": True}, "owner": owner}

    monkeypatch.setattr(lab, "run", run)
    item = preset_catalog()[0]
    response = client.post(
        "/studio/run/stream",
        headers=unlock(),
        json={"preset_id": item["id"], "inputs": item["inputs"]},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["stage"] == "studio.run"
    assert events[1]["stage"] == "route.model"
    assert events[1]["eligible"] == 4
    assert events[-1]["type"] == "result"
    assert events[-1]["response"]["run_record"]["saved"]
    assert events[-1]["response"]["owner"].startswith("studio:")


def test_stream_scrubs_storage_failure(monkeypatch):
    from fastapi import HTTPException

    async def fail(*args):
        raise HTTPException(503, "private database credential")

    monkeypatch.setattr(lab, "run", fail)
    item = preset_catalog()[0]
    response = client.post(
        "/studio/run/stream",
        headers=unlock(),
        json={"preset_id": item["id"], "inputs": item["inputs"]},
    )
    assert '"type":"error","status":503' in response.text
    assert "private database credential" not in response.text
