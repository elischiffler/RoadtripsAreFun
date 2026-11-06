"""Offline campaign and deterministic persona regressions; synthetic inputs only."""

import copy
import hashlib
import json
import socket
from pathlib import Path

import pytest

from app.agent.persona import ATTRIBUTE_KEYS
from app.catalog import personas, usfs_current
from app.routing.sources.persona_candidates import LocationProfile
from tests.catalog_extraction_tests import load_script
from tests.catalog_usfs_current_tests import bundle

campaign = load_script("catalog_expansion_campaign")
capture = load_script("catalog_test_routes")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network is forbidden in campaign regressions")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def setup(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    _, path, write = bundle(source)
    manifest = write()
    Path(str(path) + ".manifest.json").write_text(json.dumps(manifest))
    rows, report = usfs_current.prepare(path, manifest)
    monkeypatch.setattr(campaign, "baseline", lambda: ([], set()))
    root = tmp_path / "routes"
    root.mkdir()
    body = json.dumps(
        {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-120, 39.9], [-120, 40.1]],
                    }
                }
            ],
        }
    ).encode()
    (root / "route.json").write_bytes(body)
    (root / "index.json").write_text(
        json.dumps(
            {
                "routes": [{"id": "fixture", "response_path": "route.json"}],
                "receipts": [
                    {
                        "path": "route.json",
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "status": 200,
                        "url": "https://router.project-osrm.org/route/v1/driving/-120,39.9;-120,40.1",
                    }
                ],
            }
        )
    )
    return path, manifest, rows[0], report["calendar_entries"][0], root / "index.json"


def test_persona_matches_existing_schema_separates_inference_and_preserves_unknowns(
    tmp_path, monkeypatch
):
    _, manifest, row, entry, _ = setup(tmp_path, monkeypatch)
    original = copy.deepcopy((row, entry))
    profile = personas.build(
        row, entry, release=manifest["release"], attribution=manifest["attribution"]
    )
    typed = LocationProfile.model_validate(profile["location_profile"])
    assert set(typed.attribute_ratings.model_dump()) == set(ATTRIBUTE_KEYS)
    assert typed.coordinates == [40, -120]
    assert typed.activities == []
    assert typed.attribute_ratings.nature == 0.9
    assert typed.attribute_ratings.crowd_avoidance == 0.5
    assert typed.attribute_ratings.hiking_outdoors == 0.5  # Generic trailheads can be motorized.
    assert profile["inferred_traveler_fit"]["suggested_activities"]
    assert "inferred" == profile["validation_scope"]["traveler_fit"]
    for key in (
        "cost",
        "accessibility",
        "parking_availability",
        "reservation_availability",
        "live_operating_status",
    ):
        assert profile["practical_context"][key] is None
    assert (row, entry) == original


def test_opt_in_personas_survive_source_replay_and_existing_repository_projection(
    tmp_path, monkeypatch
):
    path, manifest, row, _, _ = setup(tmp_path, monkeypatch)
    legacy = copy.deepcopy(row)
    manifest["persona_enrichment"] = personas.VERSION
    rows, _ = usfs_current.prepare(path, manifest)
    assert rows[0]["provenance"][:-1] == legacy["provenance"]
    stored = rows[0]["provenance"][-1]
    assert stored["attribute_ratings"]["nature"] == 0.9
    assert "estimates" in stored["method"]["ratings_source"]
    assert personas.facts(rows[0]["provenance"]) == {
        "description": stored["description"],
        "activities": [],
    }
    assert usfs_current.prepare(path, manifest)[0] == rows
    assert usfs_current.prepare(
        path, {key: value for key, value in manifest.items() if key != "persona_enrichment"}
    )[0] == [legacy]


def test_profile_source_preserves_originals_and_is_replayed_by_existing_addition_adapter(
    tmp_path, monkeypatch
):
    path, manifest, row, _, route = setup(tmp_path, monkeypatch)
    original = path.read_bytes(), Path(str(path) + ".manifest.json").read_bytes()
    review = tmp_path / "arrival.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": "roadtrips-usfs-arrival-review/1",
                "source_bundle_sha256": manifest["sha256"],
                "records": [
                    {
                        "source_id": row["source_id"],
                        "decision": "reviewed_no_additional_conflict_observed",
                        "reason": "Synthetic review fixture",
                    }
                ],
            }
        )
    )
    target = path.with_name("profiled.json")
    assert campaign.profile_source(path, review, target)["accepted"] == 1
    with pytest.raises(ValueError, match="exists"):
        campaign.profile_source(path, review, target)
    assert original == (path.read_bytes(), Path(str(path) + ".manifest.json").read_bytes())
    result = campaign.replay([("usfs-current", target)], route, tmp_path / "reviewed")
    assert result["new_places"] == 1
    added = json.loads((tmp_path / "reviewed/additions.preview.json").read_bytes())[0]
    assert personas.facts(added["provenance"])["description"]


@pytest.mark.parametrize(
    "decision", ["hold", "missing", "reviewed_no_additional_conflict_observed"]
)
def test_independent_review_only_excludes_and_is_bound_to_original_source(
    tmp_path, monkeypatch, decision
):
    path, manifest, row, _, _ = setup(tmp_path, monkeypatch)
    ledger = {
        "schema_version": "roadtrips-usfs-arrival-review/1",
        "source_bundle_sha256": manifest["sha256"],
        "records": [
            {
                "source_id": "other" if decision == "missing" else row["source_id"],
                "decision": "hold"
                if decision == "hold"
                else "reviewed_no_additional_conflict_observed",
                "reason": "unresolved public approach",
            }
        ],
    }
    review = path.parent / "review.json"
    review.write_text(json.dumps(ledger))
    manifest["arrival_review"] = {
        "path": review.name,
        "sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
    }
    rows, report = usfs_current.prepare(path, manifest)
    assert len(rows) == (1 if decision == "reviewed_no_additional_conflict_observed" else 0)
    assert (
        report["rejects"]
        if not rows
        else rows[0]["provenance"][0]["independent_arrival_review_sha256"]
    )
    review.write_text("{}")
    with pytest.raises(ValueError, match="checksum|SHA|hash"):
        usfs_current.prepare(path, manifest)


@pytest.mark.parametrize(
    "qualification",
    [
        "Walk-in trailhead. Park at the visitor center.",
        "Take a paid shuttle to the trailhead.",
        "All visitors must have a BWCAW permit prior to hiking.",
        "GPS: 39 degrees north, 82 degrees west.",
    ],
)
def test_road_snap_never_overrides_unresolved_source_access(tmp_path, monkeypatch, qualification):
    from datetime import date

    from tests.catalog_usfs_current_tests import inputs

    a, b, shapes = inputs()
    a["directions"] += " " + qualification
    result, reason = usfs_current.qualify(
        a, b, shapes, date(2026, 10, 21), primary_publication=True
    )
    assert result is None and reason == "unresolved_published_access_qualification"


@pytest.mark.parametrize("change", ["identity", "category", "evidence"])
def test_unreviewed_persona_inputs_fail_closed(tmp_path, monkeypatch, change):
    _, manifest, row, entry, _ = setup(tmp_path, monkeypatch)
    if change == "identity":
        entry["source_id"] = "other"
    elif change == "category":
        row["categories"] = ["unreviewed"]
    else:
        row["provenance"] = []
    with pytest.raises(ValueError):
        personas.build(row, entry, release=manifest["release"], attribution=manifest["attribution"])


def test_original_source_replay_is_deterministic_and_never_overwrites(tmp_path, monkeypatch):
    path, _, row, _, route = setup(tmp_path, monkeypatch)
    output = tmp_path / "review"
    result = campaign.replay([("usfs-current", path)], route, output)
    assert result["new_places"] == result["new_personas"] == 1
    assert result["corridors_after"] == {"fixture": 1}
    assert json.loads((output / "additions.preview.json").read_bytes()) == [row]
    with pytest.raises(ValueError, match="already exists"):
        campaign.replay([("usfs-current", path)], route, output)
    second = tmp_path / "again"
    campaign.replay([("usfs-current", path)], route, second)
    for file in output.iterdir():
        assert file.read_bytes() == (second / file.name).read_bytes()


def test_corrupted_original_and_existing_native_identity_never_publish(tmp_path, monkeypatch):
    path, _, row, _, route = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        campaign, "baseline", lambda: ([dict(row, source_id="usfs:old-portal")], set())
    )
    output = tmp_path / "held"
    with pytest.raises(ValueError, match="no admitted additions"):
        campaign.replay([("usfs-current", path)], route, output)
    assert not output.exists()
    monkeypatch.setattr(campaign, "baseline", lambda: ([], set()))
    (path.parent / "facility.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum|SHA|hash"):
        campaign.replay([("usfs-current", path)], route, output)
    assert not output.exists()


@pytest.mark.parametrize("change", ["host", "credentials", "coordinates", "identity", "count"])
def test_custom_capture_rejects_invalid_requests_before_any_network(tmp_path, change):
    specs = campaign.specs()[:1]
    if change == "host":
        specs[0]["url"] = specs[0]["url"].replace("router.project-osrm.org", "other.example")
    elif change == "credentials":
        specs[0]["url"] = specs[0]["url"].replace("https://", "https://user:secret@")
    elif change == "coordinates":
        specs[0]["endpoint_coordinates_lat_lon"][0] = [float("nan"), 2]
    elif change == "identity":
        specs[0]["id"] = "../escape"
    else:
        specs *= 17
    with pytest.raises(ValueError):
        capture.acquire(
            tmp_path / "bad", route_specs=specs, request_get=lambda *a, **k: pytest.fail("network")
        )
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("ids", [[], ["x"], ["1", "1"], [str(x) for x in range(251)]])
def test_explicit_native_shortlists_cannot_raise_acquisition_bounds(tmp_path, ids):
    with pytest.raises(ValueError, match="shortlist"):
        usfs_current.acquire(
            tmp_path / "bad", parent_rows=[], routes_index=None, route_root=None, site_ids=ids
        )
    assert not (tmp_path / "bad").exists()
