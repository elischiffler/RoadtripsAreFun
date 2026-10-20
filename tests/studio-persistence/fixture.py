"""Synthetic browser QA on port 8004: actual Studio routes/jobs, memory-only run storage.

Run with backend/.venv/bin/python tests/studio-persistence/fixture.py. Pair with a
Vite server on 5174 and VITE_BACKEND_SERVER=http://127.0.0.1:8004/. No provider or
hosted database functions execute. Not a deployment or real trip acceptance test.
"""

import asyncio
import copy
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import uvicorn
from app.agent.progress import emit
from app.crud import lab_runs
from app.main import app
from app.routers import algorithm_lab as lab

rows = {}
executions = []


def record(owner, key):
    row = rows.get(str(key))
    return copy.deepcopy(row) if row and row["owner"] == owner else None


def begin(owner, payload, key=None):
    key = str(key or uuid4())
    if key in rows:
        raise ValueError("Duplicate fixture run")
    rows[key] = {
        "id": key,
        "owner": owner,
        "status": "running",
        "mode": payload["mode"],
        "preset_id": payload["preset_id"],
        "input": payload["inputs"],
        "metrics": None,
        "started_at": "2026-10-19T18:00:00-07:00",
        "result": None,
    }
    return key


def finish(owner, key, envelope, metrics):
    row = rows[str(key)]
    assert row["owner"] == owner
    row.update(
        status="completed",
        input=envelope["input_snapshot"],
        metrics=copy.deepcopy(metrics),
        result=copy.deepcopy(envelope),
    )


def history(owner, limit=50, offset=0):
    return [
        {**copy.deepcopy(row), "has_result": bool(row["result"])}
        for row in reversed(list(rows.values()))
        if row["owner"] == owner
    ][offset : offset + limit]


def cancel(owner, key):
    row = rows.get(str(key))
    if row and row["owner"] == owner and row["status"] == "running":
        row.update(
            status="failed",
            result={"error": {"code": "cancelled", "message": "Run cancelled."}},
        )


async def execute(payload, owner, departure):
    executions.append(1)
    for _ in range(30):
        emit("route.model", state="started", candidates=4, eligible=2, requestedStops=2)
        await asyncio.sleep(1)
    arrived = datetime.fromisoformat(departure) + timedelta(hours=1)
    left = arrived + timedelta(hours=1)
    stop = {
        "provider_id": "fixture:museum",
        "name": "Sample museum",
        "type": "stop",
        "duration": 3600,
        "coordinates": [37.8, -122.4],
        "arrival_time": arrived.isoformat(),
        "departure_time": left.isoformat(),
        "timezone": "America/Los_Angeles",
        "source_attribution": "National Park Service factual heritage-unit and visitor-arrival data. No NPS endorsement.",
        "source_release": "nps-heritage-2026-10-15",
        "address": "Sample address",
    }
    return {
        "schema_version": 1,
        "mode": "live",
        "snapshot": {
            "id": str(uuid4()),
            "label": "Sample trip",
            "source": "Synthetic browser fixture",
        },
        "input_snapshot": {
            **payload.inputs.model_dump(mode="json"),
            "start_date": departure,
        },
        "route": {"distance": 160934.4, "duration": 7200, "cost": 0, "stops": [stop]},
        "itinerary": [{"date": "Sample day", "stops": [{**stop, "time": "10:00 AM"}]}],
        "explanation": {
            "candidates": [
                {
                    "name": "Sample museum",
                    "provider_id": "fixture:museum",
                    "selected": True,
                    "utility": 0.8,
                }
            ],
            "solver": {
                "status": "OPTIMAL",
                "objective_direction": "minimize",
                "selected_count": 1,
                "eligible_count": 2,
                "requested_stops": payload.inputs.num_stops,
            },
        },
        "stages": [],
        "error": None,
    }


lab_runs.record = record
lab_runs.begin = begin
lab_runs.finish = finish
lab_runs.cancel = cancel
lab_runs.history = history
lab_runs.result = lambda owner, key: (record(owner, key) or {}).get("result")
lab.execute_run = execute


@app.get("/fixture/status")
async def status():
    return {
        "executions": len(executions),
        "rows": len(rows),
        "statuses": [row["status"] for row in rows.values()],
    }


if __name__ == "__main__":
    # No application lifespan: it warms the real configured DB pool. Only memory fixtures run.
    uvicorn.run(app, host="127.0.0.1", port=8004, lifespan="off")
