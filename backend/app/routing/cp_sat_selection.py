"""Select K verified places within the accepted match bound, minimizing seconds."""

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
    eligible, explanations, seen = [], [], set()
    for candidate in candidates:
        candidate = candidate if isinstance(candidate, dict) else {}
        provider_id, utility = candidate.get("provider_id"), candidate.get("utility")
        progress, detour = candidate.get("route_progress_seconds"), candidate.get("detour_seconds")
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
        item = {
            **candidate,
            "selected": False,
            "objective_coefficient": None,
            "reason": "invalid_candidate",
        }
        explanations.append(item)
        if not valid:
            continue
        if provider_id in seen:
            item["reason"] = "duplicate_provider_id"
            continue
        seen.add(provider_id)
        if utility < MIN_UTILITY:
            item["reason"] = "below_utility_threshold"
            continue
        item["reason"] = "eligible_not_selected"
        eligible.append((candidate, item))
    eligible.sort(key=lambda pair: (pair[0]["route_progress_seconds"], pair[0]["provider_id"]))
    return eligible, explanations


def _build_model(eligible, requested, baseline_seconds):
    model = cp_model.CpModel()
    count = min(requested, len(eligible))
    variables = [model.NewBoolVar(f"candidate_{i}") for i in range(len(eligible))]
    model.Add(sum(variables) == count).WithName("exact_available_stop_count")
    utilities = [math.floor(pair[0]["utility"] * UTILITY_SCALE) for pair in eligible]
    best = math.fsum(sorted((pair[0]["utility"] for pair in eligible), reverse=True)[:count])
    model.Add(
        sum(value * variable for value, variable in zip(utilities, variables))
        >= math.ceil((best - 0.10 * count) * UTILITY_SCALE - 1e-9)
    ).WithName("ten_percentage_point_quality_bound")
    # A source-to-sink path over the ordered selected nodes makes every gap,
    # including both endpoints, explicit. Unselected nodes have no incident edges.
    # Costs use (K+1)*seconds, avoiding rounded ideal-gap divisions.
    positions = (
        [0]
        + [round(pair[0]["route_progress_seconds"]) for pair in eligible]
        + [round(baseline_seconds)]
    )
    last = len(positions) - 1
    edges, costs = {}, []
    for i in range(last):
        for j in range(i + 1, last + 1):
            edge = model.NewBoolVar(f"gap_{i}_{j}")
            edges[i, j] = edge
            costs.append(abs((positions[j] - positions[i]) * (count + 1) - positions[-1]) * edge)
    model.Add(sum(edges[0, j] for j in range(1, last + 1)) == 1)
    model.Add(sum(edges[i, last] for i in range(last)) == 1)
    for i, variable in enumerate(variables, start=1):
        model.Add(sum(edges[j, i] for j in range(i)) == variable)
        model.Add(sum(edges[i, j] for j in range(i + 1, last + 1)) == variable)
    costs.extend(
        round(pair[0]["detour_seconds"]) * (count + 1) * variable
        for pair, variable in zip(eligible, variables)
    )
    model.Minimize(sum(costs))
    return model, variables, best / count, count


def select_attractions(candidates, query_points, num_stops, baseline_seconds):
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
        "maximum_average_quality_loss": 0.10,
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
        sections=len({pair[0].get("section_id") for pair in eligible}),
    )
    if not eligible:
        summary.update(status="EMPTY", selected_count=0)
        return []
    model, variables, best_average, count = _build_model(eligible, num_stops, baseline_seconds)
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
    for variable, (candidate, explanation) in zip(variables, eligible):
        if solver.Value(variable):
            explanation.update(selected=True, reason="selected")
            selected.append(SelectedAttraction(candidate["route_progress_seconds"], candidate))
    # Keep units honest: the integer objective is (K+1)*seconds, never surplus.
    summary["objective_integer_scale"] = count + 1
    if hasattr(solver, "ObjectiveValue"):
        summary.update(
            objective_value=solver.ObjectiveValue() / (count + 1),
            best_bound=solver.BestObjectiveBound() / (count + 1),
        )
    positions = [0] + [item.route_progress_seconds for item in selected] + [baseline_seconds]
    ideal = baseline_seconds / (count + 1)
    average = (
        sum(item.candidate["utility"] for item in selected) / len(selected) if selected else None
    )
    summary.update(
        selected_count=len(selected),
        best_average_match=best_average,
        average_match=average,
        quality_loss=best_average - average if average is not None else None,
        spacing_deviation_seconds=sum(abs(b - a - ideal) for a, b in zip(positions, positions[1:])),
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
