"""Studio research API; private results use a per-study read/control capability."""

import csv
import io
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict

from app.research import store
from app.research.design import PERSONAS, TRIPS, Design, plan
from app.routers.studio import require_studio_session
from app.routing.evaluation.runner import identity

router = APIRouter(prefix="/studio/research", tags=["studio research"])
_workers = {}


def require_execution():
    if os.getenv("STUDIO_RESEARCH_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Batch execution is disabled on this server.")


def reap_workers():
    for study_id, child in list(_workers.items()):
        if child.poll() is not None:
            _workers.pop(study_id, None)
            record = store.study(study_id, trusted=True)
            if record["state"] in {"starting", "running", "pausing"}:
                store.state(study_id, "interrupted")


class CreateStudy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    design: Design


@router.get("/catalog")
def catalog(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "trips": [{"id": key, "label": value[0]} for key, value in TRIPS.items()],
        "personas": list(PERSONAS),
        "defaults": Design().model_dump(mode="json"),
        "execution_enabled": os.getenv("STUDIO_RESEARCH_ENABLED", "false").lower() == "true",
    }


@router.post("/plan")
def preview(design: Design, user: str = Depends(require_studio_session)):
    result = plan(design)
    return {"counts": result["counts"], "variants": result["variants"]}


@router.post("/batches", status_code=201)
def create(payload: CreateStudy, response: Response, user: str = Depends(require_studio_session)):
    require_execution()
    response.headers["Cache-Control"] = "no-store"
    key = store.create(str(payload.id), user, plan(payload.design), identity())
    return {"id": str(payload.id), "key": key}


def authorized(study_id: UUID, x_studio_batch_key: str | None = Header(default=None)):
    reap_workers()
    return store.study(str(study_id), x_studio_batch_key)


@router.get("/batches/{study_id}")
def snapshot(response: Response, study=Depends(authorized), after: int = Query(default=0, ge=0)):
    response.headers["Cache-Control"] = "no-store"
    rows, progress, cursor = store.changes(study["id"], after)
    planned = study["plan"]
    return {
        "id": study["id"],
        "schema_version": 1,
        "state": study["state"],
        "created_at": study["created_at"],
        "identity": study["identity"],
        "counts": planned["counts"],
        "design": planned["design"],
        "variants": planned["variants"],
        "dataset_hash": planned["dataset_hash"],
        "progress": progress,
        "cursor": cursor,
        "rows": [
            {key: value for key, value in row.items() if key not in {"inputs", "preset_id"}}
            for row in rows
            if row["state"] == "finished"
        ],
    }


@router.post("/batches/{study_id}/start")
def start(study=Depends(authorized)):
    require_execution()
    if study["identity"]["source_snapshot_hash"] != identity()["source_snapshot_hash"]:
        raise HTTPException(
            409, "Application source changed. Create a new study to keep revisions separate."
        )
    store.claim(study["id"])
    root = store.directory() / study["id"]
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        command = [sys.executable, "-m", "app.research.worker", study["id"]]
        if sys.platform == "darwin" and Path("/usr/bin/caffeinate").is_file():
            command = ["/usr/bin/caffeinate", "-i", *command]
        with (root / "worker.log").open("ab") as log:
            child = subprocess.Popen(
                command,
                cwd=Path(__file__).resolve().parents[2],
                env={**os.environ, "STUDIO_RESEARCH_DIR": str(store.directory())},
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        with store.connection() as conn:
            conn.execute("UPDATE studies SET pid=? WHERE id=?", (child.pid, study["id"]))
        _workers[study["id"]] = child
    except Exception:
        store.state(study["id"], "interrupted")
        raise HTTPException(503, "The study worker could not start") from None
    return {"state": "starting"}


@router.post("/batches/{study_id}/pause")
def pause(study=Depends(authorized)):
    with store.connection() as conn:
        conn.execute(
            "UPDATE studies SET state='pausing' WHERE id=? AND state IN ('starting','running')",
            (study["id"],),
        )
    return {"state": store.study(study["id"], trusted=True)["state"]}


@router.get("/batches/{study_id}/export")
def export(study=Depends(authorized), format: str = "json"):
    data = snapshot(Response(), study, 0)
    if format == "json":
        return Response(
            store.dumps(data | {"protocol": study["plan"] | {"cases": store.rows(study["id"])}}),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="study-{study["id"]}.json"',
                "Cache-Control": "no-store",
            },
        )
    if format != "csv":
        raise HTTPException(422, "Choose json or csv")
    output = io.StringIO()
    fields = [
        "id",
        "state",
        "trip",
        "persona",
        "stops_per_day",
        "target_days",
        "track",
        "variant",
        "repeat",
        "outcome",
        "completed",
        "utility_mean",
        "utility_min",
        "utility_max",
        "utility_median",
        "max_gap_seconds",
        "extra_meters",
        "extra_seconds",
        "budget_utilization",
        "budget_excess_usd",
        "runtime_seconds",
        "solver_seconds",
        "solver_status",
        "objective",
        "actual_days",
        "fulfillment",
        "failed_stage",
        "error_code",
        "delivered",
        "requested",
        "candidate_count",
        "candidate_hash",
        "evidence",
        "run_id",
        "study_id",
        "revision",
        "metric_version",
        "source_snapshot_hash",
        "dataset_hash",
        "parameter",
        "parameter_value",
        "seed",
        "attempt_started_at",
        "recorded_at",
    ]
    writer = csv.DictWriter(output, fields, extrasaction="ignore")
    writer.writeheader()
    variants = {row["id"]: row for row in study["plan"]["variants"]}
    for row in store.rows(study["id"]):
        condition = variants.get(row["variant"], {})
        writer.writerow(
            row
            | {
                "study_id": study["id"],
                "error_code": (row.get("error") or {}).get("code"),
                "revision": study["identity"].get("revision"),
                "metric_version": study["identity"].get("metric_version"),
                "source_snapshot_hash": study["identity"]["source_snapshot_hash"],
                "dataset_hash": study["plan"]["dataset_hash"] if row["track"] == "solver" else None,
                "parameter": condition.get("parameter"),
                "parameter_value": condition.get("value"),
                "seed": row["repeat"] - 1 if row["track"] == "solver" else None,
            }
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="study-{study["id"]}.csv"',
            "Cache-Control": "no-store",
        },
    )
