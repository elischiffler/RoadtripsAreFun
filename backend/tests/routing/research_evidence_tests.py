"""Fixtures test capture integrity; no test observations enter an empirical study."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.agent.persona import ATTRIBUTE_KEYS
from app.research import evidence, worker
from app.research.design import Design, plan
from app.research.metrics import observation
from app.routing.run_metrics import fingerprint


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
            "source_provenance": [
                {
                    "dataset": "Roadtrips active catalog",
                    "generation": "unit-fixture-not-empirical-data",
                }
            ],
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
        {"explanation": {"candidates": candidates, "baseline_seconds": 1000}}, case
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
                    "baseline_seconds": 1000,
                }
            },
            case,
        )


def test_configuration_errors_pause_instead_of_consuming_the_entire_study():
    assert worker.infrastructure_failure({"error": {"causes": [{"provider_code": "BAD_REQUEST"}]}})
    assert not worker.infrastructure_failure({"error": {"http_status": 429}})


def test_unverified_sources_and_invented_utility_are_rejected():
    _, case, frozen = fixture_capture()
    envelope = {"explanation": {"candidates": frozen["candidates"], "baseline_seconds": 1000}}
    envelope["explanation"]["candidates"][0]["source_provenance"] = []
    with pytest.raises(ValueError, match="provenance"):
        evidence.capture(envelope, case)
    envelope["explanation"]["candidates"][0]["source_provenance"] = [
        {"dataset": "Roadtrips active catalog", "generation": "unit-fixture-not-empirical-data"}
    ]
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
    result = observation(envelope, 20)
    assert result["candidate_utility_mean"] == pytest.approx(0.7)
    assert result["utility_gain"] == pytest.approx(0.2)
    envelope["explanation"]["solver"]["status"] = "UNKNOWN"
    result = observation(envelope, 20)
    assert result["candidate_utility_mean"] == pytest.approx(0.7)
    assert result["selected_utility_mean"] is None
    assert result["utility_gain"] is None


def test_research_capture_removes_financial_fields():
    assert evidence.without_costs(
        {"budget": 180, "route": {"cost": 25, "stops": [{"price": 25, "name": "Hotel"}]}}
    ) == {"route": {"stops": [{"name": "Hotel"}]}}


def test_measured_empty_pool_is_preserved_as_empty_not_invented():
    planned, case, _ = fixture_capture()
    frozen = evidence.capture({"explanation": {"candidates": [], "baseline_seconds": 1000}}, case)
    assert frozen["eligible_count"] == 0
    result = worker.solver_trial(case, planned, frozen)
    assert result["solver_status"] == "EMPTY"
    assert result["candidate_utility_mean"] is None


async def test_collection_stops_before_selection_scheduling_hotels_and_itinerary(monkeypatch):
    from types import SimpleNamespace

    from app.research import collect
    from app.routers import algorithm_lab, routing_api
    from app.routing.planners import cp_sat

    _, case, frozen = fixture_capture()
    endpoint = {"coordinates": [34, -118], "timezone": "America/Los_Angeles"}
    monkeypatch.setattr(collect, "resolve_endpoint", AsyncMock(return_value=endpoint))
    initial = SimpleNamespace(duration=1000, model_dump=lambda **kwargs: {"duration": 1000})
    monkeypatch.setattr(collect, "call_route", AsyncMock(return_value=initial))
    plan = SimpleNamespace(queries=[SimpleNamespace(coordinates=[34, -118])])
    monkeypatch.setattr(collect, "make_discovery_plan", lambda *args: plan)
    monkeypatch.setattr(
        collect,
        "TripCalendar",
        lambda *args: SimpleNamespace(eligible=AsyncMock(return_value=True)),
    )
    services = SimpleNamespace(
        timezone_at=None,
        cp_sat_candidates=AsyncMock(
            return_value=SimpleNamespace(candidates=frozen["candidates"], explanation={})
        ),
    )
    monkeypatch.setattr(collect, "_build_services", lambda: services)
    checked = AsyncMock(return_value=frozen["candidates"])
    monkeypatch.setattr(collect.CPSatPlanner, "_verify_detours", checked)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Research must not select, schedule hotels, plan final routes, or build itineraries during capture"
        )

    monkeypatch.setattr(cp_sat.CPSatPlanner, "plan", forbidden)
    monkeypatch.setattr(cp_sat, "select_attractions", forbidden)
    monkeypatch.setattr(cp_sat, "schedule_cp_sat_route", forbidden)
    monkeypatch.setattr(algorithm_lab, "execute_run", forbidden)
    monkeypatch.setattr(algorithm_lab, "build_itinerary", forbidden)
    monkeypatch.setattr(routing_api, "plan_final_route", forbidden)
    result = await collect.collect_inputs(case)
    assert result["error"] is None
    checked.assert_awaited_once_with(initial, frozen["candidates"], services)
    captured = evidence.capture(result, case)
    assert captured["eligible_count"] == 3
    assert "route" not in result and "itinerary" not in result
    assert "budget" not in str(result) and "hotel" not in str(result)
