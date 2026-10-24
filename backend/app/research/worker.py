"""Detached campaign execution: two input captures and one solver trial at a time."""

import asyncio
import json
import os
import sys
from dataclasses import replace
from time import perf_counter
from uuid import UUID, uuid5

from fastapi import HTTPException

from app.research import evidence, preparation, store
from app.research.metrics import observation
from app.routing.cp_sat_selection import SelectionConfig, select_attractions
from app.routing.evaluation.runner import atomic, identity, json_text
from app.routing.explanation import capture_explanation


def solver_trial(case, planned, snapshot=None):
    started = perf_counter()
    variant = next(row for row in planned["variants"] if row["id"] == case["variant"])
    config = replace(SelectionConfig(**variant["config"]), seed=case["repeat"] - 1)
    try:
        frozen = evidence.validate_capture(snapshot, case)
    except ValueError as exc:
        return {
            "outcome": "blocked",
            "completed": False,
            "solver_status": "NOT_RUN",
            "evidence": "real_capture_unavailable",
            "error": {"code": "capture_unavailable", "message": str(exc)},
        }
    baseline = frozen["baseline_seconds"]
    candidates = frozen["candidates"]
    with capture_explanation() as explanation:
        error = None
        try:
            select_attractions(
                candidates,
                frozen["query_points"],
                case["inputs"]["num_stops"],
                baseline,
                config=config,
            )
        except Exception as exc:
            error = {"code": "selection", "message": str(exc)}
        result = observation(
            {"explanation": explanation, "error": error},
            (perf_counter() - started) * 1000,
        )
        return result | {
            "evidence": "real_frozen_selection",
            "dataset_hash": frozen["hash"],
            "candidate_hash": frozen["hash"],
            "capture_case_id": frozen["capture_case_id"],
            "catalog_generations": sorted({row["source_generation"] for row in candidates}),
            "solver": explanation.get("solver"),
            "selected_ids": [
                row["provider_id"]
                for row in explanation.get("candidates", [])
                if row.get("selected")
            ],
        }


async def capture_trial(case, study):
    attempt_id = str(uuid5(UUID(study["id"]), str(case["id"])))
    root = store.directory() / study["id"]
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    result_path = root / f"{attempt_id}.json"
    intent_path = root / f"{attempt_id}.started"
    if result_path.is_file():
        return json.loads(result_path.read_text())
    try:
        with intent_path.open("x") as handle:
            os.chmod(intent_path, 0o600)
            handle.write(store.now())
    except FileExistsError:
        return {
            "outcome": "interrupted",
            "completed": False,
            "solver_status": "NOT_RUN",
            "error": {
                "code": "interrupted",
                "message": "An earlier capture did not finish; provider calls were not repeated.",
            },
        }
    envelope = await asyncio.wait_for(preparation.inputs(case, study), timeout=1200)
    envelope["attempt_id"] = attempt_id
    result = {
        "outcome": "failed" if envelope.get("error") else "completed",
        "completed": not envelope.get("error"),
        "evidence": "live_candidate_capture",
        "capture_evidence": envelope,
        "runtime_seconds": envelope["runtime_seconds"],
        "error": envelope.get("error"),
        "solver_status": "NOT_RUN",
    }
    try:
        if not envelope.get("error"):
            result["capture"] = evidence.capture(envelope, case)
            if result["capture"] is None:
                raise ValueError("Candidate capture did not retain measured baseline inputs")
            result["candidate_count"] = len(result["capture"]["candidates"])
    except (ValueError, KeyError) as exc:
        result.update(
            outcome="failed",
            completed=False,
            capture_error=str(exc),
            halt_reason="Candidate provenance validation failed; inspect the saved capture evidence.",
        )
    atomic(result_path, json_text(result))
    return result


def infrastructure_failure(result):
    error = result.get("error") or {}
    causes = [error, *error.get("causes", [])]
    return (
        bool(result.get("halt_reason"))
        or result.get("saved") is False
        or any(
            cause.get("http_status") in {401, 403}
            or cause.get("provider_code") in {"BAD_REQUEST", "UNAUTHORIZED", "MODEL_NOT_FOUND"}
            for cause in causes
        )
    )


async def execute(study_id):
    study = store.study(study_id, trusted=True)
    if study["identity"]["source_snapshot_hash"] != identity()["source_snapshot_hash"]:
        store.state(study_id, "interrupted")
        return  # A resumed study must not mix application source revisions.
    if not store.activate(study_id):
        return
    os.environ["ROADTRIPS_REVISION"] = study["identity"].get("revision", "unversioned-study")
    cases = store.rows(study_id)
    for case in cases:
        if case["state"] == "running":
            # Capture intent/result files prevent repeated provider calls; solver trials can be recomputed.
            store.save(study_id, case["id"], "pending")
            case["state"] = "pending"
    captures = iter(
        [row for row in cases if row["track"] == "capture" and row["state"] == "pending"]
    )
    frozen = {}
    solver = iter([row for row in cases if row["track"] == "solver" and row["state"] == "pending"])

    fatal_failures = 0

    async def lane(queue):
        nonlocal fatal_failures
        for case in queue:
            if store.study(study_id, trusted=True)["state"] != "running":
                return
            store.save(study_id, case["id"], "running")
            attempt_started = perf_counter()
            started_at = store.now()
            try:
                result = (
                    await capture_trial(case, study)
                    if case["track"] == "capture"
                    else await asyncio.to_thread(
                        solver_trial, case, study["plan"], frozen.get(evidence.scenario_key(case))
                    )
                )
            except Exception as exc:
                result = {
                    "outcome": "failed",
                    "completed": False,
                    "solver_status": "NOT_RUN",
                    "runtime_seconds": perf_counter() - attempt_started,
                    "error": {
                        "code": type(exc).__name__,
                        "message": "Run failed; inspect the worker log and saved run.",
                    },
                }
                if isinstance(exc, HTTPException) and exc.status_code in {401, 403, 503}:
                    result["halt_reason"] = (
                        "Run storage or authorization is unavailable. Pending runs were paused."
                    )
            result.update(attempt_started_at=started_at, recorded_at=store.now())
            if result.get("requested") is None:
                result["requested"] = case["inputs"]["num_stops"]
            store.save(study_id, case["id"], "finished", result)
            if case["track"] == "capture":
                fatal = infrastructure_failure(result)
                fatal_failures = fatal_failures + 1 if fatal else 0
                if fatal_failures >= 3:
                    store.state(study_id, "pausing")

    # Capture real pools first; controlled trials share them and run without provider contention.
    await asyncio.gather(lane(captures), lane(captures))
    frozen.update(
        {
            evidence.scenario_key(row): row["capture"]
            for row in store.rows(study_id)
            if row.get("capture")
        }
    )
    await lane(solver)
    pending = any(row["state"] in {"pending", "running"} for row in store.rows(study_id))
    store.state(study_id, "paused" if pending else "complete")


if __name__ == "__main__":
    try:
        asyncio.run(execute(str(UUID(sys.argv[1]))))
    except BaseException:
        store.state(str(UUID(sys.argv[1])), "interrupted")
        raise
