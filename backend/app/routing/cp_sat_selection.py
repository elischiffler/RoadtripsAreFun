"""Choose attractions by match quality, route spacing, and measured detour time."""

import math
from typing import Any

from ortools.sat.python import cp_model

from app.agent.progress import emit
from app.routing.base import PlanningError
from app.routing.discovery import SelectedAttraction
from app.routing.explanation import record_explanation

MIN_UTILITY = 0.60
MAX_CANDIDATES = 60
UTILITY_SCALE = 1_000_000
MAX_AVERAGE_QUALITY_LOSS = 0.10
TIME_LIMIT_SECONDS = 5.0


def valid_coordinates(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(c, (float, int)) and math.isfinite(c) for c in value)
        and -90 <= value[0] <= 90
        and -180 <= value[1] <= 180
    )


def _prepare(candidates, baseline_seconds):
    """Filter invalid, duplicate, and low-match records; retain exclusion reasons."""
    eligible = []
    explanations = []
    seen = set()
    for candidate in candidates:
        candidate = candidate if isinstance(candidate, dict) else {}
        provider_id = candidate.get("provider_id")
        utility = candidate.get("utility")
        progress = candidate.get("route_progress_seconds")
        detour = candidate.get("detour_seconds")
        valid = (
            isinstance(provider_id, str)
            and bool(provider_id)
            and isinstance(candidate.get("name"), str)
            and bool(candidate["name"])
            and valid_coordinates(candidate.get("coordinates"))
            and all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (utility, progress, detour)
            )
            and 0 <= utility <= 1
            and 0 <= progress <= baseline_seconds
            and detour >= 0
        )
        explanation = {
            **candidate,
            "selected": False,
            "objective_coefficient": None,
            "reason": "invalid_candidate",
        }
        explanations.append(explanation)
        if not valid:
            continue
        if provider_id in seen:
            explanation["reason"] = "duplicate_provider_id"
            continue
        seen.add(provider_id)
        if utility < MIN_UTILITY:
            explanation["reason"] = "below_utility_threshold"
            continue
        explanation["reason"] = "eligible_not_selected"
        eligible.append((candidate, explanation))
    eligible.sort(key=lambda entry: (entry[0]["route_progress_seconds"], entry[0]["provider_id"]))
    return eligible, explanations


def _build_model(eligible, requested, baseline_seconds):
    """Select the available count within the quality bound, then minimize route cost."""
    candidates = [candidate for candidate, _ in eligible]
    model = cp_model.CpModel()
    stop_count = min(requested, len(candidates))
    selected_vars = [model.NewBoolVar(f"candidate_{i}") for i in range(len(candidates))]
    model.Add(sum(selected_vars) == stop_count).WithName("exact_available_stop_count")

    # Floor candidate scores and ceil the required total so rounding cannot weaken the bound.
    scaled_utilities = [
        math.floor(candidate["utility"] * UTILITY_SCALE) for candidate in candidates
    ]
    best_utility_total = math.fsum(
        sorted((candidate["utility"] for candidate in candidates), reverse=True)[:stop_count]
    )
    minimum_utility_total = math.ceil(
        (best_utility_total - MAX_AVERAGE_QUALITY_LOSS * stop_count) * UTILITY_SCALE - 1e-9
    )
    model.Add(
        sum(utility * selected for utility, selected in zip(scaled_utilities, selected_vars))
        >= minimum_utility_total
    ).WithName("ten_percentage_point_quality_bound")

    # Forward edges form a path in baseline route order; no cycle constraints are needed.
    positions = (
        [0]
        + [round(candidate["route_progress_seconds"]) for candidate in candidates]
        + [round(baseline_seconds)]
    )
    destination = len(positions) - 1
    gap_count = stop_count + 1
    edges = {}
    spacing_costs = []
    for start in range(destination):
        for end in range(start + 1, destination + 1):
            edge = model.NewBoolVar(f"gap_{start}_{end}")
            edges[start, end] = edge
            gap_seconds = positions[end] - positions[start]
            # Scale by K+1 to encode abs(gap - baseline/(K+1)) without fractions.
            deviation = abs(gap_seconds * gap_count - positions[-1])
            spacing_costs.append(deviation * edge)

    # Include the endpoint gaps; selected places have one incoming and one outgoing edge.
    model.Add(sum(edges[0, end] for end in range(1, destination + 1)) == 1)
    model.Add(sum(edges[start, destination] for start in range(destination)) == 1)
    for node, selected in enumerate(selected_vars, start=1):
        model.Add(sum(edges[start, node] for start in range(node)) == selected)
        model.Add(sum(edges[node, end] for end in range(node + 1, destination + 1)) == selected)

    detour_costs = [
        round(candidate["detour_seconds"]) * gap_count * selected
        for candidate, selected in zip(candidates, selected_vars)
    ]
    model.Minimize(sum(spacing_costs + detour_costs))
    return model, selected_vars, best_utility_total / stop_count, stop_count


def select_attractions(candidates, query_points, num_stops, baseline_seconds):
    """Return chosen records in route order; query points are used only for diagnostics."""
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise PlanningError("Verified attraction candidate limit exceeded", 502)
    summary = {
        "status": "NOT_RUN",
        "objective_value": None,
        "best_bound": None,
        "wall_time_seconds": None,
        "time_limit_seconds": TIME_LIMIT_SECONDS,
        "requested_stops": num_stops,
        "eligible_count": 0,
        "selected_count": 0,
        "utility_threshold": MIN_UTILITY,
        "utility_scale": UTILITY_SCALE,
        "objective": "minimize_all_gap_deviation_plus_solo_detour_seconds",
        "objective_direction": "minimize",
        "maximum_average_quality_loss": MAX_AVERAGE_QUALITY_LOSS,
        "baseline_seconds": baseline_seconds,
    }
    record_explanation(solver=summary, query_points=query_points)
    if num_stops <= 0:
        record_explanation(candidates=[])
        return []
    eligible, explanations = _prepare(candidates, baseline_seconds)
    record_explanation(candidates=explanations)
    summary["eligible_count"] = len(eligible)
    emit(
        "route.model",
        candidates=len(candidates),
        eligible=len(eligible),
        requestedStops=num_stops,
        threshold=MIN_UTILITY,
        sections=len({candidate.get("section_id") for candidate, _ in eligible}),
    )
    if not eligible:
        summary.update(status="EMPTY", selected_count=0)
        return []
    model, selected_vars, best_average, stop_count = _build_model(
        eligible, num_stops, baseline_seconds
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TIME_LIMIT_SECONDS
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    summary["status"] = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, "UNKNOWN")
    if hasattr(solver, "WallTime"):
        summary["wall_time_seconds"] = solver.WallTime()
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise PlanningError(
            "CP-SAT found no feasible selection"
            if status == cp_model.INFEASIBLE
            else "CP-SAT selection timed out without a feasible solution",
            503,
        )
    selected = []
    for selected_var, (candidate, explanation) in zip(selected_vars, eligible):
        if solver.Value(selected_var):
            explanation.update(selected=True, reason="selected")
            selected.append(SelectedAttraction(candidate["route_progress_seconds"], candidate))
    # Convert the solver's scaled cost back to seconds for displayed metrics.
    gap_count = stop_count + 1
    summary["objective_integer_scale"] = gap_count
    if hasattr(solver, "ObjectiveValue"):
        summary.update(
            objective_value=solver.ObjectiveValue() / gap_count,
            best_bound=solver.BestObjectiveBound() / gap_count,
        )
    positions = [0] + [item.route_progress_seconds for item in selected] + [baseline_seconds]
    ideal_gap = baseline_seconds / gap_count
    average_match = (
        sum(item.candidate["utility"] for item in selected) / len(selected) if selected else None
    )
    summary.update(
        selected_count=len(selected),
        best_average_match=best_average,
        average_match=average_match,
        quality_loss=best_average - average_match if average_match is not None else None,
        spacing_deviation_seconds=sum(
            abs(end - start - ideal_gap) for start, end in zip(positions, positions[1:])
        ),
        estimated_detour_seconds=sum(item.candidate["detour_seconds"] for item in selected),
    )
    emit(
        "route.solution",
        selected=len(selected),
        solverStatus=summary["status"],
        eligible=len(eligible),
        objective=summary["objective_value"],
    )
    return selected
