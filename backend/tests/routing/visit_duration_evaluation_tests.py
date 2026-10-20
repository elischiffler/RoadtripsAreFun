"""Synthetic integration controls; no real capture, hours or benchmark claims."""

import copy

import pytest

from app.agent.persona import normalize_weights
from app.routing.evaluation.fixtures import EvidenceError, Fixture
from app.routing.evaluation.runner import execute
from app.routing.run_metrics import METRIC_VERSION, trip_evaluation
from app.routing.sources.persona_candidates import ProposedPlace, VerifiedPlace, _candidate
from app.routing.sources.visit_durations import duration_context, duration_context_hash
from app.routing.visit_duration import VisitDuration
from tests.routing.evaluation_tests import save_fixture, spec, write_fixture
from tests.routing.evaluation_v2_tests import reviewed_bundle, save_reviewed


def capture(item, weights, seconds, *, capture_id="synthetic-duration-control"):
    weights = normalize_weights(weights)
    candidate = _candidate(
        VerifiedPlace.model_validate(item),
        ProposedPlace(name=item["name"], attribute_ratings=item["attribute_ratings"]),
        weights,
    )
    return {
        "provider_id": item["provider_id"],
        "context_hash": duration_context_hash(duration_context(candidate, weights)),
        "capture_id": capture_id,
        "visit_duration": VisitDuration(
            seconds=seconds, source="ai_estimate", reason="estimated"
        ).model_dump(),
    }


def test_frozen_pipeline_replays_context_matched_dwell_and_wait_with_zero_network(tmp_path):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root, count=1)
    request = spec(tmp_path, "offline-pipeline")
    place = data["attractions"][0]
    calendar = place["source_provenance"][0]["source_visit_calendar"]
    calendar["weekly_windows"][0].update(opens="10:00", closes="11:30")
    data["visit_duration_estimates"] = [
        capture(place, request["scenario"]["inputs"]["persona_weights"], 3600)
    ]
    save_fixture(root, data, manifest)
    row = execute(request)
    assert row["status"] == "completed", row["error"]
    stop = next(s for s in row["route"]["stops"] if s["type"] == "stop")
    assert stop["arrival_time"] == "2026-10-17T10:00:00-07:00"
    assert stop["departure_time"] == "2026-10-17T11:00:00-07:00"
    assert stop["wait_seconds"] == pytest.approx(5400)
    assert stop["visit_duration"]["seconds"] == 3600
    displayed = next(
        s
        for day in row["itinerary"]
        for s in day["stops"]
        if s["provider_id"] == place["provider_id"]
    )
    assert (displayed["arrival_time"], displayed["departure_time"]) == (
        stop["arrival_time"],
        stop["departure_time"],
    )
    evaluation = row["metrics"]["trip_evaluation"]
    assert evaluation["schedule"]["visit_seconds"] == 3600
    assert evaluation["scenario_target"]["daily_active_seconds"]["2026-10-17"] == pytest.approx(
        12600
    )
    assert evaluation["scenario_target"]["active_time_assessment_reason"] is None
    assert row["external_calls"] == 0
    assert row["offline_provider_reads"]["captured_duration_reads"] == 1
    assert "duration_fallbacks" not in row["offline_provider_reads"]


@pytest.mark.parametrize("change", ["preferences", "activities", "description", "ratings", "name"])
def test_capture_context_changes_use_labeled_fallback_instead_of_replaying_old_duration(
    tmp_path, change
):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root, count=1)
    request = spec(tmp_path, "offline-pipeline")
    place = data["attractions"][0]
    data["visit_duration_estimates"] = [
        capture(place, request["scenario"]["inputs"]["persona_weights"], 3600)
    ]
    if change == "preferences":
        weights = request["scenario"]["inputs"]["persona_weights"]
        request["scenario"]["inputs"]["persona_weights"] = dict.fromkeys(weights, 0) | {"nature": 1}
    elif change == "ratings":
        place["attribute_ratings"]["nature"] = 0.4
    elif change == "activities":
        place["activities"] = ["Synthetic changed activity"]
    elif change == "description":
        place["description"] = "Synthetic changed details"
    else:
        place["name"] = "Synthetic changed name"
    save_fixture(root, data, manifest)
    row = execute(request)
    assert row["status"] == "completed", row["error"]
    stop = next(s for s in row["route"]["stops"] if s["type"] == "stop")
    assert stop["visit_duration"]["seconds"] == 7200
    assert stop["visit_duration"]["source"] == "conservative_fallback"
    assert stop["visit_duration"]["reason"] == "missing_estimate"
    assert row["offline_provider_reads"]["duration_fallbacks"] == 1
    assert row["external_calls"] == 0


def test_separate_fixtures_do_not_share_cached_duration_captures(tmp_path):
    root = tmp_path / "short-1d"
    data, manifest = write_fixture(root, count=1)
    request = spec(tmp_path, "offline-pipeline")
    for seconds in (3600, 10800):
        data["visit_duration_estimates"] = [
            capture(
                data["attractions"][0], request["scenario"]["inputs"]["persona_weights"], seconds
            )
        ]
        save_fixture(root, data, manifest)
        row = execute(request)
        assert row["status"] == "completed", row["error"]
        assert row["metrics"]["trip_evaluation"]["schedule"]["visit_seconds"] == seconds


@pytest.mark.parametrize(
    "namespace,source", [("boulder:", "boulder-osmp"), ("overture:", "overture")]
)
@pytest.mark.parametrize("seconds", [900, 10800, None])
def test_validated_frozen_catalog_lookup_preserves_variable_dwell_and_metrics(
    tmp_path, monkeypatch, namespace, source, seconds
):
    import json
    from datetime import datetime

    from app.catalog import repository
    from app.crud import chat_crud
    from app.routing.evaluation import network
    from tests.routing.frozen_itinerary_catalog_tests import catalog_fixture

    root = tmp_path / "short-1d"
    data = catalog_fixture(root, namespace, source)
    manifest = json.loads((root / "manifest.json").read_text())
    request = spec(tmp_path, "offline-pipeline")
    if seconds is not None:
        data["visit_duration_estimates"] = [
            capture(item, request["scenario"]["inputs"]["persona_weights"], seconds)
            for item in data["attractions"]
        ]
    save_fixture(root, data, manifest)
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("Validated frozen evaluation must not read live catalog or network")

    for name in ("current_records", "nearby", "nearby_page"):
        monkeypatch.setattr(repository, name, forbidden)
    monkeypatch.setattr(chat_crud, "_get_conn", forbidden)
    monkeypatch.setattr(network, "denied", forbidden)
    row = execute(request)
    assert row["status"] == "completed", row["error"]
    assert row["external_calls"] == 0 and attempted == []
    assert row["offline_provider_reads"]["captured_catalog_fact_reads"] == 1
    assert len(row["selected_ids"]) == 1
    stop = next(item for item in row["route"]["stops"] if item["type"] == "stop")
    expected = 7200 if seconds is None else seconds
    assert stop["visit_duration"]["seconds"] == expected
    assert stop["visit_duration"]["source"] == (
        "conservative_fallback" if seconds is None else "ai_estimate"
    )
    assert (
        datetime.fromisoformat(stop["departure_time"])
        - datetime.fromisoformat(stop["arrival_time"])
    ).total_seconds() == expected
    trip = row["metrics"]["trip_evaluation"]
    assert trip["schedule"]["visit_seconds"] == expected
    assert trip["scenario_target"]["maximum_daily_active_seconds"] == pytest.approx(3600 + expected)
    displayed = next(
        item
        for day in row["itinerary"]
        for item in day["stops"]
        if item["provider_id"] == stop["provider_id"]
    )
    assert displayed["visit_duration"] == stop["visit_duration"]
    assert displayed["arrival_time"] == stop["arrival_time"]
    assert displayed["departure_time"] == stop["departure_time"]
    assert displayed["source_release"] == "explicit-synthetic-frozen-release"
    assert json.loads((root / "data.json").read_text()) == data


def test_real_schema_accepts_context_scoped_capture_with_complete_provenance(tmp_path):
    data, manifest, ledger, rights = reviewed_bundle(tmp_path)
    weights = spec(tmp_path)["scenario"]["inputs"]["persona_weights"]
    manifest["duration_capture"] = copy.deepcopy(manifest["rating_capture"]) | {
        "capture_id": "unit-durations"
    }
    entry = capture(data["attractions"][0], weights, 3600, capture_id="unit-durations")
    data["visit_duration_estimates"] = [entry]
    save_reviewed(tmp_path, data, manifest, ledger, rights)
    assert Fixture(tmp_path).duration_estimates == {
        (entry["provider_id"], entry["context_hash"]): entry["visit_duration"]
    }


@pytest.mark.parametrize(
    "change,pattern",
    [
        ("missing_provenance", "duration capture provenance"),
        ("future", "predate evaluation clock"),
        ("identity", "duration capture identity"),
        ("duplicate", "duplicate captured duration"),
        ("unknown", "unknown or duplicate"),
        ("bound", "seconds"),
    ],
)
def test_real_schema_requires_valid_duration_capture_provenance_and_bounds(
    tmp_path, change, pattern
):
    data, manifest, ledger, rights = reviewed_bundle(tmp_path)
    weights = spec(tmp_path)["scenario"]["inputs"]["persona_weights"]
    manifest["duration_capture"] = copy.deepcopy(manifest["rating_capture"]) | {
        "capture_id": "unit-durations"
    }
    data["visit_duration_estimates"] = [
        capture(data["attractions"][0], weights, 3600, capture_id="unit-durations")
    ]
    if change == "missing_provenance":
        del manifest["duration_capture"]
    elif change == "future":
        manifest["duration_capture"]["captured_at"] = "2026-10-17T00:00:00+00:00"
    elif change == "identity":
        data["visit_duration_estimates"][0]["capture_id"] = "other"
    elif change == "duplicate":
        data["visit_duration_estimates"] *= 2
    elif change == "unknown":
        data["visit_duration_estimates"][0]["provider_id"] = "unknown"
    else:
        data["visit_duration_estimates"][0]["visit_duration"]["seconds"] = 899
    save_reviewed(tmp_path, data, manifest, ledger, rights)
    with pytest.raises((EvidenceError, ValueError), match=pattern):
        Fixture(tmp_path)


def timed_metrics():
    return {
        "mode": "offline_pipeline",
        "input_snapshot": {"num_stops": 2},
        "explanation": {},
        "route": {
            "stops": [
                {
                    "type": "stop",
                    "provider_id": "synthetic:dst",
                    "travel_day": "2030-11-03",
                    "duration": 600,
                    "road_arrival_time": "2030-11-03T01:15:00-07:00",
                    "arrival_time": "2030-11-03T01:30:00-07:00",
                    "departure_time": "2030-11-03T01:30:00-08:00",
                    "wait_seconds": 900,
                },
                {
                    "type": "hotel",
                    "travel_day": "2030-11-03",
                    "duration": 1200,
                    "arrival_time": "2030-11-03T02:00:00-08:00",
                    "departure_time": "2030-11-04T09:00:00-08:00",
                },
                {
                    "type": "stop",
                    "provider_id": "synthetic:long",
                    "travel_day": "2030-11-04",
                    "duration": 1800,
                    "road_arrival_time": "2030-11-04T09:30:00-08:00",
                    "arrival_time": "2030-11-04T09:30:00-08:00",
                    "departure_time": "2030-11-04T12:30:00-08:00",
                    "wait_seconds": 0,
                },
                {"type": "end", "travel_day": "2030-11-04", "duration": 1800},
            ]
        },
        "itinerary": [{}, {}],
    }


def test_daily_active_time_counts_elapsed_variable_visits_waits_and_driving_without_hotel_rest():
    result = trip_evaluation(timed_metrics())
    assert METRIC_VERSION == "balanced-route-v5"
    assert result["schedule"]["visit_seconds"] == 14400
    daily = result["scenario_target"]
    assert daily["daily_active_seconds"] == {"2030-11-03": 6300, "2030-11-04": 14400}
    assert daily["maximum_daily_active_seconds"] == 14400
    assert daily["active_time_assessment_reason"] is None


@pytest.mark.parametrize(
    "patch",
    [
        {"duration": None},
        {"duration": True},
        {"duration": -1},
        {"arrival_time": None},
        {"departure_time": "2030-11-03T01:00:00-07:00"},
        {"road_arrival_time": "2030-11-03T02:00:00-08:00"},
        {"wait_seconds": 1},
        {"wait_seconds": True},
        {"road_arrival_time": None, "wait_seconds": None},
    ],
)
def test_incomplete_or_conflicting_timing_is_unassessed_and_not_a_partial_daily_total(patch):
    envelope = timed_metrics()
    envelope["route"]["stops"][0].update(patch)
    result = trip_evaluation(envelope)["scenario_target"]
    assert result["daily_active_seconds"]["2030-11-03"] is None
    assert result["daily_active_seconds"]["2030-11-04"] == 14400
    assert result["maximum_daily_active_seconds"] is None
    assert result["active_time_assessment_reason"] == "active_time_evidence_incomplete"
