"""Offline comparators with the same eligible count and exact scaled quality contract."""

import math

from app.routing.base import PlanningError
from app.routing.cp_sat_selection import UTILITY_SCALE, _prepare, quality_bound
from app.routing.discovery import SelectedAttraction
from app.routing.explanation import record_explanation


def comparator(method, candidates, query_points, requested, baseline, config):
    if len(candidates) > config.candidate_limit:
        raise PlanningError("Comparator candidate limit exceeded", 422)
    eligible, explanations = _prepare(candidates, baseline, config)
    count = min(requested, len(eligible))
    ordered = [item for item, _ in eligible]
    _, best_total, required = quality_bound(ordered, count, config)
    top = sorted(ordered, key=lambda item: (-item["utility"], item["provider_id"]))[:count]
    chosen = list(top)
    if method == "spacing_first":
        chosen = []
        for i in range(count):
            target = baseline * (i + 1) / (count + 1)
            chosen.append(
                min(
                    (item for item in ordered if item not in chosen),
                    key=lambda item: (
                        abs(item["route_progress_seconds"] - target),
                        -item["utility"],
                        item["provider_id"],
                    ),
                )
            )
        # Bounded utility repair, deterministic ties. A failed repair remains a failure.
        for _ in range(count):
            if sum(math.floor(item["utility"] * UTILITY_SCALE) for item in chosen) >= required:
                break
            outside = [item for item in top if item not in chosen]
            if not outside:
                break
            replacement = outside[0]
            worst = min(chosen, key=lambda item: (item["utility"], item["provider_id"]))
            chosen[chosen.index(worst)] = replacement
    elif method != "utility_first":
        raise ValueError("unknown offline comparator")
    summary = {
        "status": "NOT_APPLICABLE",
        "method_status": "VALID",
        "objective_value": None,
        "best_bound": None,
        "eligible_count": len(eligible),
        "selected_count": 0,
        "requested_stops": requested,
        "baseline_seconds": baseline,
        "configuration": config.__dict__,
    }
    record_explanation(candidates=explanations, solver=summary, query_points=query_points)
    if sum(math.floor(item["utility"] * UTILITY_SCALE) for item in chosen) < required:
        summary["method_status"] = "QUALITY_CONTRACT_FAILED"
        raise PlanningError("Comparator failed the exact scaled quality bound", 422)
    ids = {item["provider_id"] for item in chosen}
    for item in explanations:
        item.update(
            selected=item.get("provider_id") in ids,
            reason="selected" if item.get("provider_id") in ids else item["reason"],
        )
    chosen.sort(key=lambda item: (item["route_progress_seconds"], item["provider_id"]))
    positions = [0, *(item["route_progress_seconds"] for item in chosen), baseline]
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    summary.update(
        selected_count=count,
        average_match=math.fsum(item["utility"] for item in chosen) / count if count else None,
        best_average_match=best_total / count if count else None,
        baseline_gaps_seconds=gaps,
        maximum_baseline_gap_seconds=max(gaps),
        spacing_deviation_seconds=sum(abs(gap - baseline / (count + 1)) for gap in gaps),
        estimated_detour_seconds=sum(item["detour_seconds"] for item in chosen),
    )
    return [SelectedAttraction(item["route_progress_seconds"], item) for item in chosen]
