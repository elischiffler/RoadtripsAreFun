import asyncio
import copy

import pytest

from app.routing.run_metrics import aggregate_runs, compile_metrics, increment, measuring, timed


def envelope():
    return {
        "mode": "replay",
        "input_snapshot": {"effective_weights": {"nature": 1}},
        "route": None,
        "error": None,
        "explanation": {
            "solver": {"status": "OPTIMAL", "objective_value": 100},
            "candidates": [
                {
                    "provider_id": "a",
                    "selected": True,
                    "utility": 0.8,
                    "provenance": {"verified_at": "today"},
                }
            ],
        },
    }


def metric(value=None):
    with measuring() as telemetry:
        return compile_metrics(value or envelope(), telemetry, 10)


def test_stable_output_and_comparison_ignore_provider_timestamps():
    first = metric()
    changed = envelope()
    changed["explanation"]["candidates"][0]["provenance"]["verified_at"] = "tomorrow"
    second = metric(changed)
    assert first["comparison_key"] == second["comparison_key"]
    assert first["output_hash"] == second["output_hash"]
    assert first["full_trip_feasibility"] is None
    assert first["external_calls"]["mapbox"] == 0
    summary = aggregate_runs([{"metrics": first}, {"metrics": second}])[0]
    assert summary["deterministic_observed"] is True
    assert summary["quality_percent"]["mean"] == 100
    assert summary["feasibility_rate"] is None


def test_quality_needs_matching_candidates_and_proven_optimum():
    baseline = metric()
    approximate = copy.deepcopy(baseline)
    approximate.update(algorithm="future", solver_status="FEASIBLE", objective_score=80)
    summary = aggregate_runs([{"metrics": baseline}, {"metrics": approximate}])[0]
    assert summary["quality_percent"]["min"] == 80
    approximate["comparison_key"] = "different-candidates"
    summary = aggregate_runs([{"metrics": baseline}, {"metrics": approximate}])[0]
    assert summary["quality_percent"]["count"] == 1
    baseline["solver_status"] = "FEASIBLE"
    assert aggregate_runs([{"metrics": baseline}])[0]["quality_percent"] is None
    baseline.update(solver_status="OPTIMAL", objective_score=0)
    assert aggregate_runs([{"metrics": baseline}])[0]["quality_percent"] is None


def test_repeated_inputs_capture_variation_and_failures_without_false_determinism():
    baseline = metric()
    changed = copy.deepcopy(baseline)
    changed.update(output_hash="different", comparison_key="different-model")
    summary = aggregate_runs([{"metrics": baseline}, {"metrics": changed}])[0]
    assert summary["deterministic_observed"] is False
    assert aggregate_runs([{"metrics": baseline}])[0]["deterministic_observed"] is None
    assert aggregate_runs([{"metrics": None}]) == []


def test_request_context_isolated_and_propagates_to_worker_threads():
    async def task():
        with measuring() as data:
            with timed("validation"):
                await asyncio.to_thread(increment, "mapbox")
            return data

    first = asyncio.run(task())
    second = asyncio.run(task())
    assert first["calls"] == second["calls"] == {"mapbox": 1}
    assert first["durations"]["validation"] >= 0
    increment("mapbox")
    assert first["calls"] == {"mapbox": 1}


def test_nightly_target_feasibility_does_not_claim_total_budget_constraint():
    value = envelope()
    value.update(
        mode="live",
        route={
            "stops": [{"type": "hotel", "provider_id": "hotel:1", "room_offers": [{"price": 120}]}]
        },
    )
    value["input_snapshot"]["budget"] = 100
    result = metric(value)
    assert result["feasibility"] is False
    assert result["full_trip_feasibility"] is None
    value["input_snapshot"]["budget"] = 150
    value["route"]["stops"].append({"type": "end", "name": "Destination"})
    assert metric(value)["feasibility"] is True
    value["route"]["stops"][0].pop("room_offers")
    assert metric(value)["feasibility"] is None


async def test_provider_attempt_is_counted_even_when_request_fails(monkeypatch):
    from app.routing.sources import mapbox

    monkeypatch.setattr(mapbox.config, "MAPBOX_API", "fixture-key")

    def fail(*args, **kwargs):
        raise mapbox.requests.RequestException("offline")

    monkeypatch.setattr(mapbox.requests, "get", fail)
    with measuring() as data:
        with pytest.raises(mapbox.requests.RequestException):
            await mapbox.call_route(37, -122, 36, -121)
    assert data["calls"] == {"mapbox": 1}


def test_lab_storage_respects_database_write_gate(monkeypatch):
    from app.crud import lab_runs

    monkeypatch.setattr(lab_runs.settings, "NEON_READ_ONLY", True)
    with pytest.raises(RuntimeError, match="writes are disabled"):
        lab_runs.begin("owner", {"mode": "replay", "preset_id": "test"})
