"""Synthetic contract models only: no imported real records or benchmark claims."""

import asyncio
import copy
import hashlib
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agent.persona import ATTRIBUTE_KEYS
from app.routing.evaluation.comparisons import bound_comparisons, paired_results, successful
from app.routing.evaluation.fixtures import EvidenceError, Fixture
from app.routing.evaluation.offline import FrozenProviders
from app.routing.evaluation.preparation import (
    assemble,
    export_reviewed,
    freeze_shortlists,
    sample_corridor,
)
from app.routing.evaluation.report import fields, render, with_provenance
from app.routing.evaluation.runner import execute, identity
from app.routing.evaluation.scenarios import Scenario, coast_diagnostics, core_scenarios
from app.routing.occupancy import HotelRoom
from app.routing.run_metrics import fingerprint
from tests.routing.evaluation_tests import save_fixture, spec, write_fixture

REF = {"uri": "unit-contract-evidence.json", "sha256": fingerprint("unit evidence")}


def reviewed_bundle(root):
    """Emulate the real-schema shape to test validation; never run as a primary suite."""
    data, manifest = write_fixture(root)
    manifest.update(
        schema_version=2,
        evidence_type="catalog_recorded_pipeline",
        catalog_generation="unit-generation",
        catalog_release="unit-release",
        attribution="Unit contract attribution",
        rights_evidence="rights.json",
        access_review_file="access_reviews.json",
    )
    manifest["rating_capture"] = {
        "capture_id": "unit-ratings",
        "model": "unit-model",
        "prompt_hash": fingerprint("unit-prompt"),
        "configuration": {},
        "captured_at": "2026-10-15T00:00:00+00:00",
    }
    manifest["routing_capture"] = {
        "capture_id": "unit-roads",
        "provider": "unit-recorded-provider",
        "profile": "driving",
        "departure_context": manifest["departure"],
        "captured_at": "2026-10-15T00:00:00+00:00",
    }
    records = []
    for item in data["attractions"]:
        item.update(
            source_generation="unit-generation",
            source_release="unit-release",
            source_attribution="Unit contract attribution",
            source_provenance=[{"unit": "contract"}],
            rating_capture_id="unit-ratings",
            evidence_references=[REF],
        )
        records.append(
            {
                "provider_id": item["provider_id"],
                "coordinates": item["coordinates"],
                "status": "eligible",
                "arrival_eligible": True,
                "reviewed_at": "2026-10-15T00:00:00+00:00",
                "valid_through": "2026-11-01",
                "reviewer": "unit-reviewer",
                "evidence": [REF],
            }
        )
    for record in data["routes"].values():
        record["capture_id"] = "unit-roads"
    ledger = {
        "schema_version": 1,
        "catalog_generation": "unit-generation",
        "catalog_release": "unit-release",
        "records": records,
    }
    rights = {
        "schema_version": 1,
        "catalog_generation": "unit-generation",
        "catalog_release": "unit-release",
        "attribution": "Unit contract attribution",
        "approved_for_evaluation": True,
        "reviewer": "unit-reviewer",
        "reviewed_at": "2026-10-15T00:00:00+00:00",
        "licenses": [REF],
    }
    save_reviewed(root, data, manifest, ledger, rights)
    return data, manifest, ledger, rights


def save_reviewed(root, data, manifest, ledger, rights):
    save_fixture(root, data, manifest)
    for name, value in (("access_reviews.json", ledger), ("rights.json", rights)):
        content = json.dumps(value).encode()
        (root / name).write_bytes(content)
        manifest["files"][name] = hashlib.sha256(content).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize(
    "change,pattern",
    [
        (
            lambda m, d, ledger, r: ledger["records"][0].update(status="pending"),
            "access review failed",
        ),
        (
            lambda m, d, ledger, r: ledger["records"][0].update(arrival_eligible=False),
            "access review failed",
        ),
        (
            lambda m, d, ledger, r: ledger["records"][0].update(valid_through="2026-10-16"),
            "expired",
        ),
        (
            lambda m, d, ledger, r: ledger["records"][0].update(coordinates=[0.0, 0.0]),
            "coordinates_changed",
        ),
        (lambda m, d, ledger, r: m["rating_capture"].pop("model"), "model"),
        (lambda m, d, ledger, r: m["rating_capture"].update(prompt_hash="wrong"), "prompt_hash"),
        (
            lambda m, d, ledger, r: m["routing_capture"].update(
                departure_context="2026-10-18T08:00:00-07:00"
            ),
            "context",
        ),
        (
            lambda m, d, ledger, r: next(iter(d["routes"].values())).update(capture_id="other"),
            "capture identity",
        ),
        (
            lambda m, d, ledger, r: d["attractions"][0].update(rating_capture_id="other"),
            "rating capture",
        ),
        (lambda m, d, ledger, r: r.update(catalog_generation="other"), "rights evidence"),
        (lambda m, d, ledger, r: ledger.update(catalog_generation="other"), "different catalog"),
    ],
)
def test_real_schema_fail_closed_contracts(tmp_path, change, pattern):
    root = tmp_path / "fixture"
    data, manifest, ledger, rights = reviewed_bundle(root)
    change(manifest, data, ledger, rights)
    save_reviewed(root, data, manifest, ledger, rights)
    with pytest.raises((EvidenceError, ValueError, ValidationError), match=pattern):
        Fixture(root)


def test_hashed_completed_reviews_and_horizon_are_required(tmp_path):
    root = tmp_path / "fixture"
    data, m, ledger, r = reviewed_bundle(root)
    fixture = Fixture(root)
    assert len(fixture.reviews) == 3
    with pytest.raises(EvidenceError, match="horizon"):
        fixture.require_access_until(datetime(2026, 12, 1).date())
    (root / "access_reviews.json").write_text("{}")
    with pytest.raises(EvidenceError, match="SHA"):
        Fixture(root)


@pytest.mark.asyncio
async def test_duplicate_original_names_and_persona_hotel_scores(tmp_path):
    root = tmp_path / "short-1d"
    data, m = write_fixture(root)
    data["attractions"][1]["name"] = data["attractions"][0]["name"]
    save_fixture(root, data, m)
    row = await asyncio.to_thread(execute, spec(tmp_path, "offline-pipeline"))
    assert row["status"] == "completed", row["error"]
    ratings = dict.fromkeys(ATTRIBUTE_KEYS, 0.0) | {"nature": 1.0}
    offers = [
        {
            "provider_id": "unit-hotel",
            "coordinates": [34.0, -118.0],
            "check_in_date": "2026-10-17",
            "hotel_rooms": [{"adults": 2, "child_ages": []}],
            "attribute_ratings": ratings,
            "utility": 0,
        }
    ]
    provider = FrozenProviders(SimpleNamespace(data={"attractions": [], "hotel_offers": offers}))
    nature = await provider.hotels(
        [34.0, -118.0],
        datetime(2026, 10, 17).date(),
        None,
        dict.fromkeys(ATTRIBUTE_KEYS, 0.0) | {"nature": 1.0},
        [HotelRoom(adults=2, child_ages=[])],
    )
    food = await provider.hotels(
        [34.0, -118.0],
        datetime(2026, 10, 17).date(),
        None,
        dict.fromkeys(ATTRIBUTE_KEYS, 0.0) | {"food": 1.0},
        [HotelRoom(adults=2, child_ages=[])],
    )
    assert nature[0]["utility"] == 1 and food[0]["utility"] == 0


def test_read_only_export_excludes_pending_and_sampling_never_pads(tmp_path):
    root = tmp_path / "captures"
    data, m, ledger, rights = reviewed_bundle(root)
    ledger["records"][1]["status"] = "pending"
    source = {
        "schema_version": 1,
        "evidence_type": "synthetic_unit_only",
        "catalog_generation": m["catalog_generation"],
        "catalog_release": m["catalog_release"],
        "attribution": m["attribution"],
        "records": data["attractions"],
    }
    for name, value in (
        ("catalog.json", source),
        ("ledger.json", ledger),
        ("rights.json", rights),
        ("baseline.json", data["baseline_route"]),
    ):
        (tmp_path / name).write_text(json.dumps(value))
    before = (tmp_path / "catalog.json").read_bytes()
    counts = export_reviewed(
        tmp_path / "catalog.json",
        tmp_path / "ledger.json",
        tmp_path / "rights.json",
        tmp_path / "export.json",
        m["evaluation_clock"],
        m["departure"],
        unit_only=True,
    )
    assert counts == {"source": 3, "approved": 2, "excluded": 1}
    result = sample_corridor(
        tmp_path / "export.json",
        tmp_path / "baseline.json",
        tmp_path / "sample.json",
        count=100,
        unit_only=True,
    )
    assert (
        result["status"] == "insufficient_real_fixture_coverage" and result["selected_count"] == 2
    )
    assert (tmp_path / "catalog.json").read_bytes() == before
    with pytest.raises(EvidenceError, match="insufficient"):
        assemble(root, tmp_path / "sample.json", tmp_path / "assembled", unit_only=True)
    with pytest.raises(EvidenceError, match="unit-only"):
        sample_corridor(
            tmp_path / "export.json", tmp_path / "baseline.json", tmp_path / "another.json"
        )


def test_sampling_is_frozen_and_assembly_and_shortlists_are_new_versions(tmp_path):
    root = tmp_path / "captures"
    data, m, ledger, rights = reviewed_bundle(root)
    source = {
        "schema_version": 1,
        "evidence_type": "synthetic_unit_only",
        "catalog_generation": m["catalog_generation"],
        "catalog_release": m["catalog_release"],
        "attribution": m["attribution"],
        "records": data["attractions"],
    }
    for name, value in (
        ("catalog.json", source),
        ("ledger.json", ledger),
        ("rights.json", rights),
        ("baseline.json", data["baseline_route"]),
    ):
        (tmp_path / name).write_text(json.dumps(value))
    export_reviewed(
        tmp_path / "catalog.json",
        tmp_path / "ledger.json",
        tmp_path / "rights.json",
        tmp_path / "export.json",
        m["evaluation_clock"],
        m["departure"],
        unit_only=True,
    )
    for name in ("sample1.json", "sample2.json"):
        sample_corridor(
            tmp_path / "export.json",
            tmp_path / "baseline.json",
            tmp_path / name,
            count=2,
            unit_only=True,
        )
    assert (tmp_path / "sample1.json").read_bytes() == (tmp_path / "sample2.json").read_bytes()
    result = assemble(root, tmp_path / "sample1.json", tmp_path / "assembled", unit_only=True)
    assert result["count"] == 2 and Fixture(root).manifest.attraction_count == 3
    result = freeze_shortlists(
        tmp_path / "assembled", core_scenarios(), tmp_path / "frozen", unit_only=True
    )
    frozen = Fixture(tmp_path / "frozen", allow_synthetic=True)
    assert result["count"] == 2 and len(frozen.data["production_shortlists"]) == 6


def test_diagnostics_workload_visits_and_resources(tmp_path):
    write_fixture(tmp_path / "short-1d")
    row = execute(spec(tmp_path, "offline-pipeline"))
    screen = row["workload_screening"]
    assert screen["requested_visit_seconds"] == 7200 and screen["proof_of_infeasibility"] is False
    assert row["metrics"]["trip_evaluation"]["schedule"]["visit_seconds"] == 7200
    assert row["metrics"]["trip_evaluation"]["schedule"]["overnight_downtime_seconds"] == 0
    assert row["resources"]["cpu_seconds"] >= 0
    assert row["resources"]["peak_rss_bytes"] is None or row["resources"]["peak_rss_bytes"] > 0
    memory = identity()["physical_memory_bytes"]
    assert memory is None or memory > 0
    diagnostics = coast_diagnostics()
    assert len(diagnostics) == 12 and {row["target_days"] for row in diagnostics} == {7, 10}
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            next(row for row in diagnostics if row["inputs"]["num_stops"] == 30)
        )


def test_publication_conditioning_provenance_and_model_scoped_bounds():
    base = {
        "run_id": "base",
        "method": "cp_sat",
        "status": "completed",
        "evidence_type": "catalog_selection_with_captured_measurements",
        "track": "selection-100",
        "assessments": {"request_fulfillment": "pass"},
        "parameter": "time_limit_seconds",
        "parameter_value": 5,
        "paired_key": "unit-pair",
        "persona": "nature",
        "fixture_hash": "unit-fixture",
        "model_key": "unit-model",
        "solver_status": "OPTIMAL",
        "solver": {"objective_value": 0, "best_bound": 0},
        "selected_ids": ["a"],
        "metrics": {"trip_evaluation": {"utility": {"selected": {"mean": 0.8}}}},
    }
    changed = copy.deepcopy(base)
    changed.update(
        run_id="changed",
        parameter_value=1,
        selected_ids=["b"],
        solver_status="FEASIBLE",
        solver={"objective_value": 10, "best_bound": 0},
    )
    failed = copy.deepcopy(base)
    failed.update(run_id="failed", status="failed")
    assert successful(base) and not successful(failed)
    pairs = paired_results([base, changed, failed], fields)
    assert len(pairs) == 1 and pairs[0]["selected_added"] == ["b"]
    bounds = bound_comparisons([base, changed, failed])
    assert (
        bounds[1]["cost_excess_above_proven_optimum"] == 10 and bounds[1]["excess_percent"] is None
    )
    metadata = {
        "revision": "unit-revision",
        "metric_version": "unit-metrics",
        "catalog_generations": ["unit-generation"],
        "evidence_layer": "unit-contract",
    }
    svg = with_provenance('<svg xmlns="http://www.w3.org/2000/svg"></svg>', metadata)
    assert "unit-revision" in svg and "unit-generation" in svg and "<metadata>" in svg


def test_exact_detour_weight_and_quality_sweeps_share_the_model():
    from app.routing.cp_sat_selection import SelectionConfig, select_attractions
    from app.routing.explanation import capture_explanation

    def candidate(key, progress, utility, detour):
        return {
            "provider_id": key,
            "name": key,
            "coordinates": [34.0, -118.0],
            "route_progress_seconds": progress,
            "utility": utility,
            "detour_seconds": detour,
        }

    places = [candidate("middle", 500, 0.9, 100), candidate("near-middle", 400, 0.9, 0)]
    chosen = []
    for weight in (0, 1, 4):
        with capture_explanation() as explanation:
            result = select_attractions(
                places, [], 1, 1000, config=SelectionConfig(detour_weight=weight)
            )
        assert explanation["solver"]["status"] == "OPTIMAL"
        chosen.append(result[0].candidate)
    assert [place["provider_id"] for place in chosen] == ["middle", "middle", "near-middle"]
    costs = []
    for tolerance in (0, 0.2):
        with capture_explanation() as explanation:
            select_attractions(
                [candidate("quality", 100, 0.95, 0), candidate("spacing", 500, 0.8, 0)],
                [],
                1,
                1000,
                config=SelectionConfig(quality_loss=tolerance),
            )
        assert explanation["solver"]["status"] == "OPTIMAL"
        costs.append(explanation["solver"]["objective_value"])
    assert costs[1] <= costs[0]


def test_warmups_are_separate_and_synthetic_bounds_are_not_primary(tmp_path):
    from app.routing.evaluation.runner import campaign

    args = SimpleNamespace(
        output=str(tmp_path / "campaign"),
        fixtures=str(tmp_path / "missing"),
        track="selection-100",
        sweep=None,
        methods=["cp_sat"],
        unit_only=True,
        deadline=20,
        warmup=1,
    )
    output = campaign(args, [core_scenarios()[0]])
    assert len((output / "runs.jsonl").read_text().splitlines()) == 1
    assert len((output / "warmups.jsonl").read_text().splitlines()) == 1
    assert json.loads((output / "manifest.json").read_text())["expected_runs"] == 1
    synthetic = {
        "method": "cp_sat",
        "solver_status": "OPTIMAL",
        "evidence_type": "synthetic_unit_only",
        "solver": {"objective_value": 0, "best_bound": 0},
    }
    assert bound_comparisons([synthetic]) == []


def test_render_conditions_quality_but_keeps_failure_denominators(tmp_path):
    from xml.etree import ElementTree

    root = tmp_path / "unit-contract-report"
    root.mkdir()
    base = {
        "run_id": "unit-good",
        "scenario_id": "unit-scenario",
        "trip_type": "short-1d",
        "persona": "nature",
        "stops_per_day": 1,
        "method": "cp_sat",
        "track": "selection-100",
        "status": "completed",
        "solver_status": "OPTIMAL",
        "stage": "complete",
        "evidence_type": "catalog_selection_with_captured_measurements",
        "fixture_hash": "unit-fixture",
        "catalog_generation": "unit-generation",
        "model_key": "unit-model",
        "assessments": {"request_fulfillment": "pass"},
        "metrics": {"trip_evaluation": {"utility": {"selected": {"mean": 0.8}}}},
    }
    failed = copy.deepcopy(base)
    failed.update(run_id="unit-failed", status="failed", stage="unit-injected-failure")
    failed["metrics"]["trip_evaluation"]["utility"]["selected"]["mean"] = 0.99
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "expected_runs": 2,
                "identity": {"revision": "unit-revision", "metric_version": "unit-metrics"},
            }
        )
    )
    (root / "runs.jsonl").write_text(json.dumps(base) + "\n" + json.dumps(failed) + "\n")
    assert render(root)["recorded"] == 2
    figure = next((root / "figures").glob("*utility_mean.svg"))
    tree = ElementTree.fromstring(figure.read_text())
    metadata = json.loads(tree.find("{http://www.w3.org/2000/svg}metadata").text)
    assert metadata["attempted"] == 2 and metadata["successful_fulfilled"] == 1
    assert "n=1" in figure.read_text()
    assert "unit-revision" in figure.read_text() and "unit-generation" in figure.read_text()


def test_mixed_generation_keeps_leaf_release_and_attribution(tmp_path):
    root = tmp_path / "mixed-contract"
    data, manifest, ledger, rights = reviewed_bundle(root)
    manifest["source_catalogs"] = {
        "unit-a": {"release": "leaf-a", "attribution": "Unit A attribution"},
        "unit-b": {"release": "leaf-b", "attribution": "Unit B attribution"},
    }
    for index, item in enumerate(data["attractions"]):
        source = "unit-b" if index == 1 else "unit-a"
        item.update(
            source=source,
            source_release=manifest["source_catalogs"][source]["release"],
            source_attribution=manifest["source_catalogs"][source]["attribution"],
        )
    save_reviewed(root, data, manifest, ledger, rights)
    assert Fixture(root).manifest.source_catalogs["unit-a"].release == "leaf-a"
    source = {
        "schema_version": 1,
        "evidence_type": "synthetic_unit_only",
        "catalog_generation": manifest["catalog_generation"],
        "catalog_release": manifest["catalog_release"],
        "attribution": manifest["attribution"],
        "source_catalogs": manifest["source_catalogs"],
        "records": data["attractions"],
    }
    (tmp_path / "mixed-export.json").write_text(json.dumps(source))
    export_reviewed(
        tmp_path / "mixed-export.json",
        root / "access_reviews.json",
        root / "rights.json",
        tmp_path / "approved.json",
        manifest["evaluation_clock"],
        manifest["departure"],
        unit_only=True,
    )
    assert {
        item["source_release"]
        for item in json.loads((tmp_path / "approved.json").read_text())["records"]
    } == {"leaf-a", "leaf-b"}
    data["attractions"][0]["source_release"] = "incorrect-global-release"
    save_reviewed(root, data, manifest, ledger, rights)
    with pytest.raises(EvidenceError, match="source release"):
        Fixture(root)


def test_shortlist_checks_review_horizon_before_discovery(tmp_path):
    root = tmp_path / "review-contract"
    data, manifest, ledger, rights = reviewed_bundle(root)
    for review in ledger["records"]:
        review["valid_through"] = "2026-10-17"
    save_reviewed(root, data, manifest, ledger, rights)
    scenario = core_scenarios()[0]
    scenario.update(target_days=2)
    scenario["inputs"]["num_stops"] = 2
    with pytest.raises(EvidenceError, match="horizon"):
        freeze_shortlists(root, [scenario], tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_retained_duplicate_source_attribution_is_not_dropped(tmp_path):
    root = tmp_path / "credits-contract"
    data, manifest, ledger, rights = reviewed_bundle(root)
    item = data["attractions"][0]
    item["source_provenance"].append({"source_attribution": "Unit additional source credit"})
    item["source_attribution"] = manifest["attribution"] + "; Unit additional source credit"
    save_reviewed(root, data, manifest, ledger, rights)
    assert (
        Fixture(root)
        .data["attractions"][0]["source_attribution"]
        .endswith("Unit additional source credit")
    )
    item["source_attribution"] = manifest["attribution"]
    save_reviewed(root, data, manifest, ledger, rights)
    with pytest.raises(EvidenceError, match="attribution mismatch"):
        Fixture(root)
