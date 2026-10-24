"""Real, immutable research inputs and cost-free live evidence."""

import asyncio
from copy import deepcopy
from time import perf_counter

from fastapi import HTTPException

from app.research import store
from app.routers import algorithm_lab as lab
from app.routing.cp_sat_selection import SelectionConfig, _prepare
from app.routing.profiles import AttributeRatings, crossmatch
from app.routing.run_metrics import fingerprint, measuring, trip_evaluation


def scenario_key(case):
    return f"{case['trip']}:{case['persona']}:{case['stops_per_day']}"


def without_costs(value):
    """Research never persists financial inputs, quotes or budget measurements."""
    if isinstance(value, list):
        return [without_costs(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: without_costs(item)
        for key, item in value.items()
        if not any(word in key.lower() for word in ("budget", "price", "cost", "quote", "currency"))
        and key not in {"room_offers", "within_nightly_room_target", "feasibility_reason"}
    }


def capture(envelope, case):
    """Freeze the last actual solver input; never construct replacement attractions."""
    explanation = envelope.get("explanation") or {}
    solver = explanation.get("solver") or {}
    baseline = solver.get("baseline_seconds")
    candidates = deepcopy(explanation.get("candidates") or [])
    if not candidates or baseline is None:
        return None
    if len(candidates) > 60:
        raise ValueError("Research capture exceeded the production candidate limit")
    for row in candidates:
        if not row.get("source_generation") or not row.get("source_provenance"):
            raise ValueError("Research requires catalog-backed candidate provenance")
        provenance = row.get("provenance") or {}
        if not provenance.get("ratings_created_at") or "/" not in (
            provenance.get("ratings_provider") or ""
        ):
            raise ValueError(
                "Research requires persisted traits with their upstream model identity"
            )
        ratings = AttributeRatings.model_validate(row["attribute_ratings"])
        score = crossmatch(case["inputs"]["persona_weights"], ratings.model_dump()).utility
        if abs(score - row["utility"]) > 1e-9:
            raise ValueError("Captured utility does not match the frozen persona and traits")
        for key in ("selected", "reason", "objective_coefficient"):
            row.pop(key, None)
    eligible, _ = _prepare(candidates, baseline, SelectionConfig())
    # Retain every supplied input, including exclusions, for denominator auditing.
    result = {
        "evidence": "real_catalog_and_measured_roads",
        "scenario": scenario_key(case),
        "capture_case_id": case["id"],
        "run_id": (envelope.get("run_record") or {}).get("id"),
        "captured_at": store.now(),
        "baseline_seconds": baseline,
        "direct_route": envelope.get("direct_route"),
        "inputs": case["inputs"],
        "candidates": candidates,
        "eligible_count": len(eligible),
        "query_points": explanation.get("query_points") or [],
    }
    result["hash"] = fingerprint(result)
    return result


def validate_capture(snapshot, case):
    if not snapshot or snapshot.get("evidence") != "real_catalog_and_measured_roads":
        raise ValueError("No measured real candidate pool was captured for this scenario")
    if snapshot["hash"] != fingerprint({k: v for k, v in snapshot.items() if k != "hash"}):
        raise ValueError("Frozen candidate capture hash mismatch")
    if snapshot["scenario"] != scenario_key(case) or snapshot["inputs"] != case["inputs"]:
        raise ValueError("Frozen capture belongs to different scenario inputs")
    return snapshot


async def recorded_run(payload, owner, run_id):
    """Use the shared live planner, retaining only nonfinancial research measurements."""
    run_id = str(run_id)
    departure = lab._departure(
        payload.inputs,
        lab.ENDPOINTS[payload.inputs.start_id].get("timezone", "America/Los_Angeles"),
    )
    try:
        await asyncio.to_thread(
            lab.lab_runs.begin, owner, without_costs(payload.model_dump(mode="json")), str(run_id)
        )
    except Exception as exc:
        raise HTTPException(503, "Research storage unavailable; no provider work started") from exc
    started = perf_counter()
    try:
        with measuring() as telemetry:
            envelope = await lab.execute_run(payload, owner, departure)
            # The ordinary planner still chooses hotels; research does not assess their costs.
            trip = trip_evaluation(envelope, include_costs=False)
        metrics = {
            "trip_evaluation": trip,
            "latency_ms": {"total": (perf_counter() - started) * 1000},
            "candidate_snapshot": (envelope.get("explanation") or {}).get("candidates", []),
            "candidate_count": len((envelope.get("explanation") or {}).get("candidates", [])),
            "candidate_hash": fingerprint(
                (envelope.get("explanation") or {}).get("candidates", [])
            ),
            "provider_measurements": {
                key: value for key, value in telemetry.items() if key != "lock"
            },
            "evidence_layer": "live_pipeline",
        }
        envelope = without_costs(envelope)
        metrics = without_costs(metrics)
        await asyncio.to_thread(lab.lab_runs.finish, owner, run_id, envelope, metrics)
    except asyncio.CancelledError:
        await asyncio.to_thread(lab.lab_runs.cancel, owner, run_id)
        raise
    except Exception as exc:
        raise HTTPException(
            503, "Research result persistence failed; inspect the saved attempt"
        ) from exc
    envelope["run_record"] = {"id": str(run_id), "saved": True, "metrics": metrics}
    return envelope
