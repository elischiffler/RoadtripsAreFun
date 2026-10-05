"""Lab-only telemetry and versioned, comparable measurements. No credentials or prompts."""

import hashlib
import json
import os
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from statistics import mean, pstdev
from threading import Lock
from time import perf_counter

METRIC_VERSION = "selection-surplus-v1"
_active = ContextVar("lab_measurements", default=None)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@contextmanager
def measuring():
    data = {"calls": {}, "durations": {}, "events": {}, "lock": Lock()}
    token = _active.set(data)
    try:
        yield data
    finally:
        _active.reset(token)


def increment(name, bucket="calls"):
    if data := _active.get():
        with data["lock"]:
            data[bucket][name] = data[bucket].get(name, 0) + 1


def duration(name, milliseconds):
    if data := _active.get():
        with data["lock"]:
            data["durations"][name] = data["durations"].get(name, 0) + milliseconds


@contextmanager
def timed(name):
    started = perf_counter()
    try:
        yield
    finally:
        duration(name, (perf_counter() - started) * 1000)


def compile_metrics(envelope, telemetry, elapsed_ms):
    """Keep the selection score separate from full-trip feasibility and cost."""
    explanation = envelope["explanation"]
    solver = explanation.get("solver") or {}
    candidates = explanation.get("candidates", [])
    model = [
        {
            key: item.get(key)
            for key in (
                "provider_id",
                "coordinates",
                "attribute_ratings",
                "utility",
                "slot",
                "objective_coefficient",
            )
        }
        for item in candidates
    ]
    model.sort(key=lambda item: str(item["provider_id"]))
    inputs = envelope["input_snapshot"]
    canonical_inputs = {
        key: value
        for key, value in inputs.items()
        if key
        not in (
            "weights_source",
            "car_usage",
            "trip_profile",
            "start",
            "destination",
            "persona_weights",
        )
    }
    route = envelope.get("route")
    replay = envelope["mode"] == "replay"
    success = envelope["error"] is None
    stops = (route or {}).get("stops") or []
    hotels = [stop for stop in stops if stop.get("type") == "hotel"]
    quotes_complete = all(hotel.get("room_offers") for hotel in hotels)
    within_target = (
        all(
            offer["price"] <= inputs["budget"] for hotel in hotels for offer in hotel["room_offers"]
        )
        if route and quotes_complete
        else None
    )
    verified = (
        all(stop.get("provider_id") for stop in stops if stop.get("type") != "end")
        if route
        else None
    )
    feasibility = (
        None
        if replay
        else (
            False
            if not success
            else bool(verified and within_target)
            if within_target is not None
            else None
        )
    )
    selected = sorted(item["provider_id"] for item in candidates if item.get("selected"))
    # Only semantic route output: timings/UUIDs/provider fetch timestamps never enter this hash.
    output = {
        "selected": selected,
        "stops": [
            {
                key: stop.get(key)
                for key in (
                    "provider_id",
                    "name",
                    "type",
                    "coordinates",
                    "price",
                    "check_in_date",
                    "timezone",
                    "arrival_time",
                    "departure_time",
                )
            }
            for stop in ((route or {}).get("stops") or [])
        ],
        "cost": (route or {}).get("cost"),
        "duration": (route or {}).get("duration"),
    }
    input_hash = fingerprint(canonical_inputs)
    candidate_hash = fingerprint({"candidates": model, "points": explanation.get("query_points")})
    revision = os.getenv("ROADTRIPS_REVISION", "unversioned-local")
    comparison = fingerprint(
        {
            "input": input_hash,
            "candidates": candidate_hash,
            "mode": envelope["mode"],
            "metric": METRIC_VERSION,
            "revision": revision,
        }
    )
    cohort = fingerprint(
        {
            "input": input_hash,
            "mode": envelope["mode"],
            "metric": METRIC_VERSION,
            "revision": revision,
        }
    )
    objective = solver.get("objective_value")
    return {
        "metric_version": METRIC_VERSION,
        "revision": revision,
        "algorithm": "cp_sat",
        "input_hash": input_hash,
        "candidate_hash": candidate_hash,
        "cohort_key": cohort,
        "comparison_key": comparison,
        "output_hash": fingerprint(output) if success else None,
        "objective_score": objective,
        "objective_scope": "attraction_selection",
        "solver_status": solver.get("status", "NOT_RUN"),
        "best_bound": solver.get("best_bound"),
        "selected_utility_sum": sum(
            item.get("utility", 0) for item in candidates if item.get("selected")
        ),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "feasibility": feasibility,
        "feasibility_scope": "provider identities, validated drive schedule, quoted nightly room target; not total-trip budget or inventory guarantee",
        "feasibility_checks": {
            "verified_places": verified,
            "drivable": bool(route and success) if not replay else None,
            "within_nightly_room_target": within_target,
        },
        "full_trip_feasibility": None if replay else (False if not success else None),
        "feasibility_reason": "selection_only"
        if replay
        else ("planning_failed" if not success else "total_budget_constraint_not_implemented"),
        "route_validated": bool(route and success) if not replay else None,
        "within_total_budget": None,
        "budget_semantics": "nightly_target_per_room_usd",
        "latency_ms": {
            "total": round(elapsed_ms, 3),
            "gathering": telemetry["durations"].get("route.gathering", 0 if replay else None),
            "solving": telemetry["durations"].get(
                "solving", telemetry["durations"].get("route.solver")
            ),
            "generation": telemetry["durations"].get("generation", 0 if replay else None),
            "validation": telemetry["durations"].get("route.validation"),
            **telemetry["durations"],
        },
        "latency_scope": "Stage durations can overlap/nest; total excludes database writes and browser/network time",
        "observed_route": {
            "duration_seconds": (route or {}).get("duration"),
            "hotels": sum(
                stop.get("type") == "hotel" for stop in ((route or {}).get("stops") or [])
            ),
        }
        if route
        else None,
        "external_calls": {
            key: telemetry["calls"].get(key, 0)
            for key in (
                "tripadvisor",
                "mapbox",
                "language_model",
                "google_hotels",
                "opencage",
            )
        },
        "call_scope": "backend request attempts; excludes gateway-internal retries and redirects",
        "provider_events": {
            "llm_empty_retries": 0,
            "llm_empty_attempt_caps": 0,
            **telemetry["events"],
        },
        "ai_validation": {
            "retries": None,
            "attempt_cap_hit": None,
            "default_fallback": None,
            "reason": "No AI route solver or route-validation retry loop is active",
        },
        "candidate_snapshot": model,
        "query_points": explanation.get("query_points"),
        "selection_output": output,
    }


def aggregate_runs(rows):
    """Statistics over exactly the supplied history window; never mix different models."""
    groups = defaultdict(list)
    for row in rows:
        if row.get("metrics"):
            groups[row["metrics"]["cohort_key"]].append(row)
    result = []
    for key, items in groups.items():
        metrics = [item["metrics"] for item in items]
        scores = [m["objective_score"] for m in metrics if m["objective_score"] is not None]
        feasible = [m["feasibility"] for m in metrics if m.get("feasibility") is not None]
        outputs = [m["output_hash"] for m in metrics if m["output_hash"] is not None]
        references = {}
        for m in metrics:
            if (
                m["algorithm"] == "cp_sat"
                and m["solver_status"] == "OPTIMAL"
                and m["objective_score"] is not None
            ):
                references[m["comparison_key"]] = m["objective_score"]
        quality = [
            100 * m["objective_score"] / references[m["comparison_key"]]
            for m in metrics
            if m["objective_score"] is not None and references.get(m["comparison_key"], 0) > 0
        ]

        def stats(values):
            return (
                {
                    "count": len(values),
                    "mean": mean(values),
                    "stddev": pstdev(values),
                    "min": min(values),
                    "max": max(values),
                }
                if values
                else None
            )

        result.append(
            {
                "cohort_key": key,
                "runs": len(items),
                "objective": stats(scores),
                "latency_ms": stats([m["latency_ms"]["total"] for m in metrics]),
                "feasibility_rate": mean(feasible) if feasible else None,
                "feasibility_assessed": len(feasible),
                "deterministic_observed": len(set(outputs)) == 1 if len(outputs) >= 2 else None,
                "successful_outputs": len(outputs),
                "optimal_references": references,
                "quality_percent": stats(quality),
                "quality_gap_percent": stats([100 - value for value in quality]),
            }
        )
    return result
