"""Publication eligibility and paired physical metrics; objectives stay model-scoped."""

import math
from collections import defaultdict

DEFAULTS = {
    "quality_loss": 0.10,
    "utility_threshold": 0.0,
    "detour_weight": 1,
    "time_limit_seconds": 5,
    "budget": 180,
}


def successful(row):
    if row.get("status") != "completed" or row.get("evidence_type") not in {
        "catalog_selection_with_captured_measurements",
        "catalog_recorded_pipeline",
    }:
        return False
    if row.get("assessments", {}).get("request_fulfillment") != "pass":
        return False
    return row.get("track") != "offline-pipeline" or (
        row.get("assessments", {}).get("pipeline_completion") == "pass"
        and row.get("assessments", {}).get("schedule") == "pass"
    )


def paired_results(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        if successful(row) and row.get("parameter") and row.get("paired_key"):
            groups[row["paired_key"]].append(row)
    results = []
    for key, items in groups.items():
        parameter = items[0]["parameter"]
        default = DEFAULTS.get(parameter, 0 if items[0]["persona"] == "nature" else 1)
        reference = next((row for row in items if row.get("parameter_value") == default), None)
        if reference is None:
            continue
        for row in items:
            if row is reference or row.get("fixture_hash") != reference.get("fixture_hash"):
                continue
            left, right = fields(reference), fields(row)
            results.append(
                {
                    "paired_key": key,
                    "parameter": parameter,
                    "baseline_value": default,
                    "value": row["parameter_value"],
                    "baseline_run_id": reference["run_id"],
                    "run_id": row["run_id"],
                    "fixture_hash": row["fixture_hash"],
                    "metric_deltas": {
                        name: right[name] - left[name]
                        for name in left
                        if isinstance(left[name], (int, float))
                        and isinstance(right.get(name), (int, float))
                    },
                    "selected_added": sorted(
                        set(row.get("selected_ids", [])) - set(reference.get("selected_ids", []))
                    ),
                    "selected_removed": sorted(
                        set(reference.get("selected_ids", [])) - set(row.get("selected_ids", []))
                    ),
                }
            )
    return results


def bound_comparisons(rows):
    references = {}
    for row in rows:
        solver = row.get("solver") or {}
        if (
            successful(row)
            and row.get("method") == "cp_sat"
            and row.get("solver_status") == "OPTIMAL"
            and solver.get("objective_value") is not None
        ):
            references[row["model_key"]] = solver["objective_value"]
    output = []
    for row in rows:
        solver = row.get("solver") or {}
        if row.get("evidence_type") not in {
            "catalog_selection_with_captured_measurements",
            "catalog_recorded_pipeline",
        }:
            continue
        if row.get("method") != "cp_sat" or row.get("solver_status") not in {"OPTIMAL", "FEASIBLE"}:
            continue
        incumbent, bound = solver.get("objective_value"), solver.get("best_bound")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (incumbent, bound)):
            continue
        optimum = references.get(row.get("model_key"))
        excess = incumbent - optimum if optimum is not None else None
        output.append(
            {
                "run_id": row["run_id"],
                "model_key": row["model_key"],
                "status": row["solver_status"],
                "incumbent": incumbent,
                "lower_bound": bound,
                "incumbent_bound_excess": incumbent - bound,
                "proven_optimum": optimum,
                "cost_excess_above_proven_optimum": excess,
                "excess_percent": 100 * excess / abs(optimum)
                if optimum is not None and optimum != 0
                else None,
                "bound_inconsistency": bound > incumbent + 1e-6,
            }
        )
    return output
