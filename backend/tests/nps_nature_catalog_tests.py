"""Synthetic source/review failures; retained authentic snapshots stay outside Git."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.catalog import nps_heritage, nps_nature, nps_public
from app.catalog.ingest import prepare
from tests.catalog_extraction_tests import load_script
from tests.nps_catalog_tests import evidence, source


def write(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle(tmp_path, monkeypatch):
    now = datetime.now(UTC).isoformat()
    data = source()
    data.update(
        siteCode="exam", name="Example National Recreation Area", url="https://www.nps.gov/exam/"
    )
    data["visitorCenters"][0].update(visitorCenterID=999999, name="Example Visitor Center")
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    operation = evidence(snapshots, data, "exam")
    index = tmp_path / "inventory.json"
    sha = write(
        index,
        {
            "rows": [
                {
                    "unit_code": "exam",
                    "fullname": data["name"],
                    "designation": "National Recreation Area",
                    "states": "CA",
                }
            ]
        },
    )
    monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", sha)
    monkeypatch.setattr(nps_nature, "REVIEWED_FACILITIES", {"exam": 999999})
    raw_directory = tmp_path / "driving"
    raw_directory.mkdir()
    response_path = raw_directory / "exam.json"
    response_sha = write(
        response_path,
        {
            "code": "Ok",
            "waypoints": [{"name": "Probe", "distance": 0}, {"name": "", "distance": 12}],
        },
    )
    driving = tmp_path / "driving-reviewed.json"
    drive_sha = write(
        driving,
        [
            {
                "source_id": "nps-public:exam:visitor-center",
                "checked_at": now,
                "checked_waypoint": "destination",
                "http_status": 200,
                "code": "Ok",
                "source_coordinates": [38.6165, -109.62],
                "snap_distance_m": 12,
                "road_name": "",
                "response_path": "driving/exam.json",
                "response_sha256": response_sha,
            }
        ],
    )
    b = {
        "profile": nps_nature.PROFILE,
        "inventory": {
            "url": nps_heritage.INDEX_URL,
            "path": str(index),
            "sha256": sha,
            "retrieved_at": now,
        },
        "inputs": {"exam": operation},
        "selections": {"exam": {"visitor_center_id": 999999}},
        "driving": {"path": str(driving), "sha256": drive_sha, "retrieved_at": now},
    }
    path = tmp_path / "bundle.json"
    bundle_sha = write(path, b)
    license_path = tmp_path / "rights.txt"
    license_path.write_text("Synthetic government-work rights evidence")
    manifest = {
        "schema_version": nps_public.SCHEMA,
        "release": "nps-public-" + datetime.now(UTC).date().isoformat(),
        "source_url": nps_nature.SOURCE_URL,
        "retrieved_at": now,
        "sha256": bundle_sha,
        "filters": {"arrival_profile": nps_nature.PROFILE},
        "attribution": nps_nature.ATTRIBUTION,
        "licenses": {
            "LicenseRef-US-Government-Work": {
                "path": str(license_path),
                "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            }
        },
    }
    return path, manifest, b


def test_nature_reuses_public_schema_and_explicit_facility_state_without_heritage_labels(
    tmp_path, monkeypatch
):
    path, manifest, _ = bundle(tmp_path, monkeypatch)
    rows, report = prepare(path, manifest)
    row = rows[0]
    assert manifest["schema_version"] == "nps-public-arrivals/1"
    assert row["source_id"] == "nps-public:exam:visitor-center"
    assert row["region"] == "UT"  # The deliberately different inventory state is unused.
    assert row["categories"] == ["daytime", "nature", "visitor_center"]
    assert "historic_site" not in row["categories"] and "national_park" not in row["categories"]
    assert report["primary_categories"] == {"nature": 1}
    assert row["provenance"][-1]["opening_hours_imported"] is False
    assert row["provenance"][-1]["driving_response_sha256"]
    assert row["provenance"][0]["cartographic_geometry_used"] is False
    assert all("Kaggle" not in p["dataset"] for p in row["provenance"])
    assert prepare(path, manifest, max_bytes=report["bytes"])[1]["accepted"] == 1
    with pytest.raises(ValueError, match="byte ceiling"):
        prepare(path, manifest, max_bytes=report["bytes"] - 1)


@pytest.mark.parametrize(
    "change",
    [
        "parking",
        "hq_state",
        "foreign",
        "boolean_coordinate",
        "dated_closure",
        "restricted_car",
        "closed",
        "origin_only",
        "wrong_point",
        "distant",
        "nan",
        "boolean_distance",
    ],
)
def test_uncertain_arrival_cannot_enter_nature_batch(tmp_path, monkeypatch, change):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    operation = b["inputs"]["exam"]
    data = json.loads(Path(operation["path"]).read_text())
    vc = data["visitorCenters"][0]
    if change == "parking":
        vc["amenities"] = []
    elif change == "hq_state":
        vc["physical_address"]["state_code"] = ""
    elif change == "foreign":
        vc["physical_address"]["country_code"] = "CA"
    elif change == "boolean_coordinate":
        vc["location"]["latitude"] = True
    elif change == "dated_closure":
        next(iter(vc["operatingHours"].values()))["exceptions"] = [
            {"date_start": "January 1", "date_end": "December 31", "schedule": [{"is_closed": 1}]}
        ]
    elif change == "restricted_car":
        vc["directions"] = "Mandatory shuttle. Staff parking only."
    elif change == "closed":
        vc["name"] = "Example Visitor Center Temporarily Closed"
    else:
        checks = json.loads(Path(b["driving"]["path"]).read_text())
        key, value = {
            "origin_only": ("checked_waypoint", "origin"),
            "wrong_point": ("source_coordinates", [0, 0]),
            "distant": ("snap_distance_m", 80),
            "nan": ("snap_distance_m", float("nan")),
            "boolean_distance": ("snap_distance_m", True),
        }[change]
        checks[0][key] = value
        b["driving"]["sha256"] = write(Path(b["driving"]["path"]), checks)
    operation["sha256"] = write(Path(operation["path"]), data)
    manifest["sha256"] = write(path, b)
    rows, report = prepare(path, manifest)
    assert not rows and sum(report["rejects"].values()) == 1


@pytest.mark.parametrize(
    "change",
    [
        "profile",
        "unselected_facility",
        "designation",
        "stale",
        "inventory_hash",
        "raw_missing",
        "raw_hash",
        "raw_road",
        "raw_distance",
        "raw_origin_only",
    ],
)
def test_uninspected_identity_or_changed_raw_evidence_fails_closed(tmp_path, monkeypatch, change):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    if change == "profile":
        b["profile"] = "unreviewed/1"
    elif change == "unselected_facility":
        b["selections"]["exam"]["visitor_center_id"] = 123
    elif change in {"designation", "inventory_hash"}:
        index = Path(b["inventory"]["path"])
        data = json.loads(index.read_text())
        data["rows"][0]["designation"] = "National Historic Site"
        b["inventory"]["sha256"] = write(index, data)
        if change == "designation":
            monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", b["inventory"]["sha256"])
    elif change == "stale":
        b["inputs"]["exam"]["retrieved_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    else:
        response_path = tmp_path / "driving/exam.json"
        if change == "raw_missing":
            response_path.unlink()
        elif change == "raw_hash":
            response_path.write_text("{}")
        else:
            response = json.loads(response_path.read_text())
            if change == "raw_road":
                response["waypoints"][1]["name"] = "Different Street"
            elif change == "raw_distance":
                response["waypoints"][1]["distance"] = 50
            else:
                response["waypoints"].pop()
            checks = json.loads(Path(b["driving"]["path"]).read_text())
            checks[0]["response_sha256"] = write(response_path, response)
            b["driving"]["sha256"] = write(Path(b["driving"]["path"]), checks)
    manifest["sha256"] = write(path, b)
    with pytest.raises(ValueError):
        prepare(path, manifest)


def test_reviewed_national_park_is_not_created_by_a_free_form_category(tmp_path, monkeypatch):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    b["selections"]["exam"]["primary_category"] = "national_parks"
    manifest["sha256"] = write(path, b)
    with pytest.raises(ValueError, match="outside the inspected selections"):
        prepare(path, manifest)
    del b["selections"]["exam"]["primary_category"]
    index = Path(b["inventory"]["path"])
    data = json.loads(index.read_text())
    data["rows"][0]["designation"] = "National Park"
    b["inventory"]["sha256"] = write(index, data)
    monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", b["inventory"]["sha256"])
    manifest["sha256"] = write(path, b)
    rows, report = prepare(path, manifest)
    assert report["primary_categories"] == {"national_parks": 1}
    assert "national_park" in rows[0]["categories"]


def test_offline_producer_rechecks_facts_and_publishes_all_or_none(tmp_path, monkeypatch):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    rows, _ = prepare(path, manifest)
    producer = load_script("catalog_nature_manifest")
    baseline_dir = Path(__file__).resolve().parents[2] / "docs/data/catalog-expansion-20261015"
    _, baseline_sha = producer.baseline(baseline_dir)
    review = {
        "schema_version": "roadtrips-nps-nature-review/1",
        "profile": nps_nature.PROFILE,
        "source_release": manifest["release"],
        "checked_at": manifest["retrieved_at"],
        "baseline_identity_sha256": baseline_sha,
        "inventory": b["inventory"],
        "driving": b["driving"],
        "batches": [
            {
                "id": "nature-01",
                "records": [
                    {
                        "unit_code": "exam",
                        "visitor_center_id": 999999,
                        "operation_evidence": b["inputs"]["exam"],
                        "row": rows[0],
                    }
                ],
            }
        ],
    }
    review_path = tmp_path / "review.json"
    write(review_path, review)
    output = tmp_path / "output"
    assert producer.build(tmp_path, review_path, baseline_dir, output)["accepted"] == 1
    with pytest.raises(ValueError, match="already exists"):
        producer.build(tmp_path, review_path, baseline_dir, output)
    review["batches"].append({**copy.deepcopy(review["batches"][0]), "id": "nature-02"})
    write(review_path, review)
    failed_output = tmp_path / "all-or-none"
    with pytest.raises(ValueError, match="duplicate natural unit"):
        producer.build(tmp_path, review_path, baseline_dir, failed_output)
    assert not list(failed_output.glob("*.json"))
    assert not list(failed_output.glob("*.jsonl"))


@pytest.mark.parametrize("change", ["baseline", "reviewed_point", "source_bytes"])
def test_producer_rejects_changed_review_or_evidence_before_publication(
    tmp_path, monkeypatch, change
):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    rows, _ = prepare(path, manifest)
    producer = load_script("catalog_nature_manifest")
    baseline_dir = Path(__file__).resolve().parents[2] / "docs/data/catalog-expansion-20261015"
    _, baseline_sha = producer.baseline(baseline_dir)
    review = {
        "schema_version": "roadtrips-nps-nature-review/1",
        "profile": nps_nature.PROFILE,
        "source_release": manifest["release"],
        "checked_at": manifest["retrieved_at"],
        "baseline_identity_sha256": baseline_sha,
        "inventory": b["inventory"],
        "driving": b["driving"],
        "batches": [
            {
                "id": "nature-01",
                "records": [
                    {
                        "unit_code": "exam",
                        "visitor_center_id": 999999,
                        "operation_evidence": b["inputs"]["exam"],
                        "row": rows[0],
                    }
                ],
            }
        ],
    }
    if change == "baseline":
        review["baseline_identity_sha256"] = "changed"
    elif change == "reviewed_point":
        review["batches"][0]["records"][0]["row"]["latitude"] += 0.01
    else:
        Path(b["inputs"]["exam"]["path"]).write_text("{}")
    review_path = tmp_path / "review.json"
    write(review_path, review)
    output = tmp_path / "refused"
    with pytest.raises(ValueError):
        producer.build(tmp_path, review_path, baseline_dir, output)
    assert not list(output.glob("*.json")) and not list(output.glob("*.jsonl"))


def test_public_nature_29_matches_inspected_facilities_and_excludes_all_prior_units():
    root = Path(__file__).resolve().parents[2] / "docs/data/catalog-expansion-20261015"
    producer = load_script("catalog_nature_manifest")
    known, digest = producer.baseline(root)
    review = json.loads((root / "nps-nature-29-review.json").read_text())
    assert review["baseline_identity_sha256"] == digest
    records = [r for b in review["batches"] for r in b["records"]]
    preview = [
        json.loads(line)
        for line in (root / "reviewed-nps-nature-29.preview.jsonl").read_text().splitlines()
    ]
    assert len(records) == len(preview) == len({r["source_id"] for r in preview}) == 29
    assert {r["unit_code"] for r in records} == set(nps_nature.REVIEWED_FACILITIES)
    assert preview == [r["row"] for r in records]
    baseline_ids = {r["source_id"] for r in known}
    baseline_units = {
        r["source_id"].split(":")[1]
        for r in known
        if r["source_id"].startswith(("nps:", "nps-public:", "nps-heritage:"))
    }
    for item in records:
        row, code = item["row"], item["unit_code"]
        assert code not in baseline_units and row["source_id"] not in baseline_ids
        assert row["source_id"] == f"nps-public:{code}:visitor-center"
        assert item["visitor_center_id"] == nps_nature.REVIEWED_FACILITIES[code]
        assert row["provenance"][-1]["auto_parking_listed"] is True
        assert row["provenance"][-1]["opening_hours_imported"] is False
        assert (
            row["provenance"][-1]["coordinate_source"]
            == "original NPS visitor-facility coordinate; unchanged"
        )
        assert "historic_site" not in row["categories"]
        assert (
            item["operation_evidence"]["url"]
            == f"https://www.nps.gov/{code}/structured_data_{code}.json"
        )


def portable_bundle(tmp_path, monkeypatch, *, historical_colons=False):
    path, manifest, b = bundle(tmp_path, monkeypatch)
    old_checks = json.loads(Path(b["driving"]["path"]).read_text())
    raw = tmp_path / "driving/exam.json"
    if not historical_colons:
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "exam.json").write_bytes(raw.read_bytes())
        old_checks[0]["response_path"] = "legacy/exam.json"
        b["driving"]["sha256"] = write(Path(b["driving"]["path"]), old_checks)
        manifest["sha256"] = write(path, b)
        prior_rows, _ = prepare(path, manifest)
    else:
        # Historical metadata may contain colons; no colon-named file is ever
        # created, so this regression fixture also runs on Windows itself.
        old_checks[0]["response_path"] = "driving/nps-public:exam:visitor-center.json"
        prior_rows = None
    original = tmp_path / "driving-original.json"
    old_sha = write(original, old_checks)
    b["driving_original"] = {**b["driving"], "path": str(original), "sha256": old_sha}
    active = [
        {**c, "response_path": nps_nature.portable_receipt_path(c["source_id"])} for c in old_checks
    ]
    b["driving"]["sha256"] = write(Path(b["driving"]["path"]), active)
    manifest["sha256"] = write(path, b)
    return path, manifest, b, prior_rows


def test_portable_filenames_preserve_original_rows_and_provenance(tmp_path, monkeypatch):
    path, manifest, b, prior = portable_bundle(tmp_path, monkeypatch)
    assert b["driving"]["sha256"] != b["driving_original"]["sha256"]
    rows, report = prepare(path, manifest)
    assert rows == prior and report["accepted"] == 1
    assert rows[0]["provenance"][-1]["driving_evidence_sha256"] == b["driving_original"]["sha256"]
    assert prepare(path, manifest, max_bytes=report["bytes"])[1]["accepted"] == 1
    with pytest.raises(ValueError, match="byte ceiling"):
        prepare(path, manifest, max_bytes=report["bytes"] - 1)


def test_historical_colon_reference_uses_the_portable_active_index(tmp_path, monkeypatch):
    path, manifest, b, _ = portable_bundle(tmp_path, monkeypatch, historical_colons=True)
    rows, report = prepare(path, manifest)
    assert report["accepted"] == 1
    assert rows[0]["provenance"][-1]["driving_evidence_sha256"] == b["driving_original"]["sha256"]
    assert not (tmp_path / "driving/nps-public:exam:visitor-center.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("response_path", "driving/nps-public:exam:visitor-center.json"),
        ("response_path", "driving/other.json"),
        ("source_coordinates", [0, 0]),
        ("checked_at", "2020-01-01T00:00:00+00:00"),
        ("response_sha256", "changed"),
    ],
)
def test_portable_index_cannot_change_receipt_identity_or_routing_facts(
    tmp_path, monkeypatch, field, value
):
    path, manifest, b, _ = portable_bundle(tmp_path, monkeypatch, historical_colons=True)
    active = json.loads(Path(b["driving"]["path"]).read_text())
    active[0][field] = value
    b["driving"]["sha256"] = write(Path(b["driving"]["path"]), active)
    manifest["sha256"] = write(path, b)
    with pytest.raises(ValueError, match="changes acquisition facts"):
        prepare(path, manifest)


def test_public_portable_receipt_names_are_valid_windows_paths():
    from pathlib import PureWindowsPath

    for code in nps_nature.REVIEWED_FACILITIES:
        name = nps_nature.portable_receipt_path(f"nps-public:{code}:visitor-center")
        windows = PureWindowsPath(name)
        assert not windows.drive and not windows.is_absolute()
        assert not windows.is_reserved()
        assert all(not any(c in part for c in '<>:"/\\|?*') for part in windows.parts)
