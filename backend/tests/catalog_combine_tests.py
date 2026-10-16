"""Complete-generation combination tests use only synthetic regional inputs."""

import json

import pytest

from app.catalog.ingest import prepare
from tests.catalog_extraction_tests import load_script
from tests.catalog_ingest_tests import bundle, feature

combiner = load_script("catalog_combine")


def regional(tmp_path, name, features, **updates):
    directory = tmp_path / name
    directory.mkdir()
    path, manifest = bundle(directory, features)
    manifest["filters"]["region_label"] = name
    manifest.update(updates)
    path.with_suffix(".jsonl.manifest.json").write_text(json.dumps(manifest))
    return path


def test_combine_retains_regions_and_deduplicates_normalized_identity(tmp_path):
    first = regional(tmp_path, "west", [feature()])
    same = feature()
    same["unused_raw_metadata"] = "does not change normalized identity"
    second = regional(
        tmp_path,
        "east",
        [same, feature(id="east-2", addresses=[{"country": "US", "region": "NY"}])],
    )
    output = tmp_path / "combined.jsonl"
    manifest = combiner.combine([first, second], output)
    rows, _ = prepare(output, manifest)
    assert {row["region"] for row in rows} == {"CA", "NY"}
    assert manifest["combination"]["duplicates"] == 1
    assert len(manifest["inputs"]) == 2
    assert all(item["manifest_sha256"] and item["sha256"] for item in manifest["inputs"])
    assert "complete replacement" in manifest["filters"]["generation_semantics"]
    with pytest.raises(ValueError, match="already exists"):
        combiner.combine([first], output)
    assert len(prepare(output, manifest)[0]) == 2


def test_combined_attribution_deduplicates_shared_source_names(tmp_path):
    a = regional(tmp_path, "a", [feature()], attribution="Provider A; Provider B")
    b = regional(tmp_path, "b", [feature(id="another")], attribution="Provider B; Provider C")
    manifest = combiner.combine([a, b], tmp_path / "credits.jsonl")
    assert manifest["attribution"] == "Provider A; Provider B; Provider C"


@pytest.mark.parametrize("case", ["conflict", "release", "schema", "checksum", "rows", "bytes"])
def test_invalid_combination_never_publishes_partial_output(tmp_path, case):
    first = regional(tmp_path, "first", [feature()])
    second_feature = feature(id="another")
    updates = {}
    if case == "conflict":
        second_feature = feature(names={"primary": "Changed name"})
    if case == "release":
        updates = {
            "release": "2026-10-01.0",
            "source_url": "s3://overturemaps-us-west-2/release/2026-10-01.0/theme=places/type=place/",
        }
    if case == "schema":
        updates = {"schema_version": "unexpected"}
    if case == "checksum":
        updates = {"sha256": "incorrect"}
    second = regional(tmp_path, "second", [second_feature], **updates)
    output = tmp_path / "combined.jsonl"
    kwargs = {"max_rows": 1} if case == "rows" else {"max_bytes": 10} if case == "bytes" else {}
    with pytest.raises(ValueError):
        combiner.combine([first, second], output, **kwargs)
    assert not output.exists()
    assert not output.with_suffix(".jsonl.manifest.json").exists()
    assert not list(tmp_path.glob("catalog-combine-*"))


def test_bounded_input_count_and_existing_manifest_preserved(tmp_path):
    first = regional(tmp_path, "first", [feature()])
    output = tmp_path / "combined.jsonl"
    with pytest.raises(ValueError, match="1..100"):
        combiner.combine([first] * 101, output)
    target = output.with_suffix(".jsonl.manifest.json")
    target.write_text("existing")
    with pytest.raises(ValueError, match="already exists"):
        combiner.combine([first], output)
    assert target.read_text() == "existing"
    assert not output.exists()


def test_manifest_publication_failure_removes_only_new_output(tmp_path, monkeypatch):
    first = regional(tmp_path, "first", [feature()])
    output = tmp_path / "combined.jsonl"
    original = combiner.os.link

    def fail_manifest(source, destination):
        if str(destination).endswith(".manifest.json"):
            raise OSError("publication failed")
        original(source, destination)

    monkeypatch.setattr(combiner.os, "link", fail_manifest)
    with pytest.raises(OSError, match="publication failed"):
        combiner.combine([first], output)
    assert not output.exists()


def test_explicit_selection_is_exact_and_retains_original_source_features(tmp_path):
    first = regional(tmp_path, "first", [feature(), feature(id="exclude")])
    output = tmp_path / "selected.jsonl"
    manifest = combiner.combine([first], output, selected_ids={"stable-1"})
    assert prepare(output, manifest)[1]["accepted"] == 1
    assert json.loads(output.read_text()) == feature()
    assert manifest["filters"]["selected_id_count"] == 1
    assert manifest["inputs"][0]["manifest_sha256"]
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(ValueError, match="absent"):
        combiner.combine([first], missing, selected_ids={"absent"})
    assert not missing.exists()
