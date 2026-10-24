"""Fixtures test capture integrity; no test observations enter an empirical study."""

from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent.persona import ATTRIBUTE_KEYS
from app.research import evidence, worker
from app.research.design import Design, plan
from app.research.metrics import observation
from app.routing.run_metrics import fingerprint, trip_evaluation


def fixture_capture():
    planned = plan(
        Design(trips=["short-1d"], personas=["nature"], stops_per_day=[1], solver_repeats=1)
    )
    case = next(
        row for row in planned["cases"] if row["track"] == "solver" and row["variant"] == "baseline"
    ) | {"id": 1}
    candidates = [
        {
            "provider_id": f"test-{i}",
            "name": f"Test fixture {i}",
            "coordinates": [34, -118],
            "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, utility),
            "utility": utility,
            "source_generation": "unit-fixture-not-empirical-data",
            "source_provenance": [{"dataset": "unit test fixture"}],
            "provenance": {
                "ratings_created_at": "2026-10-24T00:00:00Z",
                "ratings_provider": "unit-fixture/test-model",
            },
            "route_progress_seconds": i * 200,
            "detour_seconds": 10,
        }
        for i, utility in enumerate([0.4, 0.6, 0.8], 1)
    ]
    frozen = evidence.capture(
        {"explanation": {"candidates": candidates, "solver": {"baseline_seconds": 1000}}}, case
    )
    return planned, case, frozen


def test_capture_preserves_exact_roads_ratings_and_hash_across_solver_seeds():
    planned, case, frozen = fixture_capture()
    before = deepcopy(frozen)
    for seed in (1, 2):
        result = worker.solver_trial(case | {"repeat": seed}, planned, frozen)
        assert result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
        assert result["candidate_count"] == 3
        assert result["candidate_utility_mean"] == pytest.approx(0.6)
        assert result["selected_utility_mean"] == pytest.approx(0.8)
        assert result["utility_gain"] == pytest.approx(0.2)
        assert result["dataset_hash"] == frozen["hash"]
        assert result["solver"]["configuration"]["candidate_limit"] == 60
    assert frozen == before


def test_tampering_or_wrong_persona_cannot_be_used_as_real_evidence():
    planned, case, frozen = fixture_capture()
    frozen["candidates"][0]["detour_seconds"] += 1
    assert worker.solver_trial(case, planned, frozen)["outcome"] == "blocked"
    frozen["hash"] = fingerprint({k: v for k, v in frozen.items() if k != "hash"})
    assert (
        worker.solver_trial(case | {"persona": "entertainment"}, planned, frozen)["outcome"]
        == "blocked"
    )


def test_missing_persistent_model_provenance_is_rejected():
    _, case, frozen = fixture_capture()
    frozen["candidates"][0]["provenance"] = {}
    with pytest.raises(ValueError, match="persisted traits"):
        evidence.capture(
            {
                "explanation": {
                    "candidates": frozen["candidates"],
                    "solver": {"baseline_seconds": 1000},
                }
            },
            case,
        )


def test_configuration_errors_pause_instead_of_consuming_the_entire_study():
    assert worker.infrastructure_failure({"error": {"causes": [{"provider_code": "BAD_REQUEST"}]}})
    assert not worker.infrastructure_failure({"error": {"http_status": 429}})


def test_unverified_sources_and_invented_utility_are_rejected():
    _, case, frozen = fixture_capture()
    envelope = {
        "explanation": {"candidates": frozen["candidates"], "solver": {"baseline_seconds": 1000}}
    }
    envelope["explanation"]["candidates"][0]["source_provenance"] = []
    with pytest.raises(ValueError, match="provenance"):
        evidence.capture(envelope, case)
    envelope["explanation"]["candidates"][0]["source_provenance"] = [{"dataset": "test"}]
    envelope["explanation"]["candidates"][0]["utility"] = 0.99
    with pytest.raises(ValueError, match="utility"):
        evidence.capture(envelope, case)


def test_utility_comparison_excludes_ineligible_and_does_not_fabricate_failed_selection():
    envelope = {
        "explanation": {
            "solver": {"status": "OPTIMAL", "requested_stops": 1, "selected_count": 1},
            "candidates": [
                {"utility": 0.9, "selected": True},
                {"utility": 0.5, "reason": "eligible_not_selected"},
                {"utility": 1, "reason": "unknown_source_visit_calendar"},
            ],
        }
    }
    result = observation(envelope, 20, solver_only=True)
    assert result["candidate_utility_mean"] == pytest.approx(0.7)
    assert result["utility_gain"] == pytest.approx(0.2)
    envelope["explanation"]["solver"]["status"] = "UNKNOWN"
    result = observation(envelope, 20, solver_only=True)
    assert result["candidate_utility_mean"] == pytest.approx(0.7)
    assert result["selected_utility_mean"] is None
    assert result["utility_gain"] is None


def test_research_omits_financial_fields_while_normal_trip_metrics_retain_them():
    envelope = {
        "mode": "live",
        "input_snapshot": {"budget": 180},
        "explanation": {"candidates": []},
        "route": None,
    }
    assert "hotel_costs" in trip_evaluation(envelope)
    assert "hotel_costs" not in trip_evaluation(envelope, include_costs=False)
    assert evidence.without_costs(
        {"budget": 180, "route": {"cost": 25, "stops": [{"price": 25, "name": "Hotel"}]}}
    ) == {"route": {"stops": [{"name": "Hotel"}]}}


async def test_live_persistence_normalizes_uuid_and_never_writes_financial_fields(monkeypatch):
    planned, case, _ = fixture_capture()
    request = evidence.lab.LabRun(
        preset_id=case["preset_id"], inputs=case["inputs"] | {"budget": 180}
    )
    writes = []
    monkeypatch.setattr(evidence.lab.lab_runs, "begin", lambda *args: writes.append(args))
    monkeypatch.setattr(evidence.lab.lab_runs, "finish", lambda *args: writes.append(args))
    monkeypatch.setattr(
        evidence.lab,
        "execute_run",
        AsyncMock(
            return_value={
                "mode": "live",
                "input_snapshot": {"budget": 180, "num_stops": 1},
                "route": None,
                "itinerary": None,
                "error": {"code": "provider"},
                "explanation": {"candidates": [], "solver": None},
            }
        ),
    )
    run_id = uuid4()
    result = await evidence.recorded_run(request, "unit-owner", run_id)
    assert writes[0][-1] == str(run_id)
    assert writes[1][1] == str(run_id)
    assert "budget" not in str(writes)
    assert "hotel_costs" not in str(writes)
    assert "lock" not in writes[1][3]["provider_measurements"]
    assert result["run_record"]["saved"] is True
