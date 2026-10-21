"""Real PostgreSQL mirror, cursor and read-only access regressions; disposable DSN only."""

import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.research import database, store
from app.research.design import Design, plan


@pytest.fixture
def mirror(tmp_path, monkeypatch):
    url = os.getenv("RESEARCH_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RESEARCH_TEST_DATABASE_URL to a disposable PostgreSQL database")
    monkeypatch.setenv("STUDIO_RESEARCH_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_RESEARCH_DATABASE", "true")
    monkeypatch.setattr(database.settings, "NEON_READ_ONLY", False)
    monkeypatch.setattr(database, "_get_conn", lambda: psycopg2.connect(url))
    monkeypatch.setattr(database, "_put_conn", lambda conn: conn.close())
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            ddl = (Path(__file__).resolve().parents[2] / "sql/studio_research.sql").read_text()
            cur.execute(ddl)
            cur.execute(ddl)  # Explicit migration is safe to reapply.
    study_id = str(uuid4())
    planned = plan(
        Design(
            trips=["short-1d"],
            personas=["nature"],
            stops_per_day=[1],
            pipeline=False,
            solver_repeats=1,
        )
    )
    key = store.create(study_id, "private-visitor", planned, {"source_snapshot_hash": "frozen"})
    yield study_id, key, planned


def test_backfill_and_incremental_late_low_id_preserve_every_observation(mirror):
    study_id, key, planned = mirror
    case_id = len(planned["cases"]) - 1
    result = {
        "outcome": "completed",
        "completed": True,
        "solver_status": "FEASIBLE",
        "utility_values": [0.5, 0.8],
        "solver_seconds": 2.125,
    }
    store.save(study_id, case_id, "finished", result)
    assert database.mirror_once() == len(planned["cases"])
    first, protocol, _ = database.read(study_id)
    assert protocol == {k: v for k, v in planned.items() if k != "cases"}
    assert first["rows"][0]["solver_status"] == "FEASIBLE"
    assert first["rows"][0]["solver_seconds"] == 2.125
    assert key not in json.dumps(first) and "private-visitor" not in json.dumps(first)
    assert database.mirror_once() == 0
    store.save(study_id, 0, "finished", result | {"solver_status": "UNKNOWN", "completed": False})
    assert database.mirror_once() == 1
    second, _, _ = database.read(study_id, first["cursor"])
    assert [row["id"] for row in second["rows"]] == [0]
    assert second["rows"][0]["solver_status"] == "UNKNOWN"
    assert second["progress"]["finished"] == 2
    _, _, rows = database.read(study_id, export=True)
    assert len(rows) == len(planned["cases"])
    assert next(row for row in rows if row["id"] == case_id)["utility_values"] == [0.5, 0.8]


def test_database_read_access_needs_studio_session_and_never_grants_control(mirror):
    study_id, key, _ = mirror
    store.save(study_id, 0, "finished", {"solver_status": "OPTIMAL", "completed": True})
    database.mirror_once()
    client = TestClient(app)
    url = f"/studio/research/saved/{study_id}"
    for path in ("/studio/research/saved", url, url + "/export"):
        assert client.get(path).status_code == 401
    token = client.post("/studio/access", json={"password": "cp-sat"}).json()["token"]
    headers = {"X-Studio-Session": token}
    library = client.get("/studio/research/saved", headers=headers)
    assert {"id": study_id, "database": True} in library.json()["studies"]
    assert key not in library.text and "private-visitor" not in library.text
    response = client.get(url, headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["rows"][0]["solver_status"] == "OPTIMAL"
    assert key not in response.text and "inputs" not in response.json()["rows"][0]
    export = client.get(url + "/export", headers=headers)
    assert export.status_code == 200 and key not in export.text
    assert export.json()["protocol"]["cases"][0]["inputs"]
    assert "OPTIMAL" in client.get(url + "/export?format=csv", headers=headers).text
    assert client.get(url + "/export?format=bad", headers=headers).status_code == 422
    assert client.get(f"/studio/research/saved/{uuid4()}", headers=headers).status_code == 404
    assert client.post(url + "/pause", headers=headers).status_code in {404, 405}
    assert (
        client.post(f"/studio/research/batches/{study_id}/pause", headers=headers).status_code
        == 404
    )
    os.environ["STUDIO_RESEARCH_DATABASE"] = "false"
    assert client.get(url, headers=headers).status_code == 503


def test_conflicting_source_and_read_only_gate_leave_database_intact(mirror, monkeypatch):
    study_id, _, _ = mirror
    database.mirror_once()
    before, protocol, rows = database.read(study_id, export=True)
    with store.connection() as local:
        local.execute("UPDATE studies SET identity=? WHERE id=?", ('{"changed":true}', study_id))
    with pytest.raises(ValueError, match="conflicts"):
        database.mirror_once()
    after, original_protocol, original_rows = database.read(study_id, export=True)
    assert after == before and original_protocol == protocol and original_rows == rows
    monkeypatch.setattr(database.settings, "NEON_READ_ONLY", True)
    with pytest.raises(RuntimeError, match="disabled"):
        database.mirror_once()
    assert database.read(study_id)[0]["cursor"] == before["cursor"]
