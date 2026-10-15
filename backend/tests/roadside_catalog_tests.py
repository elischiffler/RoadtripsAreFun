"""Synthetic admission cases; authentic roadside receipts remain outside Git."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.catalog import mixed, roadside
from app.catalog.identity import identity
from app.catalog.ingest import prepare
from tests.catalog_extraction_tests import load_script


def encoded_csv(columns, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def bundle(tmp_path, monkeypatch):
    now = datetime.now(UTC).isoformat()

    def evidence(key, data, url=None):
        p = tmp_path / key
        p.write_bytes(data)
        e = {"path": str(p), "sha256": hashlib.sha256(data).hexdigest(), "retrieved_at": now}
        if url:
            e["url"] = url
        return e

    archive = encoded_csv(
        ["index", "title", "year", "image", "image_link"],
        [
            {"index": 279, "title": "Mitchell Corn Palace, Mitchell, South Dakota"},
            {"index": 5771, "title": "Corn Palace, Mitchell, South Dakota"},
            {"index": 11631, "title": "Corn Palace billboard, South Dakota"},
        ],
    )
    monkeypatch.setattr(roadside, "CSV_SHA256", hashlib.sha256(archive).hexdigest())
    monkeypatch.setattr(roadside, "CSV_ROWS", 3)
    rights = encoded_csv(
        ["id", "title", "publication"],
        [
            {
                "id": "723_marg.html",
                "title": "John Margolies Roadside America Photograph Archive",
                "publication": "<p>Library of Congress purchased the intellectual property rights; "
                "no known copyright restrictions; sculpture or other works of art exceptions.</p>",
            }
        ],
    )
    point = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-98.02536536, 43.71485882]},
        "properties": {
            "id": "synthetic-point",
            "names": {"primary": "The World's Only Corn Palace"},
            "addresses": [
                {
                    "freeform": "604 N Main St",
                    "country": "US",
                    "region": "SD",
                    "locality": "Mitchell",
                    "postcode": "57301",
                }
            ],
            "operating_status": "open",
            "confidence": 0.95,
            "basic_category": "stadium_arena",
            "sources": [
                {"dataset": "meta", "record_id": "synthetic-meta", "license": "CDLA-Permissive-2.0"}
            ],
        },
    }
    b = {
        "profile": "corn-palace/1",
        "point_id": "synthetic-point",
        "archive": evidence("archive.csv", archive),
        "rights": evidence("rights.csv", rights, roadside.RIGHTS_URL),
        "points": evidence("points.jsonl", json.dumps(point).encode(), roadside.POINT_SOURCE),
        "visit": evidence(
            "visit.html",
            b"<p>The Corn Palace is open year-round and is free to visit. 604 North Main Street; Mitchell, SD 57301.</p>",
            roadside.VISIT_URL,
        ),
        "parking": evidence(
            "parking.html",
            b"<p>FREE RV/Trailer parking located on 7th and Lawler</p>",
            roadside.PARKING_URL,
        ),
        "driving": evidence(
            "driving.json",
            json.dumps(
                [
                    {
                        "source_id": "synthetic-point",
                        "checked_at": now,
                        "http_status": 200,
                        "code": "Ok",
                        "source_coordinates": [43.71485882, -98.02536536],
                        "snap_distance_m": 16.2,
                        "road_name": "North Main Street",
                    }
                ]
            ).encode(),
        ),
    }
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(b))
    load_script("catalog_roadside_manifest").build(p)
    m = json.loads(p.with_suffix(".json.manifest.json").read_text())
    return p, m, b


def update(p, m, b, key=None, raw=None):
    if key:
        Path(b[key]["path"]).write_bytes(raw)
        b[key]["sha256"] = hashlib.sha256(raw).hexdigest()
    p.write_text(json.dumps(b))
    m["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()


def test_photos_collapse_to_one_licensed_current_arrival(tmp_path, monkeypatch):
    p, m, _ = bundle(tmp_path, monkeypatch)
    rows, report = prepare(p, m)
    r = rows[0]
    assert report["accepted"] == 1 and report["duplicate_photograph_records"] == 1
    assert report["rejects"] == {"not_selected_for_current_arrival_review": 1}
    assert identity(r["source_id"]) == ("kaggle-loc:279", "kaggle-loc-roadside")
    assert [r["latitude"], r["longitude"]] == [43.71485882, -98.02536536]
    assert "roadside_attraction" in r["categories"] and r["source_updated_at"] is None
    assert (
        next(x for x in r["provenance"] if x["dataset"] == "Overture reviewed arrival point")[
            "record_id"
        ]
        == "synthetic-point"
    )
    assert r["provenance"][-1]["arrival_type"] == "venue frontage at published visitor address"
    assert not {"images", "description", "operatingHours"} & r.keys()
    with pytest.raises(ValueError, match="already exists"):
        load_script("catalog_roadside_manifest").build(p)


@pytest.mark.parametrize(
    "change",
    [
        "closure",
        "giftshop",
        "foreign",
        "unlicensed",
        "polygon",
        "nonfinite",
        "weak",
        "stale",
        "driving_distance",
        "driving_road",
        "driving_coordinates",
        "publisher",
        "rights",
        "archive",
        "profile",
        "byte_limit",
    ],
)
def test_roadside_evidence_cannot_admit_uncertain_arrivals(tmp_path, monkeypatch, change):
    p, m, b = bundle(tmp_path, monkeypatch)
    key, raw = None, None
    if change == "closure":
        key = "visit"
        raw = Path(b[key]["path"]).read_bytes() + b"<p>Temporarily closed.</p>"
    if change in {"giftshop", "foreign", "unlicensed", "polygon", "nonfinite", "weak"}:
        key = "points"
        f = json.loads(Path(b[key]["path"]).read_bytes())
        if change == "giftshop":
            f["properties"]["addresses"][0]["freeform"] = "603 N Main St"
        if change == "foreign":
            f["properties"]["addresses"][0]["country"] = "CA"
        if change == "unlicensed":
            f["properties"]["sources"][0]["dataset"] = "unreviewed"
        if change == "polygon":
            f["geometry"]["type"] = "Polygon"
        if change == "nonfinite":
            f["geometry"]["coordinates"][0] = float("nan")
        if change == "weak":
            f["properties"]["confidence"] = 0.1
        raw = json.dumps(f).encode()
    if change == "stale":
        b["visit"]["retrieved_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    if change.startswith("driving_"):
        key = "driving"
        d = json.loads(Path(b[key]["path"]).read_bytes())
        field, value = {
            "driving_distance": ("snap_distance_m", 400),
            "driving_road": ("road_name", "Wrong Street"),
            "driving_coordinates": ("source_coordinates", [0, 0]),
        }[change]
        d[0][field] = value
        raw = json.dumps(d).encode()
    if change == "publisher":
        b["parking"]["url"] = "https://example.test/parking"
    if change == "rights":
        key, raw = "rights", b"id,title,publication\nunknown,Unknown,No clearance\n"
    if change == "archive":
        b["archive"]["sha256"] = "wrong"
    if change == "profile":
        b["profile"] = "unreviewed/1"
    update(p, m, b, key, raw)
    with pytest.raises(ValueError):
        prepare(p, m, max_bytes=100 if change == "byte_limit" else 20 * 1024 * 1024)


def test_roadside_rights_and_point_license_must_both_be_retained(tmp_path, monkeypatch):
    p, m, _ = bundle(tmp_path, monkeypatch)
    del m["licenses"]["CDLA-Permissive-2.0"]
    with pytest.raises(ValueError, match="provenance/license"):
        prepare(p, m)
    del m["licenses"]["LicenseRef-LOC-Margolies-Notice"]
    with pytest.raises(ValueError, match="reviewed archive"):
        prepare(p, m)


def test_mixed_roadside_revalidates_original_evidence(tmp_path, monkeypatch):
    p, m, b = bundle(tmp_path, monkeypatch)
    data = {
        "inputs": [
            {
                "path": str(p),
                "manifest": str(p.with_suffix(".json.manifest.json")),
                "manifest_sha256": hashlib.sha256(
                    p.with_suffix(".json.manifest.json").read_bytes()
                ).hexdigest(),
            }
        ]
    }
    rows, sources, _, report = mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)
    assert report["source_counts"] == {"kaggle-loc-roadside": 1}
    assert sources["kaggle-loc-roadside"]["release"] == m["release"]
    assert rows[0]["source_id"] == "kaggle-loc:279"
    Path(b["parking"]["path"]).write_text("Unverified changed evidence")
    with pytest.raises(ValueError, match="checksum"):
        mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)


def test_overture_regional_combiner_refuses_roadside_bundle(tmp_path, monkeypatch):
    p, _, _ = bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Overture only"):
        load_script("catalog_combine").combine([p], tmp_path / "not-overture.jsonl")
