"""Research observations: selection comparisons only, without costs."""

import math

from app.routing.run_metrics import utility_summary


def observation(envelope, elapsed_ms):
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
    good = not envelope.get("error") and solver.get("status") in {"OPTIMAL", "FEASIBLE"}
    utility = utility_summary(selection) if good else {}
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
        "utility_values": selection if good and utility else None,
        "solver_status": solver.get("status", "NOT_RUN"),
        "solver_seconds": solver.get("wall_time_seconds"),
        "runtime_seconds": elapsed_ms / 1000,
        "max_gap_seconds": solver.get("maximum_baseline_gap_seconds"),
        "estimated_detour_seconds": solver.get("estimated_detour_seconds"),
        "selected": solver.get("selected_count"),
        "requested": solver.get("requested_stops"),
        "fulfillment": (
            solver.get("selected_count") / solver["requested_stops"]
            if solver.get("selected_count") is not None and solver.get("requested_stops")
            else None
        ),
        "objective": solver.get("objective_value"),
        "best_bound": solver.get("best_bound"),
        "error": envelope.get("error"),
        "candidate_count": len(envelope.get("explanation", {}).get("candidates", [])),
    }
