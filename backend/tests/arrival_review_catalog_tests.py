"""Synthetic current-arrival cases; authentic publisher pages remain outside Git."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.catalog import arrival_review
from app.catalog.ingest import prepare
from tests.catalog_extraction_tests import load_script
from tests.catalog_ingest_tests import bundle, feature


def reviewed(tmp_path, source_id=None):
    now = datetime.now(UTC).isoformat()
    source_id = source_id or next(iter(arrival_review.PROFILES))
    profile = arrival_review.PROFILES[source_id]
    f = feature(
        id=source_id,
        names={"primary": profile["name"]},
        websites=["https://www." + profile["host"] + "/"],
        addresses=[{"country": "US", "region": profile["region"], "freeform": profile["address"]}],
    )
    lon, lat = (
        [-122.32289613, 47.59825849] if profile["region"] == "WA" else [-157.82149954, 21.26582513]
    )
    f["geometry"]["coordinates"] = [lon, lat]
    p, m = bundle(tmp_path, [f])
    m["schema_version"] = "roadtrips-overture-places-v1"

    def retained(name, raw, url=None):
        path = tmp_path / name
        path.write_bytes(raw)
        e = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "retrieved_at": now}
        if url:
            e["url"] = url
        return e

    pages = {
        url: retained(f"publisher-{i}.html", ("<p>" + "; ".join(phrases) + "</p>").encode(), url)
        for i, (url, phrases) in enumerate(profile["pages"].items())
    }
    driving = retained(
        "driving.json",
        json.dumps(
            [
                {
                    "source_id": source_id,
                    "checked_at": now,
                    "checked_waypoint": "destination",
                    "http_status": 200,
                    "code": "Ok",
                    "source_coordinates": [lat, lon],
                    "snap_distance_m": min(11.2, profile["distance_m"]),
                    "road_name": sorted(profile["roads"])[0],
                }
            ]
        ).encode(),
    )
    m["arrival_review"] = {
        "schema_version": arrival_review.SCHEMA,
        "entries": {source_id: {"profile": profile["profile"], "pages": pages, "driving": driving}},
    }
    return p, m, source_id


def replace(evidence, raw):
    Path(evidence["path"]).write_bytes(raw)
    evidence["sha256"] = hashlib.sha256(raw).hexdigest()


def test_explicit_review_preserves_point_and_adds_current_provenance(tmp_path):
    p, m, key = reviewed(tmp_path)
    original, _ = prepare(p, {k: v for k, v in m.items() if k != "arrival_review"})
    rows, report = prepare(p, m)
    assert rows[0]["source_id"] == key and rows[0]["latitude"] == original[0]["latitude"]
    assert rows[0]["provenance"][:-1] == original[0]["provenance"]
    provenance = rows[0]["provenance"][-1]
    assert provenance["profile"] == "wing-luke/1"
    assert "No on-site parking" in provenance["limitations"]
    assert provenance["opening_hours_imported"] is False
    assert report["arrival_reviewed"] == 1 and report["bytes"] > p.stat().st_size


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "coverage",
        "profile",
        "publisher",
        "closure",
        "content",
        "hash",
        "stale",
        "origin_only",
        "coordinates",
        "distance",
        "road",
        "byte_limit",
    ],
)
def test_uncertain_review_prevents_admission(tmp_path, change):
    p, m, key = reviewed(tmp_path)
    review = m["arrival_review"]
    entry = review["entries"][key]
    page = next(iter(entry["pages"].values()))
    if change == "schema":
        review["schema_version"] = "unknown"
    if change == "coverage":
        review["entries"]["unsupported"] = {}
    if change == "profile":
        entry["profile"] = "unreviewed/1"
    if change == "publisher":
        page["url"] = "https://example.test/visit"
    if change == "closure":
        replace(page, Path(page["path"]).read_bytes() + b"<p>Temporarily closed.</p>")
    if change == "content":
        replace(page, b"<p>Changed publisher information</p>")
    if change == "hash":
        page["sha256"] = "wrong"
    if change == "stale":
        page["retrieved_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    if change in {"origin_only", "coordinates", "distance", "road"}:
        checks = json.loads(Path(entry["driving"]["path"]).read_text())
        field, value = {
            "origin_only": ("checked_waypoint", "origin"),
            "coordinates": ("source_coordinates", [0, 0]),
            "distance": ("snap_distance_m", 50),
            "road": ("road_name", "Another Street"),
        }[change]
        checks[0][field] = value
        replace(entry["driving"], json.dumps(checks).encode())
    with pytest.raises(ValueError):
        prepare(p, m, max_bytes=p.stat().st_size if change == "byte_limit" else 20 * 1024 * 1024)


def test_combiner_rechecks_review_before_publishing(tmp_path):
    p, m, _ = reviewed(tmp_path)
    review = m.pop("arrival_review")
    p.with_suffix(".jsonl.manifest.json").write_text(json.dumps(m))
    output = tmp_path / "reviewed.jsonl"
    combiner = load_script("catalog_combine")
    final = combiner.combine([p], output, arrival_review=review)
    assert prepare(output, final)[1]["arrival_reviewed"] == 1
    with pytest.raises(ValueError, match="explicit complete arrival review"):
        combiner.combine([output], tmp_path / "must-not-strip-review.jsonl")
    changed = tmp_path / "rejected.jsonl"
    next(iter(review["entries"].values()))["profile"] = "wrong"
    with pytest.raises(ValueError):
        combiner.combine([p], changed, arrival_review=review)
    assert not changed.exists() and not changed.with_suffix(".jsonl.manifest.json").exists()


def test_unnamed_link_requires_reviewed_entrance_parking_profile(tmp_path):
    key = "57193dd5-6aa9-4857-98bc-60e2097c3af0"
    p, m, _ = reviewed(tmp_path, key)
    rows, report = prepare(p, m)
    assert report["primary_categories"] == {"entertainment": 1}
    assert rows[0]["provenance"][-1]["driving_road"] == ""
    assert "very limited" in rows[0]["provenance"][-1]["limitations"]
    page = next(iter(m["arrival_review"]["entries"][key]["pages"].values()))
    replace(page, b"<p>2777 Kalakaua Avenue. Driving from the West.</p>")
    with pytest.raises(ValueError, match="access evidence"):
        prepare(p, m)
