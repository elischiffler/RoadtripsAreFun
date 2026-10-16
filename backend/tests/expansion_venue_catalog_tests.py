"""Raw destination evidence is required for the newly inspected venues."""

import hashlib
import json
from pathlib import Path

import pytest

from app.catalog.ingest import prepare
from tests.arrival_review_catalog_tests import replace, reviewed

LUCKY_STRIKE = "440a13bb-c07b-4b4f-87aa-8dcbe7b691f1"


def venue(tmp_path):
    path, manifest, ident = reviewed(tmp_path, LUCKY_STRIKE)
    entry = manifest["arrival_review"]["entries"][ident]
    summary = json.loads(Path(entry["driving"]["path"]).read_text())
    raw = json.dumps(
        {
            "code": "Ok",
            "waypoints": [
                {"name": "origin", "distance": 0},
                {
                    "name": summary[0]["road_name"],
                    "distance": summary[0]["snap_distance_m"],
                },
            ],
        }
    ).encode()
    target = tmp_path / "raw-response.json"
    target.write_bytes(raw)
    entry["raw_driving"] = {
        "path": str(target),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": summary[0]["checked_at"],
    }
    summary[0]["response_sha256"] = entry["raw_driving"]["sha256"]
    replace(entry["driving"], json.dumps(summary).encode())
    return path, manifest, entry


def test_public_sports_bar_category_reaches_the_existing_evening_query_group(tmp_path):
    path, manifest, _ = venue(tmp_path)
    rows, _ = prepare(path, manifest)
    row = rows[0]
    assert "nightlife" in row["categories"]
    assert row["provenance"][-1]["additional_publisher_categories"] == ["nightlife"]
    assert row["provenance"][-1]["opening_hours_imported"] is False
    assert "On-site parking is unverified" in row["provenance"][-1]["limitations"]


@pytest.mark.parametrize("change", ["code", "waypoints", "road", "distance", "hash"])
def test_changed_raw_receipt_cannot_be_cleared_by_a_successful_summary(tmp_path, change):
    path, manifest, entry = venue(tmp_path)
    raw = json.loads(Path(entry["raw_driving"]["path"]).read_text())
    if change == "hash":
        entry["raw_driving"]["sha256"] = "0" * 64
    else:
        if change == "code":
            raw["code"] = "NoRoute"
        if change == "waypoints":
            raw["waypoints"] = raw["waypoints"][:1]
        if change == "road":
            raw["waypoints"][-1]["name"] = "Different street"
        if change == "distance":
            raw["waypoints"][-1]["distance"] = 200
        replace(entry["raw_driving"], json.dumps(raw).encode())
    with pytest.raises(ValueError):
        prepare(path, manifest)
