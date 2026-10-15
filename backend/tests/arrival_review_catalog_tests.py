"""Synthetic current-arrival cases; authentic publisher pages remain outside Git."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.catalog import arrival_review, mixed, venue_profiles
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
    if "coordinates" in profile:
        lat, lon = profile["coordinates"]
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
        url: retained(
            f"publisher-{i}.html",
            ("<meta charset='utf-8'><p>" + "; ".join(phrases) + "</p>").encode(),
            url,
        )
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


@pytest.mark.parametrize("key", venue_profiles.PROFILES)
@pytest.mark.parametrize("failure", [None, "closure", "parking", "changed_point"])
def test_expansion_profiles_require_inspected_point_and_access(tmp_path, key, failure):
    p, manifest, _ = reviewed(tmp_path, key)
    profile = venue_profiles.PROFILES[key]
    entry = manifest["arrival_review"]["entries"][key]
    if failure in {"closure", "parking"}:
        page = next(iter(entry["pages"].values()))
        raw = Path(page["path"]).read_bytes()
        replace(
            page,
            raw + b"<p>Temporarily closed.</p>" if failure == "closure" else b"<p>Visit us.</p>",
        )
    if failure == "changed_point":
        # A different source point and a matching drive receipt still do not
        # establish arrival at the physically inspected venue coordinates.
        source = json.loads(p.read_text())
        source["geometry"]["coordinates"][0] += 0.0001
        p.write_text(json.dumps(source) + "\n")
        manifest["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        check = json.loads(Path(entry["driving"]["path"]).read_text())
        check[0]["source_coordinates"][1] += 0.0001
        replace(entry["driving"], json.dumps(check).encode())
    if failure:
        with pytest.raises(ValueError):
            prepare(p, manifest)
    else:
        rows, report = prepare(p, manifest)
        assert report["primary_categories"] == {profile["primary_category"]: 1}
        assert [rows[0]["latitude"], rows[0]["longitude"]] == profile["coordinates"]
        assert rows[0]["provenance"][-1]["opening_hours_imported"] is False


def test_reviewed_venue_facts_match_profiles_and_do_not_duplicate_prior_197():
    root = Path(__file__).resolve().parents[2] / "docs/data/catalog-expansion-20261015"
    review = json.loads((root / "venues-17-review.json").read_text())
    rows = [
        json.loads(line)
        for line in (root / "reviewed-venues-17.preview.jsonl").read_text().splitlines()
    ]
    assert len(rows) == len({r["source_id"] for r in rows}) == 17
    assert {r["source_id"] for r in rows} == set(venue_profiles.PROFILES)
    assert rows == review["records"]
    prior = json.loads((root / "starter-82-identities.json").read_text())
    for name in ("reviewed-103.preview.jsonl", "reviewed-nature-12.preview.jsonl"):
        prior.extend(json.loads(line) for line in (root / name).read_text().splitlines())
    assert len(prior) == 197
    for row in rows:
        profile = venue_profiles.PROFILES[row["source_id"]]
        assert [row["latitude"], row["longitude"]] == profile["coordinates"]
        if profile["primary_category"] in {"food", "nightlife"}:
            assert profile["primary_category"] in row["categories"]
        assert row["provenance"][-1]["primary_category"] == profile["primary_category"]
        for other in prior:
            assert row["source_id"] != other["source_id"]
            assert not (
                row["region"] == other["region"]
                and mixed.names(row).intersection(mixed.names(other))
                and mixed.distance(row, other) <= 250
            )
        prior.append(row)
