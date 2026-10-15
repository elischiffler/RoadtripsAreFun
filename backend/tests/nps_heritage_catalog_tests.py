"""Synthetic heritage admission; actual government snapshots remain outside Git."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from app.catalog import nps_heritage
from app.catalog.identity import identity
from app.catalog.ingest import prepare
from tests.nps_catalog_tests import evidence, source


def bundle(tmp_path, monkeypatch, *, change=None):
    now = datetime.now(UTC).isoformat()
    d = source()
    d.update(
        siteCode="exam", name="Example National Historic Site", url="https://www.nps.gov/exam/"
    )
    d["visitorCenters"][0]["name"] = "Example Visitor Center"
    vc = d["visitorCenters"][0]
    if change == "hq_only":
        vc["physical_address"]["state_code"] = ""
    if change == "foreign":
        vc["physical_address"]["country_code"] = "CA"
    if change == "parking":
        vc["amenities"] = []
    if change == "closed_name":
        vc["name"] = "Example Visitor Center (Temporarily Closed)"
    if change == "bool_coord":
        vc["location"]["latitude"] = True
    index = {
        "rows": [
            {
                "unit_code": "exam",
                "fullname": d["name"],
                "designation": "National Historic Site",
                "states": "ca",
            }
        ]
    }
    if change == "wrong_designation":
        index["rows"][0]["designation"] = "National Park"
    index_path = tmp_path / "inventory.json"
    index_path.write_text(json.dumps(index))
    index_sha = hashlib.sha256(index_path.read_bytes()).hexdigest()
    monkeypatch.setattr(nps_heritage, "INDEX_SHA256", index_sha)
    snap = evidence(tmp_path, d, "exam")
    driving = [
        {
            "source_id": "nps-heritage:exam",
            "checked_at": now,
            "checked_waypoint": "destination",
            "http_status": 200,
            "code": "Ok",
            "source_coordinates": [38.6165, -109.62],
            "snap_distance_m": 12,
            "road_name": "",
        }
    ]
    if change == "origin":
        driving[0]["checked_waypoint"] = "origin"
    if change == "distance":
        driving[0]["snap_distance_m"] = 90
    if change == "wrong_point":
        driving[0]["source_coordinates"] = [0, 0]
    drive = tmp_path / "driving.json"
    drive.write_text(json.dumps(driving))
    b = {
        "inventory": {
            "url": nps_heritage.INDEX_URL,
            "path": str(index_path),
            "sha256": index_sha,
            "retrieved_at": now,
        },
        "inputs": {"exam": snap},
        "selections": {"exam": {"visitor_center_id": 71, "primary_category": "landmarks"}},
        "driving": {
            "path": str(drive),
            "sha256": hashlib.sha256(drive.read_bytes()).hexdigest(),
            "retrieved_at": now,
        },
    }
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(b))
    license_path = tmp_path / "rights.txt"
    license_path.write_text("Synthetic government-work rights evidence")
    m = {
        "schema_version": nps_heritage.SCHEMA,
        "release": "nps-heritage-" + datetime.now(UTC).date().isoformat(),
        "source_url": nps_heritage.SOURCE_URL,
        "retrieved_at": now,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "filters": {"explicit_visitor_facilities": True},
        "attribution": nps_heritage.ATTRIBUTION,
        "licenses": {
            "LicenseRef-US-Government-Work": {
                "path": str(license_path),
                "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            }
        },
    }
    return p, m


def test_heritage_uses_actual_facility_state_and_point_without_kaggle_or_park_labels(
    tmp_path, monkeypatch
):
    p, m = bundle(tmp_path, monkeypatch)
    rows, report = prepare(p, m)
    r = rows[0]
    assert (
        report["accepted"] == 1 and r["region"] == "UT"
    )  # Inventory label was CA, deliberately unused.
    assert identity(r["source_id"]) == ("nps-heritage:exam", "nps-heritage")
    assert r["latitude"] == 38.6165 and r["longitude"] == -109.62
    assert "historic_site" in r["categories"] and "national_park" not in r["categories"]
    assert all("Kaggle" not in x["dataset"] for x in r["provenance"])
    assert r["provenance"][0]["cartographic_geometry_used"] is False
    assert r["source_updated_at"] is None and r["provenance"][-1]["driving_snap_distance_m"] == 12


@pytest.mark.parametrize(
    "change",
    [
        "hq_only",
        "foreign",
        "parking",
        "closed_name",
        "bool_coord",
        "origin",
        "distance",
        "wrong_point",
    ],
)
def test_uncertain_heritage_arrivals_are_withheld(tmp_path, monkeypatch, change):
    p, m = bundle(tmp_path, monkeypatch, change=change)
    rows, report = prepare(p, m)
    assert rows == [] and sum(report["rejects"].values()) == 1


def test_other_designations_and_wrong_evidence_cannot_be_reclassified(tmp_path, monkeypatch):
    p, m = bundle(tmp_path, monkeypatch, change="wrong_designation")
    with pytest.raises(ValueError, match="heritage designation"):
        prepare(p, m)


def test_heritage_keeps_source_and_aggregate_limits(tmp_path, monkeypatch):
    p, m = bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="byte ceiling"):
        prepare(p, m, max_bytes=100)
    m["sha256"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        prepare(p, m)
