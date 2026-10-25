"""Real, immutable research inputs and cost-free live evidence."""

from copy import deepcopy

from app.research import store
from app.routing.cp_sat_selection import SelectionConfig, _prepare
from app.routing.profiles import AttributeRatings, crossmatch
from app.routing.run_metrics import fingerprint


def scenario_key(case):
    return f"{case['trip']}:{case['persona']}:{case['stops_per_day']}"


def without_costs(value):
    """Research never persists financial inputs, quotes or budget measurements."""
    if isinstance(value, list):
        return [without_costs(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: without_costs(item)
        for key, item in value.items()
        if not any(word in key.lower() for word in ("budget", "price", "cost", "quote", "currency"))
        and key not in {"room_offers", "within_nightly_room_target", "feasibility_reason"}
    }


def capture(envelope, case):
    """Freeze real pre-selection inputs; never construct replacement attractions."""
    explanation = envelope.get("explanation") or {}
    baseline = explanation.get("baseline_seconds")
    candidates = deepcopy(explanation.get("candidates") or [])
    if baseline is None:
        return None
    for row in candidates:
        generations = {
            item["generation"]
            for item in row.get("source_provenance", [])
            if item.get("dataset") == "Roadtrips active catalog"
            and isinstance(item.get("generation"), str)
            and item["generation"]
        }
        if len(generations) != 1:
            raise ValueError("Research requires catalog-backed candidate provenance")
        generation = next(iter(generations))
        if row.get("source_generation", generation) != generation:
            raise ValueError("Candidate generation conflicts with its source provenance")
        row["source_generation"] = generation
        provenance = row.get("provenance") or {}
        if not provenance.get("ratings_created_at") or "/" not in (
            provenance.get("ratings_provider") or ""
        ):
            raise ValueError(
                "Research requires persisted traits with their upstream model identity"
            )
        ratings = AttributeRatings.model_validate(row["attribute_ratings"])
        score = crossmatch(case["inputs"]["persona_weights"], ratings.model_dump()).utility
        if abs(score - row["utility"]) > 1e-9:
            raise ValueError("Captured utility does not match the frozen persona and traits")
        for key in ("selected", "reason", "objective_coefficient"):
            row.pop(key, None)
    eligible, _ = _prepare(candidates, baseline, SelectionConfig(candidate_limit=None))
    # Retain every supplied input, including exclusions, for denominator auditing.
    result = {
        "evidence": "real_catalog_and_measured_roads",
        "scenario": scenario_key(case),
        "capture_case_id": case["id"],
        "attempt_id": envelope.get("attempt_id"),
        "captured_at": store.now(),
        "baseline_seconds": baseline,
        "direct_route": envelope.get("direct_route"),
        "inputs": case["inputs"],
        "candidates": candidates,
        "eligible_count": len(eligible),
        "query_points": explanation.get("query_points") or [],
        "discovery": explanation.get("discovery") or {},
    }
    result["hash"] = fingerprint(result)
    return result


def validate_capture(snapshot, case):
    if not snapshot or snapshot.get("evidence") != "real_catalog_and_measured_roads":
        raise ValueError("No measured real candidate pool was captured for this scenario")
    if snapshot["hash"] != fingerprint({k: v for k, v in snapshot.items() if k != "hash"}):
        raise ValueError("Frozen candidate capture hash mismatch")
    if snapshot["scenario"] != scenario_key(case) or snapshot["inputs"] != case["inputs"]:
        raise ValueError("Frozen capture belongs to different scenario inputs")
    return snapshot
