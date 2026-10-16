"""Expansion admission keeps source evidence and starter deduplication mandatory."""

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.catalog import nps_heritage
from app.catalog.ingest import prepare
from tests.catalog_extraction_tests import load_script
from tests.nps_heritage_catalog_tests import bundle

expansion = load_script("catalog_expansion_manifest")


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return path


def setup(tmp_path, monkeypatch):
    p, m = bundle(tmp_path, monkeypatch)
    rows, _ = prepare(p, m)
    b = json.loads(p.read_bytes())
    monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", b["inventory"]["sha256"])
    baseline = write(
        tmp_path / "baseline.json",
        [
            dict(rows[0], source_id=f"starter-{i}", name=f"Starter {i}", latitude=0, longitude=i)
            for i in range(82)
        ],
    )
    record = {
        k: rows[0][k]
        for k in ("source_id", "name", "latitude", "longitude", "region", "categories")
    }
    record.update(
        unit_code="exam", selection=b["selections"]["exam"], operation_evidence=b["inputs"]["exam"]
    )
    review = {
        "schema_version": "roadtrips-expansion-review/1",
        "source_release": m["release"],
        "checked_at": datetime.now(UTC).isoformat(),
        "baseline_identity_sha256": expansion.fingerprint(baseline),
        "inventory": b["inventory"],
        "driving": b["driving"],
        "batches": [{"id": "heritage-01", "records": [record]}],
    }
    return write(tmp_path / "review.json", review), baseline, review


def test_rebuild_revalidates_original_sources_and_publishes_existing_import_schema(
    tmp_path, monkeypatch
):
    review, baseline, _ = setup(tmp_path, monkeypatch)
    output = tmp_path / "output"
    report = expansion.build(tmp_path, review, baseline, output)
    assert report["accepted"] == 1 and report["baseline"] == 82
    manifest = json.loads((output / "heritage-01.json.manifest.json").read_bytes())
    rows, result = prepare(output / "heritage-01.json", manifest)
    assert result["accepted"] == 1 and rows[0]["source_id"] == "nps-heritage:exam"
    with pytest.raises(ValueError, match="already exists"):
        expansion.build(tmp_path, review, baseline, output)
    assert prepare(output / "heritage-01.json", manifest)[1]["accepted"] == 1


@pytest.mark.parametrize(
    "change", ["coordinate", "baseline", "driving", "source", "duplicate", "colocated"]
)
def test_changed_evidence_or_unresolved_destination_never_publishes_a_batch(
    tmp_path, monkeypatch, change
):
    review_path, baseline, review = setup(tmp_path, monkeypatch)
    record = review["batches"][0]["records"][0]
    if change == "coordinate":
        record["latitude"] += 0.5
    elif change == "baseline":
        baseline.write_text(baseline.read_text() + " ")
    elif change == "driving":
        Path(review["driving"]["path"]).write_text("[]")
    elif change == "source":
        Path(record["operation_evidence"]["path"]).write_text("{}")
    elif change == "duplicate":
        record["source_id"] = "starter-0"
    elif change == "colocated":
        original = json.loads(baseline.read_bytes())
        original[0].update({k: record[k] for k in ("name", "latitude", "longitude", "region")})
        write(baseline, original)
        review["baseline_identity_sha256"] = expansion.fingerprint(baseline)
    write(review_path, review)
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        expansion.build(tmp_path, review_path, baseline, output)
    assert not list(output.glob("*.json")) and not list(output.glob("*.jsonl"))


def test_later_failed_batch_publishes_none_and_existing_partial_is_preserved(tmp_path, monkeypatch):
    review_path, baseline, review = setup(tmp_path, monkeypatch)
    bad = copy.deepcopy(review["batches"][0])
    bad["id"] = "heritage-02"
    bad["records"][0]["operation_evidence"]["sha256"] = "incorrect"
    bad["records"][0]["source_id"] = "nps-heritage:other"
    review["batches"].append(bad)
    write(review_path, review)
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        expansion.build(tmp_path, review_path, baseline, output)
    assert list(output.iterdir()) == []
    (output / "heritage-01.partial").write_text("preserve another producer")
    with pytest.raises(FileExistsError):
        expansion.build(tmp_path, review_path, baseline, output)
    assert (output / "heritage-01.partial").read_text() == "preserve another producer"


def test_new_reviewed_inventory_keeps_its_actual_fingerprint_in_provenance(tmp_path, monkeypatch):
    p, m = bundle(tmp_path, monkeypatch)
    sha = json.loads(p.read_bytes())["inventory"]["sha256"]
    monkeypatch.setattr(nps_heritage, "INDEX_SHA256", "initial-release-fingerprint")
    monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", sha)
    rows, report = prepare(p, m)
    assert report["accepted"] == 1 and rows[0]["provenance"][0]["snapshot_sha256"] == sha
    monkeypatch.setattr(nps_heritage, "EXPANSION_INDEX_SHA256", "uninspected-fingerprint")
    with pytest.raises(ValueError, match="inspected public index"):
        prepare(p, m)


def test_checked_in_review_contains_unique_bounded_public_facts_and_no_starter_duplicates():
    root = Path(__file__).resolve().parents[2] / "docs/data/catalog-expansion-20261015"
    review = json.loads((root / "review.json").read_bytes())
    baseline = json.loads((root / "starter-82-identities.json").read_bytes())
    records = [r for b in review["batches"] for r in b["records"]]
    assert len(records) == len({r["source_id"] for r in records}) == 103
    assert not {r["source_id"] for r in records} & {r["source_id"] for r in baseline}
    assert (
        hashlib.sha256((root / "starter-82-identities.json").read_bytes()).hexdigest()
        == review["baseline_identity_sha256"]
    )
    assert review["inventory"]["sha256"] == nps_heritage.EXPANSION_INDEX_SHA256
    assert all(len(b["records"]) <= 25 for b in review["batches"])
    for r in records:
        assert -90 <= r["latitude"] <= 90 and -180 <= r["longitude"] <= 180
        assert r["source_id"] == "nps-heritage:" + r["unit_code"]
        assert (
            r["operation_evidence"]["url"]
            == f"https://www.nps.gov/{r['unit_code']}/structured_data_{r['unit_code']}.json"
        )
        assert "rating" not in r and "opening_hours" not in r

    preview = [
        json.loads(line) for line in (root / "reviewed-103.preview.jsonl").read_text().splitlines()
    ]
    by_id = {r["source_id"]: r for r in preview}
    assert len(preview) == len(by_id) == len(records)
    for r in records:
        for key in ("source_id", "name", "latitude", "longitude", "region", "categories"):
            assert by_id[r["source_id"]][key] == r[key]
        provenance = by_id[r["source_id"]]["provenance"]
        assert provenance[0]["snapshot_sha256"] == review["inventory"]["sha256"]
        assert provenance[-1]["snapshot_sha256"] == r["operation_evidence"]["sha256"]
