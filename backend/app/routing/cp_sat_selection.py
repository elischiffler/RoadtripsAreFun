"""The attraction-subset model: eligibility, Boolean constraints, and exact objective.

Hotels, actual driving durations, and scheduling are separate stages. An optimal
solution here proves only this bounded integer selection problem optimal.
"""

import math
from typing import Any

from geopy.distance import geodesic
from ortools.sat.python import cp_model

from app.routing.base import PlanningError
from app.routing.explanation import record_explanation

MIN_UTILITY = 0.60
MAX_CANDIDATES = 30
UTILITY_SCALE = 1_000_000
TIME_LIMIT_SECONDS = 5.0


def query_count(num_stops: int) -> int:
    return min(30, max(6, 3 * num_stops)) if num_stops else 0


def valid_coordinates(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(c, (float, int)) and math.isfinite(c) for c in value)
        and -90 <= value[0] <= 90
        and -180 <= value[1] <= 180
    )


def _prepare(candidates, points):
    eligible, explanations, seen = [], [], set()
    for candidate in candidates:
        candidate = candidate if isinstance(candidate, dict) else {}
        provider_id = candidate.get("provider_id")
        utility = candidate.get("utility")
        valid = (
            isinstance(provider_id, str)
            and bool(provider_id)
            and isinstance(candidate.get("name"), str)
            and bool(candidate["name"])
            and valid_coordinates(candidate.get("coordinates"))
            and isinstance(utility, (float, int))
            and math.isfinite(utility)
            and 0 <= utility <= 1
        )
        item = {
            "provider_id": provider_id[:180] if isinstance(provider_id, str) else None,
            "name": str(candidate.get("name", "Invalid candidate"))[:180],
            "selected": False,
            "slot": None,
            "objective_coefficient": None,
            "reason": "invalid_candidate",
        }
        explanations.append(item)
        if not valid:
            continue
        item.update(
            coordinates=candidate["coordinates"],
            utility=utility,
            attribute_ratings=candidate.get("attribute_ratings", {}),
            contributions=candidate.get("contributions", []),
            provenance=candidate.get("provenance", {"ratings_source": "unspecified"}),
        )
        if provider_id in seen:
            item["reason"] = "duplicate_provider_id"
            continue
        if utility < MIN_UTILITY:
            item["reason"] = "below_utility_threshold"
            continue
        seen.add(provider_id)
        slot = min(
            range(len(points)),
            key=lambda i: (geodesic(candidate["coordinates"], points[i]).meters, i),
        )
        item.update(slot=slot, reason="eligible_not_selected")
        eligible.append((slot, candidate, item))
    eligible.sort(key=lambda item: (item[0], item[1]["provider_id"]))
    return eligible, explanations


def _build_model(eligible, num_stops):
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"candidate_{i}") for i in range(len(eligible))]
    model.Add(sum(variables) <= num_stops).WithName("requested_stop_cap")
    for slot in sorted({item[0] for item in eligible}):
        model.Add(
            sum(variables[i] for i, item in enumerate(eligible) if item[0] == slot) <= 1
        ).WithName(f"one_attraction_in_slot_{slot}")
    count = len(eligible)
    tie_bound = count * (count + 1)
    coefficients = []
    for i, (_, candidate, explanation) in enumerate(eligible):
        surplus = round((candidate["utility"] - MIN_UTILITY) * UTILITY_SCALE)
        coefficient = surplus * (tie_bound + 1) + count - i
        explanation.update(
            objective_coefficient=coefficient, scaled_surplus=surplus, tie_preference=count - i
        )
        coefficients.append(coefficient)
    model.Maximize(
        sum(coefficient * variable for coefficient, variable in zip(coefficients, variables))
    )
    return model, variables


def select_attractions(candidates, query_points, num_stops):
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
        "objective": "rounded_match_surplus_then_stable_tie_preference",
    }
    record_explanation(solver=summary, query_points=query_points)
    if not query_points or num_stops <= 0:
        record_explanation(candidates=[])
        return []
    eligible, explanations = _prepare(candidates, query_points)
    record_explanation(candidates=explanations)
    summary["eligible_count"] = len(eligible)
    if not eligible:
        return []
    model, variables = _build_model(eligible, num_stops)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TIME_LIMIT_SECONDS
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    # Narrow fakes used by existing planner tests need only Solve/Value.
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
            else "CP-SAT selection timed out",
            503,
        )
    if hasattr(solver, "ObjectiveValue"):
        summary.update(
            objective_value=solver.ObjectiveValue(), best_bound=solver.BestObjectiveBound()
        )
    selected = []
    for variable, (slot, candidate, explanation) in zip(variables, eligible):
        if solver.Value(variable):
            explanation.update(selected=True, reason="selected")
            selected.append((slot, candidate))
    summary["selected_count"] = len(selected)
    return selected
