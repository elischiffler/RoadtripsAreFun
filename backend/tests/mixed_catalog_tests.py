import hashlib
import json

import pytest

from app.catalog import mixed
from app.catalog.ingest import prepare
from tests.boulder_catalog_tests import bundle as boulder_bundle
from tests.catalog_ingest_tests import bundle, feature


def write_bundle(tmp_path, inputs, **extra):
    descriptions = []
    for p, m in inputs:
        manifest_path = p.with_suffix(p.suffix + ".manifest.json")
        manifest_path.write_text(json.dumps(m))
        descriptions.append(
            {
                "path": str(p),
                "manifest": str(manifest_path),
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            }
        )
    data = {"inputs": descriptions, **extra}
    p = tmp_path / "mixed.json"
    p.write_text(json.dumps(data))
    return p, data


def test_mixed_sources_revalidate_children_and_preserve_native_namespaces(tmp_path, monkeypatch):
    ov = tmp_path / "ov"
    ov.mkdir()
    bo = tmp_path / "bo"
    bo.mkdir()
    a, ma = bundle(ov, [feature()])
    ma["schema_version"] = "roadtrips-overture-places-v1"
    b, mb = boulder_bundle(bo, monkeypatch)
    p, data = write_bundle(tmp_path, [(a, ma), (b, mb)])
    rows, sources, licenses, report = mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)
    assert {r["source_id"] for r in rows} == {"stable-1", "boulder:272"}
    assert report["source_counts"] == {"overture": 1, "boulder-osmp": 1}
    assert report["source_reports"][0]["report"]["accepted"] == 1
    assert report["source_reports"][1]["artifact_sha256"] == mb["sha256"]
    m = {
        "schema_version": mixed.SCHEMA,
        "release": "pilot-2026-10-15.1",
        "retrieved_at": "2026-10-15T00:00:00Z",
        "source_url": mixed.SOURCE_URL,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "filters": {"complete_generation": True},
        "attribution": "; ".join(s["attribution"] for s in sources.values()),
        "licenses": licenses,
        "source_catalogs": sources,
    }
    assert prepare(p, m)[1]["accepted"] == 2
    m["source_catalogs"]["boulder-osmp"]["release"] = "fabricated"
    with pytest.raises(ValueError, match="metadata differs"):
        prepare(p, m)
    data["inputs"][0]["manifest_sha256"] = "wrong"
    with pytest.raises(ValueError, match="child manifest"):
        mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)


def test_duplicate_source_mapping_requires_review_and_retains_both_provenances(
    tmp_path, monkeypatch
):
    ov = tmp_path / "ov"
    ov.mkdir()
    bo = tmp_path / "bo"
    bo.mkdir()
    f = feature(
        id="same-venue",
        names={"primary": "Realization Point"},
        addresses=[{"country": "US", "region": "CO"}],
    )
    f["geometry"]["coordinates"] = [-105.309001, 39.997223]
    a, ma = bundle(ov, [f])
    ma["schema_version"] = "roadtrips-overture-places-v1"
    b, mb = boulder_bundle(bo, monkeypatch)
    _, data = write_bundle(tmp_path, [(a, ma), (b, mb)])
    with pytest.raises(ValueError, match="unresolved colocated"):
        mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)
    data["deduplications"] = [
        {
            "keep": "boulder:272",
            "merge": "overture:same-venue",
            "evidence_url": "https://bouldercolorado.gov/trailhead/realization-point",
        }
    ]
    rows, _, _, report = mixed.assemble(data, max_rows=500, max_bytes=20 * 1024 * 1024)
    assert report["accepted"] == 1 and report["duplicates"] == 1
    assert any(x.get("provider_id") == "overture:same-venue" for x in rows[0]["provenance"])
    assert any(x.get("dataset") == "meta" for x in rows[0]["provenance"])
    mapping = next(x for x in rows[0]["provenance"] if x.get("provider_id"))
    assert mapping["source_release"] == ma["release"]
    assert mapping["source_attribution"] == ma["attribution"]


@pytest.mark.parametrize(
    "case,expected",
    [
        ("nested", "nesting"),
        ("namespace", "empty source input"),
        ("conflict", "conflicting duplicate"),
        ("release", "consistent source release"),
        ("rows", "row ceiling"),
        ("bytes", "byte ceiling"),
    ],
)
def test_mixed_generation_rejects_conflicts_and_aggregate_limits(tmp_path, case, expected):
    inputs = []
    for i in range(2):
        directory = tmp_path / str(i)
        directory.mkdir()
        item = feature(id=f"item-{i}")
        if case == "namespace":
            # The original Overture adapter rejects a forged native ID before
            # the mixer's namespace check; it must not become an accepted row.
            item["properties"]["id"] = "nps:forged"
        if case == "conflict":
            item["properties"]["id"] = "same-id"
            item["properties"]["names"] = {"primary": f"Different venue {i}"}
        path, manifest = bundle(directory, [item])
        manifest["schema_version"] = "roadtrips-overture-places-v1"
        if case == "nested":
            manifest["schema_version"] = mixed.SCHEMA
        if case == "release" and i:
            manifest["release"] = "2026-10-01.0"
            manifest["source_url"] = manifest["source_url"].replace("2026-09-23.1", "2026-10-01.0")
        inputs.append((path, manifest))
    _, data = write_bundle(tmp_path, inputs)
    max_rows = 1 if case == "rows" else 500
    max_bytes = sum(p.stat().st_size for p, _ in inputs) - 1 if case == "bytes" else 1_000_000
    with pytest.raises(ValueError, match=expected):
        mixed.assemble(data, max_rows=max_rows, max_bytes=max_bytes)
