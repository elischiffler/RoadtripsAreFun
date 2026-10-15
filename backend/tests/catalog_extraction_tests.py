"""Extraction bounds use synthetic source records, never hosted data."""

import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.catalog.ingest import prepare
from tests.catalog_ingest_tests import feature


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = load_script("extract_overture_places")
loader = load_script("catalog_import")


def test_selected_limit_stops_reading_before_another_source_record(tmp_path):
    def source():
        yield feature()
        raise AssertionError("source should not be consumed beyond accepted limit")

    path = tmp_path / "pilot.jsonl"
    manifest = extractor.extract(
        source(), path, bbox=(-123, 37, -122, 38), region="synthetic", max_records=1
    )
    rows, report = prepare(path, manifest)
    assert len(rows) == 1 and report["accepted"] == 1
    assert manifest["extraction"]["stop_reason"] == "accepted_row_limit"
    assert manifest["extraction"]["complete_bbox_scan"] is False
    assert path.with_suffix(".jsonl.manifest.json").is_file()


def test_filter_before_write_and_preserve_licensed_provenance(tmp_path):
    bad = feature(sources=[{"dataset": "unknown"}])
    other_country = feature(addresses=[{"country": "CA", "region": "CA"}])
    path = tmp_path / "pilot.jsonl"
    manifest = extractor.extract(
        [bad, other_country, feature()],
        path,
        bbox=(-123, 37, -122, 38),
        region="synthetic",
    )
    assert manifest["extraction"]["inspected"] == 3
    assert manifest["extraction"]["accepted"] == 1
    assert manifest["extraction"]["rejects"] == {
        "unapproved_provenance": 1,
        "country_region": 1,
    }
    assert len(path.read_text().splitlines()) == 1
    assert json.loads(path.read_text())["properties"]["sources"][-1]["dataset"] == "Overture"
    assert manifest["extraction"]["complete_bbox_scan"] is True


def test_decoded_byte_cap_does_not_write_oversize_record(tmp_path):
    huge = copy.deepcopy(feature())
    huge["properties"]["unused"] = "x" * 5000
    path = tmp_path / "pilot.jsonl"
    manifest = extractor.extract(
        [feature(), huge], path, bbox=(-123, 37, -122, 38), region="synthetic", max_bytes=1000
    )
    assert path.stat().st_size <= 1000
    assert manifest["extraction"]["stop_reason"] == "decoded_byte_limit"
    assert manifest["extraction"]["accepted"] == 1


def test_shapely_point_tuples_are_validated_as_the_written_geojson(tmp_path):
    item = feature()
    item["geometry"]["coordinates"] = (-122.4, 37.8)
    path = tmp_path / "geometry.jsonl"
    extractor.extract([item], path, bbox=(-123, 37, -122, 38), region="synthetic")
    assert json.loads(path.read_text())["geometry"]["coordinates"] == [-122.4, 37.8]


def test_no_empty_publication_and_no_overwrite(tmp_path):
    path = tmp_path / "empty.jsonl"
    with pytest.raises(ValueError, match="no eligible"):
        extractor.extract([], path, bbox=(-123, 37, -122, 38), region="synthetic")
    assert not path.exists()
    assert not path.with_suffix(".jsonl.partial").exists()
    path.write_text("preserve")
    with pytest.raises(ValueError, match="already exists"):
        extractor.extract([feature()], path, bbox=(-123, 37, -122, 38), region="synthetic")
    assert path.read_text() == "preserve"


def test_quality_and_category_selection_does_not_promote_unknown_status(tmp_path):
    path = tmp_path / "reviewed.jsonl"
    examples = [
        feature(id="status-unknown", confidence=0.99),
        feature(id="low-confidence", operating_status="open", confidence=0.8),
        feature(id="bool-confidence", operating_status="open", confidence=True),
        feature(
            id="other-category",
            operating_status="open",
            confidence=0.99,
            basic_category="restaurant",
            taxonomy={"primary": "restaurant", "hierarchy": []},
        ),
        feature(id="accepted", operating_status="open", confidence=0.99),
    ]
    examples[0]["properties"].pop("operating_status", None)
    manifest = extractor.extract(
        examples,
        path,
        bbox=(-123, 37, -122, 38),
        region="synthetic",
        category_filter=["museum"],
        require_open=True,
        min_confidence=0.9,
    )
    assert [r["source_id"] for r in prepare(path, manifest)[0]] == ["accepted"]
    assert manifest["extraction"]["rejects"] == {
        "open_status_required": 1,
        "source_confidence": 2,
        "category_selection": 1,
    }
    assert manifest["filters"]["minimum_existence_confidence"] == 0.9


@pytest.mark.parametrize("bbox", ["nan,1,2,3", "1,2,1,3", "-180,-90,180,90", "1,2,3"])
def test_bbox_rejects_unbounded_or_invalid_scope(bbox):
    with pytest.raises((ValueError, extractor.argparse.ArgumentTypeError)):
        extractor.parse_bbox(bbox)


def test_neon_cli_explicit_target_enforces_verified_tls(monkeypatch):
    import psycopg2

    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:fixture@ep-test.neon.tech/neondb")
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (18,)
    connect = MagicMock(return_value=conn)
    monkeypatch.setattr(psycopg2, "connect", connect)
    assert loader.connect_target("neon") is conn
    assert connect.call_args.kwargs["sslmode"] == "verify-full"
    assert connect.call_args.kwargs["connect_timeout"] == 5
    with pytest.raises(ValueError, match="isolated local host"):
        loader.connect_target("local")
    assert connect.call_count == 1


def test_neon_cli_refuses_wrong_target_and_server_version(monkeypatch):
    import psycopg2

    connect = MagicMock()
    monkeypatch.setattr(psycopg2, "connect", connect)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture@localhost/neondb")
    with pytest.raises(ValueError, match="verified neondb"):
        loader.connect_target("neon")
    connect.assert_not_called()
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture@ep-test.neon.tech/neondb")
    conn = connect.return_value
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (17,)
    with pytest.raises(ValueError, match="PostgreSQL 18"):
        loader.connect_target("neon")
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "key,url",
    [
        (
            "aws-s3",
            "s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/part.parquet",
        ),
        (
            "aws",
            "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/release/2026-09-23.1/theme=places/type=place/part.parquet",
        ),
    ],
)
def test_inspected_stac_layouts_resolve_to_the_same_pinned_s3_path(key, url):
    assert extractor.official_s3_path({key: {"href": url}}, "2026-09-23.1") == (
        "overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/part.parquet"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://unreviewed.example/release/2026-09-23.1/theme=places/type=place/part.parquet",
        "s3://overturemaps-us-west-2/release/2026-10-01.0/theme=places/type=place/part.parquet",
        "s3://overturemaps-us-west-2/release/2026-09-23.1/theme=buildings/type=building/part.parquet",
        "s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/../part.parquet",
        "s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/part.parquet?override=1",
    ],
)
def test_actual_stac_compatibility_does_not_relax_source_guards(url):
    with pytest.raises(ValueError):
        extractor.official_s3_path({"aws": {"href": url}}, "2026-09-23.1")


def test_arrow_preserves_existing_proxy_and_tls_trust(monkeypatch):
    monkeypatch.setattr(extractor, "getproxies", lambda: {"https": "http://fixture-proxy:8080"})
    monkeypatch.setattr(extractor, "proxy_bypass", lambda host: False)
    monkeypatch.setenv("SSL_CERT_FILE", "/fixture/approved-ca.pem")
    options = extractor.s3_transport_options()
    assert options["proxy_options"] == "http://fixture-proxy:8080"
    assert options["tls_ca_file_path"] == "/fixture/approved-ca.pem"
    assert options["anonymous"] is True
    assert "tls_verify" not in options
    monkeypatch.setattr(extractor, "proxy_bypass", lambda host: True)
    assert "proxy_options" not in extractor.s3_transport_options()
