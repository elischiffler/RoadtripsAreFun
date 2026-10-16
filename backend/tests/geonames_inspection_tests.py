"""Schema-only synthetic rows; no actual GeoNames or Kaggle archive is validated."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from app.catalog.ingest import prepare

spec = importlib.util.spec_from_file_location(
    "inspect_geonames", Path(__file__).resolve().parents[2] / "scripts/inspect_geonames.py"
)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def source_row(**updates):
    fields = [
        "123",
        "Synthetic Museum",
        "Synthetic Museum",
        "",
        "37.8",
        "-122.4",
        "S",
        "MUS",
        "US",
        "",
        "CA",
        "",
        "",
        "",
        "0",
        "",
        "0",
        "America/Los_Angeles",
        "2026-09-01",
    ]
    for index, value in updates.items():
        fields[int(index)] = value
    return ("\t".join(fields) + "\n").encode()


def inspect_rows(tmp_path, rows, **limits):
    source = tmp_path / "source.txt"
    source.write_bytes(b"".join(rows))
    output = tmp_path / "leads.jsonl"
    report = inspector.inspect(
        source, output, regions={"CA", "AK", "HI"}, feature_codes={"S.MUS", "L.AMUS"}, **limits
    )
    return output, report


def test_preserves_source_order_identity_and_explicitly_unverified_evidence(tmp_path):
    output, report = inspect_rows(tmp_path, [source_row(), source_row(**{"0": "456", "10": "HI"})])
    first, second = map(json.loads, output.read_text().splitlines())
    assert first["source_id"] == "geonames:123" and second["region"] == "HI"
    assert first["source_point"] == {
        "latitude": 37.8,
        "longitude": -122.4,
        "arrival_verified": False,
    }
    assert first["arrival_point"] is None and first["current_operation_evidence"] is None
    assert first["rights_review"] == "unreviewed" and first["import_eligible"] is False
    assert report["accepted_for_import"] == 0 and report["kaggle_compatibility"] == "unverified"
    assert report["regions"] == {"CA": 1, "HI": 1}
    assert report["complete_input_scan"] is True
    assert report["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    # Review files cannot be mistaken for an approved import bundle.
    with pytest.raises(ValueError, match="manifest missing"):
        prepare(output, report)


@pytest.mark.parametrize(
    "row,reason",
    [
        (b"id,name,latitude,longitude\n", "column_count"),
        (b"\xff\n", "encoding"),
        (source_row(**{"8": "CA"}), "country_region"),
        (source_row(**{"10": "PR"}), "country_region"),
        (source_row(**{"10": "00"}), "country_region"),
        (source_row(**{"6": "P", "7": "PPL"}), "feature_code"),
        (source_row(**{"0": "0"}), "identity"),
        (source_row(**{"1": ""}), "identity"),
        (source_row(**{"4": "nan"}), "coordinates"),
        (source_row(**{"5": "inf"}), "coordinates"),
        (source_row(**{"4": "91"}), "coordinates"),
        (source_row(**{"18": "2025-02-30"}), "modification_date"),
        (source_row(**{"18": "9999-01-01"}), "modification_date"),
    ],
)
def test_rejects_unrecognized_schema_scope_and_invalid_source_fields(row, reason):
    assert inspector.parse_line(row, {"CA"}, {"S.MUS"}) == (None, reason)


def test_limits_do_not_parse_partial_rows_or_claim_full_scan(tmp_path):
    first = source_row()
    second = source_row(**{"0": "456"})
    output, report = inspect_rows(tmp_path, [first, second], max_bytes=len(first) + 5)
    assert len(output.read_text().splitlines()) == 1
    assert report["scanned_rows"] == 1 and report["scanned_bytes"] == len(first) + 5
    assert report["scanned_prefix_sha256"] == hashlib.sha256(first + second[:5]).hexdigest()
    assert report["stop_reason"] == "byte_limit" and report["complete_input_scan"] is False


@pytest.mark.parametrize(
    "limit,stop", [("max_candidates", "candidate_limit"), ("max_scanned", "scan_limit")]
)
def test_stops_before_processing_another_row(tmp_path, limit, stop):
    output, report = inspect_rows(tmp_path, [source_row(), b"x" * 70_000], **{limit: 1})
    assert report["stop_reason"] == stop and report["scanned_rows"] == 1
    assert len(output.read_text().splitlines()) == 1


def test_duplicates_are_conservative_and_conflicts_never_publish(tmp_path):
    _, report = inspect_rows(tmp_path, [source_row(), source_row()])
    assert report["review_candidates"] == 1 and report["rejects"] == {"duplicate": 1}
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="conflicting duplicate"):
        inspect_rows(other, [source_row(), source_row(**{"1": "Different synthetic venue"})])
    assert not (other / "leads.jsonl").exists()
    assert not (other / "leads.jsonl.review.json").exists()


def test_no_overwrite_and_oversized_source_line_never_publishes(tmp_path):
    output = tmp_path / "leads.jsonl"
    output.write_text("preserve")
    with pytest.raises(ValueError, match="already exists"):
        inspect_rows(tmp_path, [source_row()])
    assert output.read_text() == "preserve"
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="64 KiB"):
        inspect_rows(other, [b"x" * 70_000])
    assert not (other / "leads.jsonl").exists()


@pytest.mark.parametrize("value", [0, -1, 501, True])
def test_refuses_invalid_or_increased_candidate_limit(tmp_path, value):
    with pytest.raises(ValueError, match="hard ceilings"):
        inspect_rows(tmp_path, [source_row()], max_candidates=value)


def test_monotonic_deadline_stops_without_reading_source_row(tmp_path, monkeypatch):
    clock = iter([0, 31])
    monkeypatch.setattr(inspector.time, "monotonic", lambda: next(clock))
    output, report = inspect_rows(tmp_path, [source_row()])
    assert output.read_bytes() == b""
    assert report["stop_reason"] == "time_limit" and report["scanned_rows"] == 0
    assert report["accepted_for_import"] == 0


def test_partial_publication_failure_preserves_existing_report(tmp_path, monkeypatch):
    original_link = inspector.os.link
    report_path = tmp_path / "leads.jsonl.review.json"

    def collision(source, destination):
        if Path(destination) == report_path:
            report_path.write_text("concurrent report")
        original_link(source, destination)

    monkeypatch.setattr(inspector.os, "link", collision)
    with pytest.raises(FileExistsError):
        inspect_rows(tmp_path, [source_row()])
    assert not (tmp_path / "leads.jsonl").exists()
    assert report_path.read_text() == "concurrent report"
