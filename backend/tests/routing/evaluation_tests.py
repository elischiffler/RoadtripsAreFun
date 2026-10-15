"""Synthetic contract checks, excluded from real-catalog benchmark claims."""

import copy
import hashlib
import itertools
import json
import socket
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from pydantic import ValidationError

from app.agent.persona import ATTRIBUTE_KEYS
from app.agent.trip_profile import TripProfile, TripProfileUpdate
from app.models.routing_models.routing_models import Route_Payload
from app.models.trip_limits import MAX_STOPS, attraction_limit
from app.routers.algorithm_lab import LabInputs
from app.routing.base import PlanningError
from app.routing.cp_sat_selection import PRODUCTION_CONFIG, SelectionConfig, select_attractions
from app.routing.evaluation.fixtures import EvidenceError, Fixture, route_key
from app.routing.evaluation.network import OfflineNetworkError, no_network
from app.routing.evaluation.report import box_plot, columns, render
from app.routing.evaluation.runner import atomic, campaign, execute
from app.routing.evaluation.scenarios import Scenario, core_scenarios
from app.routing.explanation import capture_explanation
from app.routing.run_metrics import trip_evaluation
from app.routing.sources.mapbox import require_route_capacity
from tests.routing.conftest import build_route


def write_fixture(root, count=3, duration=3600):
    """A directed line graph, fixed captured routes, no hotel required for short checks."""
    root.mkdir(parents=True, exist_ok=True)

    def coords(progress):
        return [34.0, -118.0 + progress * 0.03]

    def road(points, extra=0):
        route = build_route().model_dump(mode="json")
        legs = []
        for start, end in zip(points, points[1:]):
            leg = copy.deepcopy(route["legs"][0])
            delta = abs(end[1] - start[1]) / 0.03
            seconds = delta * duration + extra
            leg.update(duration=seconds, distance=delta * 10000, weight=seconds)
            leg["steps"][0].update(
                duration=seconds,
                distance=delta * 10000,
                weight=seconds,
                geometry={"coordinates": [start[::-1], end[::-1]], "type": "LineString"},
            )
            leg["steps"][0]["maneuver"]["location"] = start[::-1]
            legs.append(leg)
        route.update(
            legs=legs,
            duration=sum(leg["duration"] for leg in legs),
            distance=sum(leg["distance"] for leg in legs),
            geometry={"coordinates": [p[::-1] for p in points], "type": "LineString"},
        )
        return route

    nodes = [{"id": "origin", "coordinates": coords(0), "timezone": "America/Los_Angeles"}]
    attractions = []
    routes = {}
    for i in range(count):
        progress = (i + 1) / (count + 1)
        item = {
            "provider_id": f"synthetic:{i}",
            "name": f"Unit place {i}",
            "coordinates": coords(progress),
            "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.9),
            "route_progress_seconds": progress * duration,
            "detour_seconds": 0,
            "section_id": 0,
            "source": "synthetic_unit_only",
            "categories": [],
        }
        request = [coords(0), item["coordinates"], coords(1)]
        item["solo_route_key"] = route_key(request)
        routes[route_key(request)] = {"request_coordinates": request, "response": road(request)}
        attractions.append(item)
        nodes.append(
            {
                "id": item["provider_id"],
                "coordinates": item["coordinates"],
                "timezone": "America/Los_Angeles",
            }
        )
    nodes.append({"id": "destination", "coordinates": coords(1), "timezone": "America/Los_Angeles"})
    if count <= 4:
        for size in range(count + 1):
            for subset in itertools.combinations(attractions, size):
                request = [coords(0), *(item["coordinates"] for item in subset), coords(1)]
                routes[route_key(request)] = {
                    "request_coordinates": request,
                    "response": road(request),
                }
    scenarios = core_scenarios()
    ids = [item["provider_id"] for item in attractions]
    data = {
        "baseline_route": road([coords(0), coords(1)]),
        "nodes": nodes,
        "attractions": attractions,
        "origin_id": "origin",
        "destination_id": "destination",
        "routes": routes,
        "hotel_offers": [],
        "timezone_lookups": [],
        "synthetic_single_timezone": "America/Los_Angeles",
        "production_shortlists": {row["id"]: ids[:60] for row in scenarios},
    }
    manifest = {
        "schema_version": 1,
        "fixture_id": "short-1d",
        "evidence_type": "synthetic_unit_only",
        "coverage": "recorded_pipeline",
        "attraction_count": count,
        "catalog_generation": None,
        "catalog_release": None,
        "attribution": None,
        "rights_evidence": None,
        "rating_capture": {"type": "synthetic_unit_only"},
        "routing_capture": {"type": "synthetic_directed_line_graph"},
        "departure": "2026-10-17T08:00:00-07:00",
        "evaluation_clock": "2026-10-16T00:00:00+00:00",
        "endpoints": ["la", "san-diego"],
        "sampling_seed": 1729,
        "tzdata_version": "2024.1",
        "limitations": ["Unit checks only"],
    }
    save_fixture(root, data, manifest)
    return data, manifest


def save_fixture(root, data, manifest):
    content = json.dumps(data, allow_nan=False).encode()
    (root / "data.json").write_bytes(content)
    manifest["files"] = {"data.json": hashlib.sha256(content).hexdigest()}
    (root / "manifest.json").write_text(json.dumps(manifest))


def spec(root, track="production-shortlist", method="cp_sat"):
    return {
        "run_id": "unit-run",
        "scenario": core_scenarios()[0],
        "track": track,
        "method": method,
        "config": asdict(SelectionConfig(candidate_limit=100 if track == "selection-100" else 60)),
        "fixtures": str(root),
        "unit_only": True,
        "identity": {"revision": "unit-only"},
    }


def test_matrix_has_30_roundtrippable_controlled_cells_and_15_stop_support():
    rows = core_scenarios()
    saved = json.loads(
        (Path(__file__).parents[1] / "fixtures/route_evaluation/v1/scenarios.json").read_text()
    )["scenarios"]
    assert saved == rows
    assert len(rows) == len({row["id"] for row in rows}) == 30
    for row in rows:
        scenario = Scenario.model_validate(row)
        assert scenario.inputs.num_stops == scenario.target_days * scenario.stops_per_day
        assert len(scenario.inputs.persona_weights) == 14
        assert sum(scenario.inputs.persona_weights.values()) == pytest.approx(1)
    for medium, tight in zip(rows[6:12], rows[24:30]):
        assert medium["inputs"] | {"budget": 60} == tight["inputs"]
        assert medium["fixture"] == tight["fixture"]
    assert sum(row["inputs"]["num_stops"] == 15 for row in rows) == 2


@pytest.mark.parametrize("count", [10, 11, 15, 20, MAX_STOPS])
def test_count_contract_is_shared(count):
    raw = copy.deepcopy(core_scenarios()[0]["inputs"])
    raw["num_stops"] = count
    assert TripProfile(num_stops=count).num_stops == count
    assert TripProfileUpdate(num_stops=count).num_stops == count
    assert LabInputs.model_validate(raw).num_stops == count
    assert (
        Route_Payload(initial_route=build_route(), num_stops=count, budget=180).num_stops == count
    )


@pytest.mark.parametrize("count", [0, MAX_STOPS + 1, True, 1.5, "15"])
def test_direct_api_rejects_unsupported_count_without_coercion(count):
    for model in (TripProfile, TripProfileUpdate):
        with pytest.raises(ValidationError):
            model(num_stops=count)
    with pytest.raises(ValidationError):
        Route_Payload(initial_route=build_route(), num_stops=count, budget=180)


@pytest.mark.parametrize("value", ["0", "31", "true", "1.5", "-1"])
def test_invalid_configuration_count(value):
    with pytest.raises(ValueError):
        attraction_limit(value)


def test_mapbox_coordinate_capacity_counts_hotels_and_endpoints():
    require_route_capacity(20 + 3 + 2)
    with pytest.raises(PlanningError, match="26 coordinates"):
        require_route_capacity(20 + 4 + 2)


def test_offline_network_guard_denies_connections_and_dns():
    with no_network():
        with pytest.raises(OfflineNetworkError):
            socket.create_connection(("example.test", 443))
        with pytest.raises(OfflineNetworkError):
            socket.getaddrinfo("example.test", 443)


def test_fixture_hashes_identity_and_synthetic_gate(tmp_path):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root)
    with pytest.raises(EvidenceError, match="synthetic"):
        Fixture(root)
    original = Fixture(root, allow_synthetic=True).hash
    (root / "data.json").write_text("{}")
    with pytest.raises(EvidenceError, match="SHA"):
        Fixture(root, allow_synthetic=True)
    data["attractions"][1]["provider_id"] = data["attractions"][0]["provider_id"]
    save_fixture(root, data, manifest)
    with pytest.raises(EvidenceError, match="duplicate"):
        Fixture(root, allow_synthetic=True)
    assert original


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda d: d.update(travel_time_seconds=[[0]]), "dimensions"),
        (lambda d: d["attractions"][0].update(coordinates=[999, 0]), "coordinates"),
        (lambda d: d["attractions"][0].update(detour_seconds=99), "detour"),
        (lambda d: d["attractions"][0]["attribute_ratings"].update(nature=float("inf")), "ratings"),
    ],
)
def test_fixture_rejects_inconsistent_measurements(tmp_path, mutation, match):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root)
    mutation(data)
    if match == "ratings":
        with pytest.raises(ValueError):
            save_fixture(root, data, manifest)
    else:
        save_fixture(root, data, manifest)
        with pytest.raises((EvidenceError, ValidationError), match=match):
            Fixture(root, allow_synthetic=True)


def test_full_100_is_offline_only_and_defaults_have_parity(tmp_path):
    root = tmp_path / "short-1d"
    write_fixture(root, count=100)
    fixture = Fixture(root, allow_synthetic=True)
    candidates = [item | {"utility": 0.9} for item in fixture.data["attractions"]]
    with pytest.raises(PlanningError, match="limit"):
        select_attractions(candidates, [], 1, 3600)
    with capture_explanation() as captured:
        selected = select_attractions(
            candidates, [], 1, 3600, config=SelectionConfig(candidate_limit=100)
        )
    assert len(selected) == 1 and captured["solver"]["eligible_count"] == 100
    assert PRODUCTION_CONFIG == SelectionConfig() and PRODUCTION_CONFIG.candidate_limit == 60
    shortlist = candidates[:6]
    with capture_explanation() as first:
        a = select_attractions(shortlist, [], 2, 3600)
    with capture_explanation() as second:
        b = select_attractions(shortlist, [], 2, 3600, config=SelectionConfig())
    assert a == b
    assert first["solver"]["objective_value"] == second["solver"]["objective_value"]


@pytest.mark.parametrize("method", ["cp_sat", "utility_first", "spacing_first"])
def test_actual_pipeline_and_selection_share_metrics_zero_network(tmp_path, method):
    write_fixture(tmp_path / "short-1d")
    row = execute(spec(tmp_path, "offline-pipeline", method))
    assert row["status"] == "completed", row["error"]
    assert row["external_calls"] == 0
    assert len(row["itinerary"]) == 1
    assert row["metrics"]["trip_evaluation"]["utility"]["delivered"]["mean"] == pytest.approx(0.9)
    assert row["assessments"]["request_fulfillment"] == "pass"
    assert row["metrics"]["trip_evaluation"]["hotel_costs"]["budget_utilization"] is None
    if method != "cp_sat":
        assert row["solver_status"] == "NOT_APPLICABLE"


def test_missing_reroute_and_longer_final_legs_remain_failures(tmp_path):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root)
    # Default K=1 chooses the middle; remove that exact route (also solo evidence).
    # Keep solo records but remove K=2 final request and ask for two attractions.
    for key in list(data["routes"]):
        if len(data["routes"][key]["request_coordinates"]) == 4:
            del data["routes"][key]
    save_fixture(root, data, manifest)
    request_spec = spec(tmp_path, "offline-pipeline")
    request_spec["scenario"] = core_scenarios()[2]
    row = execute(request_spec)
    assert row["status"] == "blocked" and row["stage"] == "final_reroute"
    assert row["solver_status"] in {"OPTIMAL", "FEASIBLE"}


def test_unknown_never_becomes_infeasible_or_zero_utility(tmp_path, monkeypatch):
    write_fixture(tmp_path / "short-1d")
    import app.routing.evaluation.runner as runner

    def unknown(*args, **kwargs):
        from app.routing.explanation import record_explanation

        record_explanation(solver={"status": "UNKNOWN"}, candidates=[])
        raise PlanningError("no conclusion", 503)

    monkeypatch.setattr(runner, "select_attractions", unknown)
    row = execute(spec(tmp_path))
    assert row["status"] == "failed" and row["solver_status"] == "UNKNOWN"
    assert row["metrics"]["selected_utility_sum"] is None
    assert row["metrics"]["trip_evaluation"]["utility"]["selected"] is None


def test_zero_tolerance_integer_rounding_artifact_is_explicit():
    candidate = {
        "provider_id": "unit:a",
        "name": "a",
        "coordinates": [0.0, 0.0],
        "utility": 0.9000009,
        "route_progress_seconds": 50,
        "detour_seconds": 0,
    }
    with capture_explanation() as explanation:
        with pytest.raises(PlanningError):
            select_attractions([candidate], [], 1, 100, config=SelectionConfig(quality_loss=0))
    assert explanation["solver"]["status"] == "INFEASIBLE"


def test_hand_calculated_gaps_budget_and_missing_delivered_ids():
    envelope = {
        "mode": "offline_pipeline",
        "input_snapshot": {
            "num_stops": 2,
            "budget": 100,
            "hotel_rooms": [{}],
            "start_date": "2026-10-17T08:00:00-07:00",
        },
        "explanation": {
            "solver": {"status": "OPTIMAL"},
            "candidates": [
                {"provider_id": "a", "utility": 0.7, "selected": True},
                {"provider_id": "b", "utility": 0.9, "selected": True},
            ],
        },
        "route": {
            "duration": 1000,
            "distance": 5000,
            "stops": [
                {"type": "stop", "provider_id": "a", "duration": 100, "distance": 500},
                {
                    "type": "hotel",
                    "provider_id": "h",
                    "duration": 400,
                    "distance": 2000,
                    "room_offers": [{"price": 120}],
                },
                {"type": "stop", "provider_id": "b", "duration": 300, "distance": 1500},
                {"type": "end", "duration": 200, "distance": 1000},
            ],
        },
        "direct_route": {"duration": 800, "distance": 4000},
        "error": None,
        "itinerary": [],
    }
    trip = trip_evaluation(envelope)
    assert trip["utility"]["selected"]["median"] == pytest.approx(0.8)
    assert trip["driving_gaps"]["maximum_stretch_seconds"] == 400
    assert trip["driving_gaps"]["maximum_stretch_distance_meters"] == 2000
    assert trip["driving_gaps"]["attraction_gaps_seconds"] == [100, 700, 200]
    assert trip["hotel_costs"]["budget_utilization"] == 1.2
    assert trip["hotel_costs"]["above_target_total_usd"] == 20
    assert trip["driving"]["extra_duration_seconds"] == 200
    envelope["route"]["stops"][0]["provider_id"] = "missing"
    assert trip_evaluation(envelope)["utility"]["delivered"] is None
    envelope["input_snapshot"]["budget"] = 0
    assert trip_evaluation(envelope)["hotel_costs"]["budget_utilization"] is None
    envelope["route"]["stops"][1]["room_offers"] = []
    assert trip_evaluation(envelope)["hotel_costs"]["quoted_total_usd"] is None


def test_synthetic_reports_have_no_primary_figures_and_svg_is_calculated(tmp_path):
    output = tmp_path / "report"
    output.mkdir()
    row = {
        "run_id": "unit",
        "scenario_id": "unit",
        "trip_type": "short-1d",
        "persona": "nature",
        "stops_per_day": 1,
        "method": "cp_sat",
        "track": "selection-100",
        "status": "completed",
        "solver_status": "OPTIMAL",
        "evidence_type": "synthetic_unit_only",
        "stage": "complete",
        "metrics": None,
    }
    atomic(
        output / "manifest.json",
        json.dumps({"expected_runs": 1, "identity": {"revision": "unit", "metric_version": "v1"}}),
    )
    atomic(output / "runs.jsonl", json.dumps(row) + "\n")
    assert render(output)["primary_figures"] == 0
    assert not (output / "figures").exists()
    for svg in (
        box_plot("Unit values", {"method": [0.1, 0.2, 0.3, 0.4]}, "unit test"),
        columns("Unit counts", {"method": {"OPTIMAL": 2, "UNKNOWN": 1}}, "unit test"),
    ):
        ElementTree.fromstring(svg)
    assert box_plot("Empty", {"method": []}, "unit test") is None


def test_serial_campaign_has_terminal_rows_for_missing_fixture(tmp_path):
    output = tmp_path / "campaign"
    args = SimpleNamespace(
        output=str(output),
        fixtures=str(tmp_path / "missing"),
        track="selection-100",
        sweep=None,
        methods=["cp_sat"],
        unit_only=False,
        deadline=20,
    )
    campaign(args, [core_scenarios()[0]])
    rows = [json.loads(line) for line in (output / "runs.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["status"] == "blocked"
    assert rows[0]["solver_status"] == "NOT_RUN"
    with pytest.raises(ValueError, match="never overwritten"):
        campaign(args, [core_scenarios()[0]])


def test_final_timing_failure_retains_measured_route_and_raw_selection(tmp_path):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root)
    for record in data["routes"].values():
        if len(record["request_coordinates"]) == 4:
            for leg in record["response"]["legs"]:
                leg["duration"] = 5 * 3600
            record["response"]["duration"] = 15 * 3600
    save_fixture(root, data, manifest)
    request = spec(tmp_path, "offline-pipeline")
    request["scenario"] = core_scenarios()[2]
    row = execute(request)
    assert row["status"] == "failed" and row["stage"] == "final_timing"
    assert row["route"] is not None and row["itinerary"] is None
    assert row["metrics"]["trip_evaluation"]["driving"]["extra_duration_seconds"] > 0
    assert row["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert row["assessments"]["pipeline_completion"] == "fail"


def test_itinerary_failure_keeps_route_and_missing_hotels_keep_stage(tmp_path, monkeypatch):
    write_fixture(tmp_path / "short-1d")
    import app.routing.evaluation.offline as offline

    async def failed(*args, **kwargs):
        raise PlanningError("Unit itinerary failure", 502)

    monkeypatch.setattr(offline, "build_itinerary", failed)
    row = execute(spec(tmp_path, "offline-pipeline"))
    assert row["status"] == "failed" and row["stage"] == "itinerary"
    assert row["route"] is not None and row["itinerary"] is None
    monkeypatch.undo()
    write_fixture(tmp_path / "short-1d", duration=16 * 3600)
    row = execute(spec(tmp_path, "offline-pipeline"))
    assert row["status"] == "failed" and row["stage"] == "route.schedule"
    assert row["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert "hotel" in row["error"].lower()


def test_tool_schemas_advertise_the_shared_count_limit():
    from app.agent.tool_dispatcher import AppToolDispatcher

    tools = {tool.name: tool for tool in AppToolDispatcher().specs()}
    for name in ("generate_final_route", "record_trip_details"):
        schema = tools[name].parameters["properties"]
        if "details" in schema:
            schema = schema["details"]["properties"]
        assert schema["num_stops"]["maximum"] == MAX_STOPS
        assert schema["num_stops"]["minimum"] == 1
