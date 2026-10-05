"""Lab-only telemetry and versioned, comparable measurements. No credentials or prompts."""

import hashlib
import json
import math
import os
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from statistics import mean, pstdev
from threading import Lock
from time import perf_counter

METRIC_VERSION = "selection-surplus-v2"
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


def _number(value):
    return (
        value
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        else None
    )


def _instant(value):
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(UTC) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def trip_evaluation(envelope):
    """Measurements from actual route evidence, including partially completed runs."""
    route = envelope.get("route")
    inputs = envelope["input_snapshot"]
    live = envelope["mode"] == "live"
    assessed = live and route is not None
    stops = (route or {}).get("stops") or []
    baseline = envelope.get("direct_route") or {}
    reason = None if assessed else "selection_only" if not live else "route_unavailable"
    driving = {"assessment_reason": reason}
    for name, unit in (("distance", "meters"), ("duration", "seconds")):
        direct = _number(baseline.get(name)) if live else None
        final = _number((route or {}).get(name)) if assessed else None
        delta = final - direct if direct is not None and final is not None else None
        driving.update(
            {
                f"direct_{name}_{unit}": direct,
                f"final_{name}_{unit}": final,
                f"extra_{name}_{unit}": delta,
                f"extra_{name}_percent": 100 * delta / direct
                if delta is not None and direct > 0
                else None,
            }
        )
    if assessed and any(
        driving[f"direct_{name}_{unit}"] is None
        for name, unit in (("distance", "meters"), ("duration", "seconds"))
    ):
        driving["assessment_reason"] = "baseline_incomplete"
    elif assessed and any(baseline.get(name) == 0 for name in ("distance", "duration")):
        driving["assessment_reason"] = "zero_baseline_percentage_unassessed"
    requested = inputs.get("num_stops")
    delivered = sum(stop.get("type") == "stop" for stop in stops) if assessed else None
    selected = sum(
        bool(item.get("selected")) for item in envelope["explanation"].get("candidates", [])
    )
    if not envelope["explanation"].get("solver") and not envelope["explanation"].get("candidates"):
        selected = None
    fulfillment = {
        "requested": requested,
        "solver_selected": selected,
        "delivered": delivered,
        "ratio": delivered / requested
        if delivered is not None and requested and requested > 0
        else None,
        "assessment_reason": reason
        if not assessed
        else None
        if requested
        else "requested_count_unavailable",
    }
    hotels = [stop for stop in stops if stop.get("type") == "hotel"]
    expected_rooms = len(inputs.get("hotel_rooms") or [])
    prices = []
    quotes_complete = assessed
    for hotel in hotels:
        offers = hotel.get("room_offers") or []
        valid = [_number(offer.get("price")) for offer in offers]
        if (
            not offers
            or (expected_rooms and len(offers) != expected_rooms)
            or any(price is None or price < 0 for price in valid)
        ):
            quotes_complete = False
        prices.extend(price for price in valid if price is not None and price >= 0)
    budget = _number(inputs.get("budget"))
    costs = {
        "currency": "USD",
        "scope": "quoted_room_nights_only",
        "quotes_complete": quotes_complete,
        "quoted_total_usd": sum(prices) if quotes_complete else None,
        "room_night_count": len(prices) if quotes_complete else None,
        "max_room_night_usd": max(prices, default=0) if quotes_complete else None,
        "over_target_room_nights": sum(price > budget for price in prices)
        if quotes_complete and budget is not None
        else None,
        "above_target_total_usd": sum(max(0, price - budget) for price in prices)
        if quotes_complete and budget is not None
        else None,
        "assessment_reason": reason
        if not assessed
        else "incomplete_room_quotes"
        if not quotes_complete
        else "nightly_target_unavailable"
        if budget is None
        else None,
    }
    final = next((stop for stop in reversed(stops) if stop.get("type") == "end"), {})
    arrival = _instant(final.get("arrival_time")) if assessed else None
    start = _instant(inputs.get("start_date"))
    itinerary = envelope.get("itinerary")
    schedule = {
        "itinerary_days": len(itinerary) if live and itinerary is not None else None,
        "overnights": len(hotels) if assessed else None,
        "final_arrival": final.get("arrival_time") if arrival else None,
        "final_timezone": final.get("timezone") if arrival else None,
        "elapsed_trip_seconds": (arrival - start).total_seconds() if arrival and start else None,
        "assessment_reason": reason
        if not assessed
        else None
        if arrival and start and itinerary is not None
        else "schedule_incomplete",
    }
    slack = []
    timed_stops = [stop for stop in stops if stop.get("type") in {"stop", "hotel", "end"}]
    for stop in timed_stops if assessed else []:
        checked = _instant(
            stop.get("departure_time" if stop.get("type") == "stop" else "arrival_time")
        )
        deadline = _instant(stop.get("deadline"))
        if checked and deadline:
            slack.append((deadline - checked).total_seconds())
    complete = assessed and bool(timed_stops) and len(slack) == len(timed_stops)
    compliance = {
        "assessed_stops": len(slack),
        "expected_stops": len(timed_stops) if assessed else None,
        "min_deadline_slack_seconds": min(slack) if complete else None,
        "violation_count": sum(value < -1e-6 for value in slack) if complete else None,
        "assessment_reason": reason
        if not assessed
        else None
        if complete
        else "deadline_evidence_incomplete",
    }
    stages = [
        {"name": stage["name"], "status": stage["status"]} for stage in envelope.get("stages", [])
    ]
    warnings = (
        list(
            dict.fromkeys(
                [
                    *((route or {}).get("warnings") or []),
                    *(
                        stop[key]
                        for stop in stops
                        for key in ("warning", "late_check_in_notice")
                        if stop.get(key)
                    ),
                ]
            )
        )
        if assessed
        else []
    )
    return {
        "driving": driving,
        "stop_fulfillment": fulfillment,
        "schedule": schedule,
        "schedule_compliance": compliance,
        "hotel_costs": costs,
        "warnings": warnings,
        "stages": stages,
        "first_failed_stage": next(
            (stage["name"] for stage in stages if stage["status"] == "failed"), None
        ),
        "error_code": (envelope.get("error") or {}).get("code"),
        "completed": envelope.get("error") is None
        and live
        and route is not None
        and itinerary is not None,
    }


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
        "trip_evaluation": trip_evaluation(envelope),
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
            groups[
                (
                    row["metrics"]["cohort_key"],
                    row["metrics"].get("metric_version"),
                    row["metrics"].get("revision"),
                )
            ].append(row)
    result = []
    for (key, version, revision), items in groups.items():
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
                "metric_version": version,
                "revision": revision,
                "completion_rate": mean(
                    [
                        item["status"] == "completed"
                        for item in items
                        if item.get("status") in {"completed", "failed"}
                    ]
                )
                if any(item.get("status") in {"completed", "failed"} for item in items)
                else None,
                "completion_assessed": sum(
                    item.get("status") in {"completed", "failed"} for item in items
                ),
                "unfinished_runs": sum(item.get("status") == "running" for item in items),
                "trip_evaluation": {
                    label: stats(
                        [
                            value
                            for m in metrics
                            if (value := (m.get("trip_evaluation", {}).get(section, {}).get(field)))
                            is not None
                        ]
                    )
                    for label, section, field in (
                        ("extra_distance_meters", "driving", "extra_distance_meters"),
                        ("extra_duration_seconds", "driving", "extra_duration_seconds"),
                        ("stop_fulfillment_ratio", "stop_fulfillment", "ratio"),
                        ("quoted_hotel_total_usd", "hotel_costs", "quoted_total_usd"),
                    )
                },
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
