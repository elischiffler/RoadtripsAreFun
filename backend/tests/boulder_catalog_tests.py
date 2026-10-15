"""Synthetic admission/regression tests; authentic archive evidence lives outside Git."""

import copy
import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.catalog import boulder
from app.catalog.ingest import prepare
from app.routing.sources.persona_candidates import VerifiedPlace


def record(**changes):
    row = {
        "X": "-105.30907",
        "Y": "39.99733",
        boulder.PREFIX + "ACCESSID": "272",
        boulder.PREFIX + "THNAME": "Realization Point",
        boulder.PREFIX + "ACCESSTYPE": "TH",
        boulder.PREFIX + "ADDRESS": "3400 Flagstaff Rd",
        # Authentic v1 repeats longitude here. This is not latitude.
        boulder.PREFIX + "Y": "-105.30907",
    }
    row.update(changes)
    return row


def page(
    tmp_path,
    *,
    name="Realization Point",
    status="Open",
    parking="Parking lot with 16 standard parking spaces.",
    point="39.997223,-105.309001",
):
    content = f"""<html><h1><span>{name}</span></h1>
    <div class="field--name-field-open-status"><div>Status</div><div>{status}</div></div>
    <a href="http://www.google.com/maps/place/{point}">Get Directions</a>
    <h3>Parking</h3><p>{parking}</p><h2>Other</h2></html>""".encode()
    path = tmp_path / "operator.html"
    path.write_bytes(content)
    return {
        "url": "https://bouldercolorado.gov/trailhead/realization-point",
        "path": str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


def bundle(tmp_path, monkeypatch, records=None):
    content = io.StringIO()
    rows = records if records is not None else [record()]
    writer = csv.DictWriter(content, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(boulder.MEMBER, content.getvalue())
    # Production pins the measured real archive. Only this fixture substitutes it.
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(boulder, "ARCHIVE_SHA256", sha)
    license_path = tmp_path / "synthetic-license.txt"
    license_path.write_text("Synthetic test evidence")
    return path, {
        "release": boulder.RELEASE,
        "schema_version": boulder.SCHEMA,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": boulder.SOURCE_URL,
        "sha256": sha,
        "filters": {"country": "US", "region": "CO"},
        "attribution": boulder.ATTRIBUTION,
        "licenses": {
            "CC0-1.0": {
                "path": str(license_path),
                "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            }
        },
        "operator_evidence": {"272": page(tmp_path)},
    }


def test_source_identity_arrival_and_provenance(tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, monkeypatch)
    rows, report = prepare(path, manifest)
    assert report["accepted"] == 1
    row = rows[0]
    assert row["source_id"] == "boulder:272"
    assert row["latitude"] == 39.997223 and row["longitude"] == -105.309001
    assert row["source_updated_at"] is None
    assert row["provenance"][0]["source_point"]["latitude"] == 39.99733
    assert row["provenance"][1]["arrival_type"] == "trailhead_parking"
    assert row["provenance"][1]["status_at_check"] == "Open"
    assert "overture" not in json.dumps(row).casefold()
    place = VerifiedPlace(
        provider_id=row["source_id"],
        name=row["name"],
        coordinates=[row["latitude"], row["longitude"]],
        source_provenance=row["provenance"],
    )
    assert place.model_dump()["source_provenance"] == row["provenance"]
    from app.models.itinerary_models import Itinerary_Day

    stop = Itinerary_Day.Itinerary_Stop(
        name=place.name,
        time="10:00 AM",
        provider_id=place.provider_id,
        source_provenance=place.source_provenance,
    )
    assert stop.model_dump()["provider_id"] == "boulder:272"
    assert stop.model_dump()["source_provenance"] == row["provenance"]


@pytest.mark.parametrize("status", ["Closed", "Unknown", "", "Open seasonally"])
def test_closed_and_uncertain_operator_status_excluded(tmp_path, monkeypatch, status):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"] = page(tmp_path, status=status)
    rows, report = prepare(path, manifest)
    assert not rows and report["rejects"] == {"operator_not_open": 1}


@pytest.mark.parametrize("parking", ["", "No parking available.", "Bicycle racks only."])
def test_requires_practical_car_parking(tmp_path, monkeypatch, parking):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"] = page(tmp_path, parking=parking)
    assert prepare(path, manifest)[1]["rejects"] == {"parking_unverified": 1}


@pytest.mark.parametrize(
    "point,reason",
    [
        ("-105.309001,39.997223", "coordinates"),
        ("40.1,-105.3", "arrival_changed_review_required"),
        ("nan,-105.3", "arrival_unverified"),
    ],
)
def test_rejects_invalid_or_changed_arrival(tmp_path, monkeypatch, point, reason):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"] = page(tmp_path, point=point)
    assert prepare(path, manifest)[1]["rejects"] == {reason: 1}


@pytest.mark.parametrize("days", [-1, 31])
def test_future_or_stale_operator_evidence_rejected(tmp_path, monkeypatch, days):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"]["retrieved_at"] = (
        datetime.now(UTC) - timedelta(days=days)
    ).isoformat()
    with pytest.raises(ValueError, match="last 30 days"):
        prepare(path, manifest)


def test_wrong_page_and_tampered_evidence_rejected(tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"] = page(tmp_path, name="Another Trailhead")
    with pytest.raises(ValueError, match="identify"):
        prepare(path, manifest)
    manifest["operator_evidence"]["272"]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        prepare(path, manifest)


@pytest.mark.parametrize(
    "url",
    [
        "https://unreviewed.example/trailhead/realization-point",
        "http://bouldercolorado.gov/trailhead/realization-point",
        "https://bouldercolorado.gov/trailhead/realization-point?override=true",
    ],
)
def test_requires_original_official_trailhead_evidence(tmp_path, monkeypatch, url):
    path, manifest = bundle(tmp_path, monkeypatch)
    manifest["operator_evidence"]["272"]["url"] = url
    with pytest.raises(ValueError, match="official trailhead"):
        prepare(path, manifest)


def test_archive_pin_licenses_and_limits(tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, monkeypatch)
    for field, value in [
        ("sha256", "wrong"),
        ("source_url", "https://example.test"),
        ("release", "2"),
    ]:
        invalid = copy.deepcopy(manifest)
        invalid[field] = value
        with pytest.raises(ValueError, match="pinned"):
            prepare(path, invalid)
    invalid = copy.deepcopy(manifest)
    invalid["licenses"] = {"Unreviewed": manifest["licenses"]["CC0-1.0"]}
    with pytest.raises(ValueError, match="CC0"):
        prepare(path, invalid)
    with pytest.raises(ValueError, match="size/checksum"):
        prepare(path, manifest, max_bytes=1)
    with path.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="size/checksum"):
        prepare(path, manifest)


def test_missing_evidence_does_not_invent_open_status(tmp_path, monkeypatch):
    other = record(
        **{boulder.PREFIX + "ACCESSID": "284", boulder.PREFIX + "THNAME": "Halfway House"}
    )
    path, manifest = bundle(tmp_path, monkeypatch, [record(), other])
    assert prepare(path, manifest)[1]["rejects"] == {"operator_evidence_missing": 1}
    with pytest.raises(ValueError, match="row ceiling"):
        prepare(path, manifest, max_rows=1)
    manifest["operator_evidence"]["999"] = page(tmp_path)
    with pytest.raises(ValueError, match="unknown native"):
        prepare(path, manifest)


def test_duplicate_source_ids_are_not_arbitrarily_collapsed(tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, monkeypatch, [record(), record()])
    with pytest.raises(ValueError, match="duplicate Boulder"):
        prepare(path, manifest)


def test_two_summit_arrivals_count_as_one_destination(tmp_path, monkeypatch):
    other = record(
        **{boulder.PREFIX + "ACCESSID": "279", boulder.PREFIX + "THNAME": "Flagstaff Summit West"}
    )
    path, manifest = bundle(tmp_path, monkeypatch, [record(), other])
    manifest["operator_evidence"]["279"] = page(tmp_path)
    assert prepare(path, manifest)[1]["rejects"] == {"same_flagstaff_summit_destination": 1}


def test_overture_combiner_refuses_boulder_without_relabeling(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "boulder_combine_probe", Path(__file__).parents[2] / "scripts/catalog_combine.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path, manifest = bundle(tmp_path, monkeypatch)
    path.with_suffix(path.suffix + ".manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Overture only"):
        module.combine([path], tmp_path / "combined.jsonl")
    assert not (tmp_path / "combined.jsonl").exists()


def test_archive_and_publisher_snapshots_share_the_existing_byte_budget(tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, monkeypatch)
    total = path.stat().st_size + Path(manifest["operator_evidence"]["272"]["path"]).stat().st_size
    assert prepare(path, manifest, max_bytes=total)[1]["bytes"] == total
    with pytest.raises(ValueError, match="aggregate archive/evidence byte ceiling"):
        prepare(path, manifest, max_bytes=total - 1)
