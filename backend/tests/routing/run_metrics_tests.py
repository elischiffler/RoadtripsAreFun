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
    assert summary["quality_percent"] is None
    assert summary["selection_cost_excess_seconds"]["mean"] == 0
    assert summary["feasibility_rate"] is None


def test_quality_needs_matching_candidates_and_proven_optimum():
    baseline = metric()
    baseline["metric_version"] = "selection-surplus-v2"
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

    async def fail(*args, **kwargs):
        raise ValueError("offline")

    monkeypatch.setattr(mapbox, "http_get", fail)
    with measuring() as data:
        with pytest.raises(ValueError):
            await mapbox.call_route(37, -122, 36, -121)
    assert data["calls"] == {"mapbox": 1}


def test_lab_storage_respects_database_write_gate(monkeypatch):
    from app.crud import lab_runs

    monkeypatch.setattr(lab_runs.settings, "NEON_READ_ONLY", True)
    with pytest.raises(RuntimeError, match="writes are disabled"):
        lab_runs.begin("owner", {"mode": "replay", "preset_id": "test"})


def live_trip():
    value = envelope()
    value.update(
        mode="live",
        direct_route={"distance": 1000, "duration": 100},
        itinerary=[{"date": "2026-10-06"}, {"date": "2026-10-07"}],
        stages=[
            {"name": "reroute", "status": "complete"},
            {"name": "itinerary", "status": "complete"},
        ],
        route={
            "distance": 1200,
            "duration": 150,
            "warnings": ["Late arrival"],
            "stops": [
                {
                    "type": "stop",
                    "provider_id": "a",
                    "arrival_time": "2026-10-06T10:00:00-07:00",
                    "departure_time": "2026-10-06T12:00:00-07:00",
                    "deadline": "2026-10-06T13:00:00-07:00",
                },
                {
                    "type": "hotel",
                    "provider_id": "h",
                    "room_offers": [{"price": 120}, {"price": 80}],
                    "arrival_time": "2026-10-06T18:00:00-07:00",
                    "deadline": "2026-10-06T20:00:00-07:00",
                    "late_check_in_notice": "Confirm check-in",
                },
                {
                    "type": "hotel",
                    "provider_id": "h2",
                    "room_offers": [{"price": 150}, {"price": 90}],
                    "arrival_time": "2026-10-07T18:00:00-07:00",
                    "deadline": "2026-10-07T20:00:00-07:00",
                },
                {
                    "type": "end",
                    "arrival_time": "2026-10-08T19:00:00-06:00",
                    "deadline": "2026-10-08T21:00:00-06:00",
                    "timezone": "America/Denver",
                },
            ],
        },
    )
    value["input_snapshot"].update(
        num_stops=2, budget=100, hotel_rooms=[{}, {}], start_date="2026-10-06T09:00:00-07:00"
    )
    return value


def test_trip_evaluation_arithmetic_and_room_nights():
    result = metric(live_trip())["trip_evaluation"]
    assert result["driving"]["extra_distance_meters"] == 200
    assert result["driving"]["extra_duration_percent"] == 50
    assert result["stop_fulfillment"]["ratio"] == 0.5
    assert result["stop_fulfillment"]["delivered"] == 1
    assert result["hotel_costs"]["quoted_total_usd"] == 440
    assert result["hotel_costs"]["room_night_count"] == 4
    assert result["hotel_costs"]["over_target_room_nights"] == 2
    assert result["hotel_costs"]["above_target_total_usd"] == 70
    assert result["schedule"]["elapsed_trip_seconds"] == 57 * 3600
    assert result["schedule_compliance"]["min_deadline_slack_seconds"] == 3600
    assert result["schedule_compliance"]["violation_count"] == 0
    assert result["warnings"] == ["Late arrival", "Confirm check-in"]


def test_missing_quotes_zero_baselines_and_signed_detours():
    value = live_trip()
    value["direct_route"] = {"distance": 0, "duration": 200}
    value["route"]["stops"][1]["room_offers"].pop()
    result = metric(value)["trip_evaluation"]
    assert result["driving"]["extra_distance_percent"] is None
    assert result["driving"]["extra_duration_seconds"] == -50
    assert result["hotel_costs"]["quotes_complete"] is False
    assert result["hotel_costs"]["quoted_total_usd"] is None
    value.pop("direct_route")
    assert metric(value)["trip_evaluation"]["driving"]["assessment_reason"] == "baseline_incomplete"


def test_partial_failure_keeps_route_measurements_and_missing_deadline_unassessed():
    value = live_trip()
    value.update(
        error={"code": "provider_or_planning_failure"},
        itinerary=None,
        stages=[{"name": "itinerary", "status": "failed"}],
    )
    value["route"]["stops"][0].pop("deadline")
    result = metric(value)["trip_evaluation"]
    assert result["completed"] is False
    assert result["first_failed_stage"] == "itinerary"
    assert result["hotel_costs"]["quoted_total_usd"] == 440
    assert result["schedule"]["itinerary_days"] is None
    assert result["schedule_compliance"]["violation_count"] is None
    assert result["schedule_compliance"]["assessed_stops"] == 3


def test_no_hotel_trip_and_dst_elapsed_time():
    value = live_trip()
    value["route"]["stops"] = [
        {
            "type": "end",
            "arrival_time": "2026-11-01T02:30:00-08:00",
            "deadline": "2026-11-01T02:00:00-08:00",
            "timezone": "America/Los_Angeles",
        }
    ]
    value["input_snapshot"]["start_date"] = "2026-11-01T00:30:00-07:00"
    result = metric(value)["trip_evaluation"]
    assert result["hotel_costs"]["quoted_total_usd"] == 0
    assert result["hotel_costs"]["room_night_count"] == 0
    assert result["schedule"]["elapsed_trip_seconds"] == 3 * 3600
    assert result["schedule_compliance"]["violation_count"] == 1
    assert result["schedule_compliance"]["min_deadline_slack_seconds"] == -1800


def test_page_cohorts_separate_versions_and_exclude_missing_measurements():
    current = metric(live_trip())
    old = copy.deepcopy(current)
    old["metric_version"] = "selection-surplus-v1"
    old.pop("trip_evaluation")
    groups = aggregate_runs(
        [
            {"status": "completed", "metrics": current},
            {"status": "failed", "metrics": current},
            {"status": "completed", "metrics": old},
        ]
    )
    assert len(groups) == 2
    assert groups[0]["completion_rate"] == 0.5
    assert groups[0]["trip_evaluation"]["quoted_hotel_total_usd"]["count"] == 2
    assert groups[1]["trip_evaluation"]["quoted_hotel_total_usd"] is None


def test_minimized_cost_excess_supports_zero_optima_without_inverting_quality():
    baseline = metric()
    baseline["objective_score"] = 0
    worse = copy.deepcopy(baseline)
    worse.update(solver_status="FEASIBLE", objective_score=20)
    summary = aggregate_runs([{"metrics": baseline}, {"metrics": worse}])[0]
    assert summary["objective_direction"] == "minimize"
    assert summary["quality_percent"] is None
    assert summary["selection_cost_gap_percent"] is None
    assert summary["selection_cost_excess_seconds"]["max"] == 20
    baseline["objective_score"] = 10
    summary = aggregate_runs([{"metrics": baseline}, {"metrics": worse}])[0]
    assert summary["selection_cost_gap_percent"]["max"] == 100
