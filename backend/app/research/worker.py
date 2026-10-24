"""Detached campaign execution: two live trips and one solver trial at a time."""

import asyncio
import os
import sys
from dataclasses import replace
from time import perf_counter
from uuid import UUID, uuid5

from fastapi import HTTPException

from app.research import evidence, store
from app.research.metrics import observation
from app.routers import algorithm_lab as lab
from app.routing.cp_sat_selection import SelectionConfig, select_attractions
from app.routing.evaluation.runner import atomic, identity, json_text
from app.routing.explanation import capture_explanation
from app.routing.lab_presets import preset_catalog


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
            solver_only=True,
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


async def live_trial(case, study):
    started = perf_counter()
    run_id = uuid5(UUID(study["id"]), str(case["id"]))
    # A restart may inspect prior work, but never silently repeat a paid trip.
    previous = await asyncio.to_thread(lab.lab_runs.record, study["owner"], run_id)
    if previous:
        if previous["status"] == "running":
            return {
                "outcome": "interrupted",
                "completed": False,
                "solver_status": "NOT_RUN",
                "error": {
                    "code": "interrupted",
                    "message": "An earlier provider run has no terminal record; it was not repeated.",
                },
            }
        envelope = previous["result"] | {
            "run_record": {"id": str(run_id), "saved": True, "metrics": previous["metrics"]}
        }
    else:
        request = lab.LabRun(
            preset_id=case["preset_id"],
            # Operational hotel selection uses the ordinary default, never a research factor.
            inputs={
                **case["inputs"],
                "budget": next(row for row in preset_catalog() if row["id"] == "short-day")[
                    "inputs"
                ]["budget"],
            },
            batch_id=study["id"],
            repeat_index=case["repeat"],
        )
        envelope = await asyncio.wait_for(
            evidence.recorded_run(request, study["owner"], run_id), timeout=1200
        )
    atomic(store.directory() / study["id"] / f"{run_id}.json", json_text(envelope))
    elapsed = (
        ((envelope.get("run_record") or {}).get("metrics") or {}).get("latency_ms", {}).get("total")
    )
    result = observation(
        envelope, elapsed if elapsed is not None else (perf_counter() - started) * 1000
    ) | {
        "evidence": "live_pipeline",
        "live_evidence": envelope,
    }
    try:
        captured = evidence.capture(envelope, case)
        if case["repeat"] == 1:
            result["capture"] = captured
    except (ValueError, KeyError) as exc:
        result["capture_error"] = str(exc)
        result["halt_reason"] = (
            "Candidate provenance validation failed; inspect the saved live evidence."
        )
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
            # Reconcile live records; solver trials can safely be recomputed.
            store.save(study_id, case["id"], "pending")
            case["state"] = "pending"
    captures = iter(
        [
            row
            for row in cases
            if row["track"] == "pipeline" and row["repeat"] == 1 and row["state"] == "pending"
        ]
    )
    live = iter(
        [
            row
            for row in cases
            if row["track"] == "pipeline" and row["repeat"] > 1 and row["state"] == "pending"
        ]
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
                    await live_trial(case, study)
                    if case["track"] == "pipeline"
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
            if case["track"] == "pipeline":
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
    await asyncio.gather(lane(live), lane(live))
    pending = any(row["state"] in {"pending", "running"} for row in store.rows(study_id))
    store.state(study_id, "paused" if pending else "complete")


if __name__ == "__main__":
    try:
        asyncio.run(execute(str(UUID(sys.argv[1]))))
    except BaseException:
        store.state(str(UUID(sys.argv[1])), "interrupted")
        raise
