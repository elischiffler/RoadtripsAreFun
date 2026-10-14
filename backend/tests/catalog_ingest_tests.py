import copy
import hashlib
import json

import pytest

from app.catalog.ingest import prepare
from app.catalog.normalize import normalize
from app.catalog.repository import nearby


def feature(**updates):
    result = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-122.4, 37.8]},
        "properties": {
            "id": "stable-1",
            "names": {"primary": "Test Museum"},
            "basic_category": "museum",
            "taxonomy": {"primary": "museum", "hierarchy": [["arts_and_entertainment", "museum"]]},
            "addresses": [{"country": "US", "region": "CA"}],
            "sources": [{"dataset": "meta", "record_id": "123"}, {"dataset": "Overture"}],
        },
    }
    result["properties"].update(updates)
    return result


def bundle(tmp_path, features):
    path = tmp_path / "input.jsonl"
    path.write_text("".join(json.dumps(f) + "\n" for f in features))
    license_path = tmp_path / "fixture-license.txt"
    license_path.write_text("Synthetic test license evidence")
    manifest = {
        "release": "2026-09-23.1",
        "schema_version": "1",
        "retrieved_at": "2026-10-14T00:00:00Z",
        "source_url": "s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "filters": {"country": "US"},
        "attribution": "Overture Maps; Meta",
        "licenses": {
            "CDLA-Permissive-2.0": {
                "path": str(license_path),
                "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            }
        },
    }
    return path, manifest


@pytest.mark.parametrize("region", ["CA", "AK", "HI", "DC"])
def test_us_scope_includes_non_contiguous_states(region):
    row, reason = normalize(feature(addresses=[{"country": "US", "region": region}]))
    assert reason is None
    assert row["region"] == region
    assert row["latitude"] == 37.8
    assert "daytime" in row["categories"]


@pytest.mark.parametrize(
    "address",
    [{"country": "CA", "region": "CA"}, {"country": "US", "region": "PR"}, {"country": "US"}, {}],
)
def test_strict_us_scope(address):
    assert normalize(feature(addresses=[address]))[1] == "country_region"


@pytest.mark.parametrize("coords", [[float("nan"), 30], [180, 91], [True, 40], [1]])
def test_rejects_invalid_coordinates(coords):
    f = feature()
    f["geometry"]["coordinates"] = coords
    assert normalize(f)[0] is None


def test_food_is_not_daytime_and_closures_are_excluded():
    row, _ = normalize(feature(basic_category="italian_restaurant", taxonomy={}))
    assert "food" in row["categories"] and "daytime" not in row["categories"]
    assert normalize(feature(operating_status="permanently_closed"))[0] is None


@pytest.mark.parametrize(
    "category", ["national_park", "park", "beach", "waterfall", "hiking_trail"]
)
def test_area_centroids_require_independently_verified_access_points(category):
    assert normalize(feature(basic_category=category, taxonomy={})) == (
        None,
        "access_point_required",
    )


def test_named_trailhead_is_point_destination_without_claiming_access():
    row, reason = normalize(feature(basic_category="trailhead", taxonomy={}))
    assert reason is None and "daytime" in row["categories"]
    assert "access_verified" not in row


def test_bounded_dry_run_checksum_duplicates_and_provenance(tmp_path):
    path, manifest = bundle(tmp_path, [feature(), feature()])
    rows, report = prepare(path, manifest)
    assert len(rows) == 1 and report["rejects"] == {"duplicate": 1}
    assert "raw" not in rows[0]
    with pytest.raises(ValueError, match="row ceiling"):
        prepare(path, manifest, max_rows=1)
    with pytest.raises(ValueError, match="byte/line"):
        prepare(path, manifest, max_bytes=10)
    manifest["sha256"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        prepare(path, manifest)


@pytest.mark.parametrize(
    "sources",
    [
        [{"dataset": "Overture"}],
        [{"dataset": "unknown"}],
        [{"dataset": "meta"}, {"dataset": "unknown"}],
    ],
)
def test_no_unreviewed_provenance(tmp_path, sources):
    path, manifest = bundle(tmp_path, [feature(sources=sources)])
    rows, report = prepare(path, manifest)
    assert not rows and report["rejects"] == {"unapproved_provenance": 1}


def test_conflicting_id_fails_instead_of_arbitrary_dedup(tmp_path):
    changed = copy.deepcopy(feature())
    changed["properties"]["names"]["primary"] = "Another"
    path, manifest = bundle(tmp_path, [feature(), changed])
    with pytest.raises(ValueError, match="conflicting"):
        prepare(path, manifest)


@pytest.mark.parametrize(
    "point,categories,radius,limit",
    [
        ([91, 0], ["daytime"], 5, 1),
        ([0, 0], ["foo"], 5, 1),
        ([0, 0], ["food"], 6, 1),
        ([0, 0], ["food"], 5, 61),
    ],
)
def test_lookup_rejects_unbounded_inputs_before_connecting(point, categories, radius, limit):
    with pytest.raises(ValueError):
        nearby(point, categories, radius, limit)


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        [],
        {"properties": []},
        {"geometry": []},
        {"geometry": {"coordinates": None}},
        feature(addresses=[None]),
        feature(names=[]),
        feature(taxonomy="invalid"),
        feature(sources=[None]),
        feature(websites="invalid"),
    ],
)
def test_malformed_feature_is_rejected(malformed):
    assert normalize(malformed)[0] is None


def test_evidence_timestamp_and_license_validation(tmp_path):
    f = feature(sources=[{"dataset": "meta", "update_time": "not-a-date"}])
    assert normalize(f)[1] == "evidence_date"
    f = feature(sources=[{"dataset": "meta", "update_time": "2026-09-01T02:00:00+02:00"}])
    assert normalize(f)[0]["source_updated_at"] == "2026-09-01T00:00:00+00:00"
    path, manifest = bundle(tmp_path, [feature()])
    manifest["licenses"]["CDLA-Permissive-2.0"]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="license/notice checksum"):
        prepare(path, manifest)


def test_foursquare_requires_notice(tmp_path):
    path, manifest = bundle(
        tmp_path, [feature(sources=[{"dataset": "Foursquare"}, {"dataset": "Overture"}])]
    )
    manifest["licenses"]["Apache-2.0"] = manifest["licenses"].pop("CDLA-Permissive-2.0")
    with pytest.raises(ValueError, match="license/notice requires"):
        prepare(path, manifest)


def test_reject_unofficial_source_url(tmp_path):
    path, manifest = bundle(tmp_path, [feature()])
    manifest["source_url"] = "https://unlicensed.example/data"
    with pytest.raises(ValueError, match="official pinned"):
        prepare(path, manifest)
