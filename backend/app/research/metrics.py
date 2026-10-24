"""Research observations: selection comparisons and delivered trips, without costs."""

import math

from app.routing.run_metrics import utility_summary


def observation(envelope, elapsed_ms, *, solver_only=False):
    metrics = (envelope.get("run_record") or {}).get("metrics") or {}
    trip = metrics.get("trip_evaluation") or {}
    solver = envelope.get("explanation", {}).get("solver") or {}
    selection = [
        item["utility"]
        for item in envelope.get("explanation", {}).get("candidates", [])
        if item.get("selected")
    ]
    eligible = [
        row
        for row in envelope.get("explanation", {}).get("candidates", [])
        if row.get("selected") or row.get("reason") == "eligible_not_selected"
    ]
    values = [row.get("utility") for row in eligible]
    valid_pool = bool(values) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 < v <= 1
        for v in values
    )
    pool_mean = utility_summary(values)["mean"] if valid_pool else None
    selected_mean = (
        utility_summary(selection)["mean"]
        if selection and solver.get("status") in {"OPTIMAL", "FEASIBLE"}
        else None
    )
    compared = pool_mean is not None and selected_mean is not None
    fulfillment = trip.get("stop_fulfillment") or {}
    good = not envelope.get("error") and (
        solver.get("status") in {"OPTIMAL", "FEASIBLE"}
        and solver.get("selected_count") == solver.get("requested_stops")
        if solver_only
        else bool(trip.get("completed"))
        and fulfillment.get("ratio") == 1
        and (trip.get("schedule_compliance") or {}).get("violation_count") == 0
    )
    utility = (
        utility_summary(selection)
        if solver_only and good
        else ((trip.get("utility") or {}).get("delivered") or {})
        if good
        else {}
    )
    driving = trip.get("driving") or {}
    return {
        "outcome": "failed" if envelope.get("error") else "completed",
        "completed": good,
        "selection_assessed": compared,
        "candidate_utility_mean": pool_mean,
        "eligible_candidate_count": len(eligible),
        "selected_utility_mean": selected_mean,
        "utility_gain": selected_mean - pool_mean if compared else None,
        "best_available_utility_mean": solver.get("best_average_match"),
        "quality_loss": solver.get("quality_loss"),
        "spacing_deviation_seconds": solver.get("spacing_deviation_seconds"),
        "utility_mean": utility.get("mean"),
        "utility_min": utility.get("min"),
        "utility_max": utility.get("max"),
        "utility_median": utility.get("median"),
        "utility_values": (
            selection
            if solver_only
            else [
                item["utility"]
                for item in envelope.get("explanation", {}).get("candidates", [])
                if item.get("selected")
                and item.get("provider_id")
                in {
                    stop.get("provider_id")
                    for stop in (envelope.get("route") or {}).get("stops", [])
                    if stop.get("type") == "stop"
                }
            ]
        )
        if good and utility
        else None,
        "solver_status": solver.get("status", "NOT_RUN"),
        "solver_seconds": solver.get("wall_time_seconds"),
        "runtime_seconds": elapsed_ms / 1000,
        "max_gap_seconds": solver.get("maximum_baseline_gap_seconds")
        if solver_only
        else (trip.get("driving_gaps") or {}).get("maximum_attraction_gap_seconds"),
        "extra_meters": driving.get("extra_distance_meters") if not solver_only else None,
        "extra_seconds": driving.get("extra_duration_seconds") if not solver_only else None,
        "estimated_detour_seconds": solver.get("estimated_detour_seconds"),
        "delivered": solver.get("selected_count") if solver_only else fulfillment.get("delivered"),
        "requested": solver.get("requested_stops") if solver_only else fulfillment.get("requested"),
        "actual_days": (trip.get("schedule") or {}).get("itinerary_days"),
        "fulfillment": (
            solver.get("selected_count") / solver["requested_stops"]
            if solver.get("selected_count") is not None and solver.get("requested_stops")
            else None
        )
        if solver_only
        else fulfillment.get("ratio"),
        "objective": solver.get("objective_value"),
        "best_bound": solver.get("best_bound"),
        "error": envelope.get("error"),
        "failed_stage": trip.get("first_failed_stage"),
        "candidate_count": metrics.get(
            "candidate_count", len(envelope.get("explanation", {}).get("candidates", []))
        ),
        "candidate_hash": metrics.get("candidate_hash"),
        "catalog_generations": sorted(
            {
                item["generation"]
                for row in metrics.get("candidate_snapshot", [])
                for item in row.get("source_provenance", [])
                if item.get("dataset") == "Roadtrips active catalog" and item.get("generation")
            }
        ),
        "source_releases": sorted(
            {
                row["source_release"]
                for row in metrics.get("candidate_snapshot", [])
                if row.get("source_release")
            }
        ),
        "run_id": (envelope.get("run_record") or {}).get("id"),
        "saved": (envelope.get("run_record") or {}).get("saved"),
    }
