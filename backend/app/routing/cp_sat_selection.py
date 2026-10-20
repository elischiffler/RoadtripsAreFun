"""Choose attractions by match quality, route spacing, and measured detour time."""

import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

from ortools.sat.python import cp_model

from app.agent.progress import emit
from app.routing.base import PlanningError
from app.routing.discovery import SelectedAttraction
from app.routing.explanation import record_explanation
from app.routing.profiles import UTILITY_FLOOR, eligible_utility
from app.routing.visit_calendar import calendar_eligible

MAX_CANDIDATES = 60
UTILITY_SCALE = 1_000_000
MAX_AVERAGE_QUALITY_LOSS = 0.10
TIME_LIMIT_SECONDS = 15.0


@dataclass(frozen=True)
class SelectionConfig:
    candidate_limit: int = MAX_CANDIDATES
    utility_threshold: float = UTILITY_FLOOR
    quality_loss: float = MAX_AVERAGE_QUALITY_LOSS
    spacing_weight: float = 1.0
    detour_weight: float = 1.0
    time_limit_seconds: float = TIME_LIMIT_SECONDS
    seed: int = 0
    workers: int = 1

    def __post_init__(self):
        for name, low, high in (
            ("candidate_limit", 1, 100),
            ("seed", 0, 2147483647),
            ("workers", 1, 8),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in {low}..{high}")
        for name, low, high in (
            ("utility_threshold", 0, 1),
            ("quality_loss", 0, 1),
            ("spacing_weight", 0, 16),
            ("detour_weight", 0, 16),
            ("time_limit_seconds", 0.001, 60),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be finite in {low}..{high}")
        # Bound rational scaling and overflow; quarter-step sweeps are exact.
        self.coefficients()

    def coefficients(self):
        weights = [Fraction(str(v)) for v in (self.spacing_weight, self.detour_weight)]
        scale = math.lcm(*(v.denominator for v in weights))
        if scale > 10000:
            raise ValueError("weight precision exceeds four decimal places")
        return *(int(v * scale) for v in weights), scale


PRODUCTION_CONFIG = SelectionConfig()


def valid_coordinates(value: Any) -> bool:
    """Return whether a value is a finite [latitude, longitude] pair within geographic bounds."""
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(
            isinstance(c, (float, int)) and not isinstance(c, bool) and math.isfinite(c)
            for c in value
        )
        and -90 <= value[0] <= 90
        and -180 <= value[1] <= 180
    )


def _prepare(candidates, baseline_seconds, config=PRODUCTION_CONFIG):
    """Prepare eligible attractions for the solver.

    Inputs are candidate records and the baseline drive duration in seconds.
    Returns (candidate, explanation) pairs in route order, plus explanations
    for every input record, including invalid, duplicate, and low-match places.
    """
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
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in (utility, progress, detour)
            )
            and 0 <= utility <= 1
            and 0 <= progress <= baseline_seconds
            and 0 <= detour <= 10_000_000
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
        if not calendar_eligible(candidate):
            explanation["reason"] = "unknown_source_visit_calendar"
            continue
        if not eligible_utility(utility):
            explanation["reason"] = "nonpositive_utility"
            continue
        if utility < config.utility_threshold:
            explanation["reason"] = "below_utility_threshold"
            continue
        explanation["reason"] = "eligible_not_selected"
        eligible.append((candidate, explanation))
    eligible.sort(key=lambda entry: (entry[0]["route_progress_seconds"], entry[0]["provider_id"]))
    return eligible, explanations


def quality_bound(candidates, stop_count, config):
    scaled = [math.floor(candidate["utility"] * UTILITY_SCALE) for candidate in candidates]
    best_total = math.fsum(
        sorted((candidate["utility"] for candidate in candidates), reverse=True)[:stop_count]
    )
    required = math.ceil((best_total - config.quality_loss * stop_count) * UTILITY_SCALE - 1e-9)
    return scaled, best_total, required


def _build_model(eligible, requested, baseline_seconds, config=PRODUCTION_CONFIG):
    """Build the attraction selection model without running the solver.

    Inputs are eligible records in route order, a positive requested count,
    and the baseline drive duration. The records supply utility, route progress,
    and solo detour seconds. Returns the model, selection variables, best
    achievable average match, and available stop count.
    """
    candidates = [candidate for candidate, _ in eligible]
    model = cp_model.CpModel()
    # Stop count
    stop_count = min(requested, len(candidates))
    selected_vars = [model.NewBoolVar(f"candidate_{i}") for i in range(len(candidates))]
    model.Add(sum(selected_vars) == stop_count).WithName("exact_available_stop_count")

    # Match quality: rounding must not weaken the ten-percentage-point bound.
    scaled_utilities, best_utility_total, minimum_utility_total = quality_bound(
        candidates, stop_count, config
    )
    model.Add(
        sum(utility * selected for utility, selected in zip(scaled_utilities, selected_vars))
        >= minimum_utility_total
    ).WithName("average_quality_bound")

    # Route spacing: forward edges form a path without cycles.
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

    # Route cost: spacing deviation plus solo detours, both scaled by K+1.
    detour_costs = [
        round(candidate["detour_seconds"]) * gap_count * selected
        for candidate, selected in zip(candidates, selected_vars)
    ]
    alpha, beta, _ = config.coefficients()
    model.Minimize(alpha * sum(spacing_costs) + beta * sum(detour_costs))
    return model, selected_vars, best_utility_total / stop_count, stop_count


def select_attractions(
    candidates, query_points, num_stops, baseline_seconds, *, config=PRODUCTION_CONFIG
):
    """Filter candidates, build the CP-SAT model, and return selected attractions.

    Inputs are road-checked candidate records, the requested stop count, and
    baseline driving seconds. Query points are retained only for diagnostics.
    Returns SelectedAttraction records in route order and records solver metrics.
    An empty eligible set returns []; an unsuccessful solve raises PlanningError.
    """
    if not isinstance(config, SelectionConfig):
        raise ValueError("A validated SelectionConfig is required")
    if isinstance(num_stops, bool) or not isinstance(num_stops, int) or not 0 <= num_stops <= 30:
        raise ValueError("requested stops must be an integer in 0..30")
    if (
        isinstance(baseline_seconds, bool)
        or not isinstance(baseline_seconds, (int, float))
        or not math.isfinite(baseline_seconds)
        or not 0 <= baseline_seconds <= 10_000_000
    ):
        raise ValueError("baseline_seconds must be finite in 0..10000000")
    if not isinstance(candidates, list) or len(candidates) > config.candidate_limit:
        raise PlanningError("Verified attraction candidate limit exceeded", 502)
    summary = {
        "status": "NOT_RUN",
        "objective_value": None,
        "best_bound": None,
        "wall_time_seconds": None,
        "time_limit_seconds": config.time_limit_seconds,
        "requested_stops": num_stops,
        "eligible_count": 0,
        "selected_count": 0,
        "utility_threshold": config.utility_threshold,
        "utility_threshold_inclusive": config.utility_threshold > UTILITY_FLOOR,
        "eligibility_policy": "positive_utility"
        if config.utility_threshold == UTILITY_FLOOR
        else "positive_utility_with_evaluation_threshold",
        "utility_scale": UTILITY_SCALE,
        "objective": "minimize_all_gap_deviation_plus_solo_detour_seconds",
        "objective_direction": "minimize",
        "maximum_average_quality_loss": config.quality_loss,
        "baseline_seconds": baseline_seconds,
        "configuration": asdict(config),
        "coefficient_conversion": config.coefficients(),
        "stop_reason": None,
    }
    record_explanation(solver=summary, query_points=query_points)
    if num_stops <= 0:
        record_explanation(candidates=[])
        return []
    eligible, explanations = _prepare(candidates, baseline_seconds, config)
    record_explanation(candidates=explanations)
    summary["eligible_count"] = len(eligible)
    emit(
        "route.model",
        candidates=len(candidates),
        eligible=len(eligible),
        requestedStops=num_stops,
        threshold=config.utility_threshold,
        thresholdInclusive=config.utility_threshold > UTILITY_FLOOR,
        sections=len({candidate.get("section_id") for candidate, _ in eligible}),
    )
    if not eligible:
        summary.update(status="EMPTY", selected_count=0)
        return []
    model, selected_vars, best_average, stop_count = _build_model(
        eligible, num_stops, baseline_seconds, config
    )
    scaled, _, required = quality_bound([item for item, _ in eligible], stop_count, config)
    summary.update(
        scaled_quality_required=required,
        best_scaled_utility_total=sum(sorted(scaled, reverse=True)[:stop_count]),
        integer_quality_bound_exceeds_attainable=required
        > sum(sorted(scaled, reverse=True)[:stop_count]),
    )
    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.time_limit_seconds
    solver.parameters.num_search_workers = config.workers
    solver.parameters.random_seed = config.seed
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
    for key, method in (("branches", "NumBranches"), ("conflicts", "NumConflicts")):
        if hasattr(solver, method):
            summary[key] = getattr(solver, method)()
    if status == cp_model.UNKNOWN:
        summary["stop_reason"] = "solver_limit_without_conclusion"
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise PlanningError(
            "CP-SAT found no feasible selection"
            if status == cp_model.INFEASIBLE
            else "CP-SAT model is invalid"
            if status == cp_model.MODEL_INVALID
            else "CP-SAT selection ended without a conclusive solution",
            503,
        )
    # Selected attractions and diagnostics
    selected = []
    for selected_var, (candidate, explanation) in zip(selected_vars, eligible):
        if solver.Value(selected_var):
            explanation.update(selected=True, reason="selected")
            selected.append(SelectedAttraction(candidate["route_progress_seconds"], candidate))
    # Convert the solver's scaled cost back to seconds for displayed metrics.
    gap_count = stop_count + 1
    _, _, weight_scale = config.coefficients()
    summary["objective_integer_scale"] = gap_count * weight_scale
    if hasattr(solver, "ObjectiveValue"):
        summary.update(
            objective_value=solver.ObjectiveValue() / (gap_count * weight_scale),
            best_bound=solver.BestObjectiveBound() / (gap_count * weight_scale),
        )
    positions = [0] + [item.route_progress_seconds for item in selected] + [baseline_seconds]
    ideal_gap = baseline_seconds / gap_count
    average_match = (
        sum(item.candidate["utility"] for item in selected) / len(selected) if selected else None
    )
    summary.update(
        baseline_gaps_seconds=[end - start for start, end in zip(positions, positions[1:])],
        maximum_baseline_gap_seconds=max(
            end - start for start, end in zip(positions, positions[1:])
        ),
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
