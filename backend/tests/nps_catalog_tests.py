"""Synthetic NPS admission cases; authentic snapshots are retained outside Git."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.catalog import nps, nps_public


def source():
    return {
        "siteCode": "arch",
        "name": "Arches National Park",
        "physicalAddressCountryCode": "US",
        "physicalAddressStateCode": "UT",
        "url": "https://www.nps.gov/arch/",
        "visitorCenters": [
            {
                "visitorCenterID": 71,
                "name": "Arches Visitor Center",
                "location": {"latitude": "38.6165", "longitude": "-109.6200"},
                "physical_address": {"state_code": "UT", "line_1": "US 191"},
                "directions": "Drive north on US 191 and enter the park.",
                "amenities": ["Parking - Auto"],
                "description": "Official visitor facility",
                "siteURL": "",
                "operatingHours": {
                    "1": {
                        "description": "Open daily except holidays",
                        "label": "Visitor hours",
                        "hours": [
                            {"is_closed": 0, "time_open": "8:00 AM", "time_close": "5:00 PM"}
                        ],
                    }
                },
            }
        ],
    }


def park():
    return {
        "Park Code": "ARCH",
        "Park Name": "Arches National Park",
        "State": "UT",
        "Latitude": "38.68",
        "Longitude": "-109.57",
    }


def evidence(tmp_path, data, code="arch"):
    raw = json.dumps(data).encode()
    p = tmp_path / (code + ".json")
    p.write_bytes(raw)
    return {
        "url": f"https://www.nps.gov/{code}/structured_data_{code}.json",
        "path": str(p),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


def test_nps_uses_visitor_arrival_not_kaggle_park_center(tmp_path):
    d = source()
    e = evidence(tmp_path, d)
    row, reason = nps.normalize_arrival(park(), d, {"visitor_center_id": 71}, e, e["retrieved_at"])
    assert reason is None and row["source_id"] == "nps:arch"
    assert row["latitude"] == 38.6165 and row["latitude"] != float(park()["Latitude"])
    assert row["provenance"][1]["record_id"] == "71"
    assert row["source_updated_at"] is None
    assert row["url"] == "https://www.nps.gov/arch/"
    assert "images" not in row and "operatingHours" not in row


@pytest.mark.parametrize(
    "change,reason",
    [
        ("remote", "park_requires_non_driving_access"),
        ("closed", "closure_evidence"),
        ("hours", "schedule_unknown_or_closed"),
        ("road", "car_arrival_unverified"),
        ("coords", "coordinates"),
        ("state", "arrival_state_unresolved"),
        ("museum", "museum_classification_unverified"),
    ],
)
def test_uncertain_or_unusable_nps_arrivals_are_excluded(tmp_path, change, reason):
    d, p, select = source(), park(), {"visitor_center_id": 71}
    vc = d["visitorCenters"][0]
    if change == "remote":
        p["Park Code"] = "DRTO"
    if change == "closed":
        vc["description"] = "Temporarily closed due to structural repairs"
    if change == "hours":
        vc["operatingHours"]["1"]["hours"][0]["is_closed"] = 1
    if change == "road":
        vc["amenities"] = []
        vc["directions"] = "Take a boat to this facility."
    if change == "coords":
        vc["location"]["latitude"] = "NaN"
    if change == "state":
        vc["physical_address"]["state_code"] = ""
        p["State"] = "UT, CO"
    if change == "museum":
        select["primary_category"] = "museums"
    e = evidence(tmp_path, d)
    assert nps.normalize_arrival(p, d, select, e, e["retrieved_at"])[1] == reason


def test_nps_museum_requires_actual_official_museum_identity(tmp_path):
    d = source()
    d["visitorCenters"][0]["name"] = "Longmire Museum"
    e = evidence(tmp_path, d)
    row, reason = nps.normalize_arrival(
        park(), d, {"visitor_center_id": 71, "primary_category": "museums"}, e, e["retrieved_at"]
    )
    assert reason is None and "museum" in row["categories"]


def test_nps_snapshot_integrity_identity_and_date(tmp_path):
    d = source()
    e = evidence(tmp_path, d)
    assert nps.read_snapshot(e, "arch")[0]["siteCode"] == "arch"
    bad = copy.deepcopy(e)
    bad["retrieved_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="30 days"):
        nps.read_snapshot(bad, "arch")
    bad = copy.deepcopy(e)
    bad["url"] = "https://example.test/arch.json"
    with pytest.raises(ValueError, match="published"):
        nps.read_snapshot(bad, "arch")
    bad = copy.deepcopy(e)
    bad["sha256"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        nps.read_snapshot(bad, "arch")


def test_multiple_beach_parking_lots_count_as_one_destination(tmp_path):
    d = {
        "siteCode": "cana",
        "physicalAddressCountryCode": "US",
        "physicalAddressStateCode": "FL",
        "url": "https://www.nps.gov/cana/",
        "parkingLots": [],
    }
    for i, spaces in [(1, 20), (2, 40)]:
        d["parkingLots"].append(
            {
                "name": f"Playalinda Beach Parking Lot {i}",
                "lotID": f"00000000-0000-4000-8000-{i:012d}",
                "maintainer": "NPS",
                "latitude": "28.645",
                "longitude": "-80.683",
                "totalParkingSpaces": spaces,
                "liveStatusIsActive": 0,
                "description": "Beach access parking",
            }
        )
    e = evidence(tmp_path, d, "cana")
    raw = json.dumps({"inputs": {"cana": e}}).encode()
    p = tmp_path / "bundle.json"
    p.write_bytes(raw)
    m = {
        "source_url": nps_public.SOURCE_URL,
        "attribution": nps_public.ATTRIBUTION,
        "release": "nps-public-2026-10-15",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    rows, report = nps_public.prepare(p, m, max_rows=500, max_bytes=1024 * 1024)
    assert len(rows) == 1 and report["duplicate_arrivals"] == 1
    assert rows[0]["provenance"][0]["documented_car_spaces"] == 40
    assert rows[0]["provenance"][0]["operating_status"].startswith("unknown")
    assert rows[0]["latitude"] == 28.645
    d["physicalAddressStateCode"] = "MS"
    e = evidence(tmp_path, d, "cana")
    raw = json.dumps({"inputs": {"cana": e}}).encode()
    p.write_bytes(raw)
    m["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="state/evidence"):
        nps_public.prepare(p, m, max_rows=500, max_bytes=1024 * 1024)
