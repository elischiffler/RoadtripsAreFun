"""Exact reviewed USFS literals, conflict guards and optional whole-source replay."""

import hashlib
import json
import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.catalog import usfs_visit_calendar as usfs
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


@pytest.fixture(scope="module")
def rows():
    # The original500 rows are unchanged in557; use the committed immutable facts
    # for normal CI. Only the explicit private replay admits full source bodies.
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/data/catalog-expansion-500-20261015/reviewed-500.preview.jsonl"
    )
    return {
        row["source_id"].split(":")[-1]: row
        for row in map(json.loads, path.read_text().splitlines())
        if row["source_id"].startswith("usfs:")
    }


def _literal_inputs(row):
    provenance = row["provenance"][0]
    originals = {}
    for label, fact in provenance["published_access_facts"].items():
        matches = [
            key
            for key, receipt in usfs._SOURCES.items()
            if receipt["snapshot_sha256"] == fact["snapshot_sha256"]
        ]
        assert len(matches) == 1
        originals[label] = (matches[0], deepcopy(fact["fields"]), deepcopy(fact))
    public = deepcopy(originals["public_feed"][2]["fields"])
    constructed = deepcopy(originals["construction_feed"][2]["fields"])
    ident = str(provenance["public_record_id"])
    public.update(recareaid=int(ident), infra_cn=None)
    constructed.update(
        site_cn=provenance["record_id"],
        usda_portal_id=ident,
        latitude=row["latitude"],
        longitude=row["longitude"],
        globalid=provenance["global_id"],
        recarea_enable="Y",
    )
    return public, constructed, originals


def _entry(row):
    ident = row["source_id"].split(":")[-1]
    public, constructed, originals = _literal_inputs(row)
    assert usfs._qualify(ident, row, public, constructed, originals) is None
    constraints = usfs._constraints(ident, row, public, constructed, originals)
    return usfs._entry(ident, row, public, constructed, constraints)


def _fits(entry, literal, zone="America/Los_Angeles"):
    start = datetime.fromisoformat(literal).replace(tzinfo=ZoneInfo(zone))
    record = {"provider_id": entry["source_id"], "source_provenance": [entry]}
    try:
        _, proof = solve_visit(record, start, start + timedelta(hours=2))
        assert proof["dwell_seconds"] == 7200
        assert proof["ticket_availability"] == "unknown"
        return True
    except VisitCalendarConflict:
        return False


@pytest.mark.parametrize(
    "ident,start,end",
    [
        ("29918", "09:00", "17:00"),
        ("35235", "06:00", "22:00"),
        ("64853", "06:00", "22:00"),
        ("39566", "10:00", "17:00"),
        ("20698", "08:30", "16:15"),
    ],
)
def test_authentic_explicit_clocks_and_immutable_originals(rows, ident, start, end):
    before = deepcopy(rows[ident])
    entry = _entry(rows[ident])
    assert rows[ident] == before
    window = entry["source_visit_calendar"]["date_overrides"][0]["windows"][0]
    assert window["opens"] == start
    assert window["closes"] == end
    assert _fits(entry, "2026-10-15T" + start)
    assert entry["transformation"]["admission_price"] == "unknown"
    assert entry["transformation"]["visitor_html_status"] == 403


def test_eastern_sierra_gate_conservatively_bounds_full_visit(rows):
    entry = _entry(rows["20698"])
    assert _fits(entry, "2026-10-15T14:15")
    assert not _fits(entry, "2026-10-15T14:16")
    assert "16:30" in entry["transformation"]["gate_interpretation"]
    assert "4:30 p.m." in entry["source_constraints"][0]["literal_fields"]["operational_hours"]
    assert "4:15 p.m." in entry["source_constraints"][0]["literal_fields"]["operational_hours"]


def test_gladie_uses_thursday_through_sunday_only(rows):
    entry = _entry(rows["39566"])
    assert _fits(entry, "2026-10-18T10:00", "America/New_York")
    assert not _fits(entry, "2026-10-19T10:00", "America/New_York")
    assert _fits(entry, "2026-10-15T15:00", "America/New_York")
    assert not _fits(entry, "2026-10-15T15:01", "America/New_York")


@pytest.mark.parametrize("ident", sorted(usfs._PROFILES))
def test_policy_bounds_and_unverified_holiday_are_unknown_not_closed(rows, ident):
    entry = _entry(rows[ident])
    assert not entry["source_visit_calendar"]["weekly_windows"]
    assert not any(
        d["date"] == "2026-11-11" for d in entry["source_visit_calendar"]["date_overrides"]
    )
    assert not _fits(entry, "2026-11-11T12:00")
    assert not _fits(entry, "2026-11-14T12:00")
    assert not _fits(entry, "2026-10-14T12:00")
    assert entry["transformation"]["policy_scope_is_source_publication_or_expiry_claim"] is False
    assert not entry["source_visit_calendar"].get("annual_closures")


def test_sears_kay_day_use_and_no_trailers_restrictions_stay_separate(rows):
    entry = _entry(rows["35235"])
    facts = entry["source_constraints"]
    assert "no trailers" in facts[0]["literal_fields"]["restrictions"]
    assert "no trailers" in facts[1]["literal_fields"]["restrictions"]
    assert "no trailers" in facts[2]["literal_fields"]["restrictions"]
    assert "no trailers" in facts[3]["literal_fields"]["restrictions"]
    assert entry["transformation"]["additional_access_conditions"] == {
        "day_use_only": True,
        "trailers": "prohibited",
    }
    assert entry["transformation"]["identity_join"]["public_infra_cn"] is None


@pytest.mark.parametrize(
    "channel,field,value",
    [
        ("public", "openstatus", "closed"),
        ("construction", "seasonal_operational_status", "CLOSED"),
        ("construction", "recarea_enable", "N"),
    ],
)
def test_open_enum_never_overrides_closed_or_disabled_feed(rows, channel, field, value):
    row = rows["29918"]
    public, constructed, originals = _literal_inputs(row)
    (public if channel == "public" else constructed)[field] = value
    assert "OPEN/open" in usfs._qualify("29918", row, public, constructed, originals)


@pytest.mark.parametrize(
    "channel,field,value",
    [
        ("construction", "site_cn", "wrong"),
        ("construction", "usda_portal_id", "35235"),
        ("public", "recareaid", 35235),
        ("public", "infra_cn", "wrong"),
        ("construction", "latitude", 45.65351),
        ("construction", "globalid", "wrong"),
    ],
)
def test_native_identity_or_coordinate_disagreement_is_withheld(rows, channel, field, value):
    row = rows["29918"]
    public, constructed, originals = _literal_inputs(row)
    (public if channel == "public" else constructed)[field] = value
    assert "identity or unchanged construction coordinates" in usfs._qualify(
        "29918", row, public, constructed, originals
    )


def test_original_season_restriction_is_not_replaced_by_open_status(rows):
    row = rows["29918"]
    public, constructed, originals = _literal_inputs(row)
    originals["public_feed"][2]["fields"]["open_season_end"] = "October 14"
    assert "Original and current" in usfs._qualify("29918", row, public, constructed, originals)


def test_unknown_season_or_negative_cannot_be_ignored_even_when_feeds_agree(rows):
    row = rows["29918"]
    public, constructed, originals = _literal_inputs(row)
    public["open_season_end"] = "weather depending"
    originals["public_feed"][2]["fields"]["open_season_end"] = "weather depending"
    assert "qualification unresolved" in usfs._qualify("29918", row, public, constructed, originals)


@pytest.mark.parametrize("ident", [i for i in usfs._SELECTED_IDS if i not in usfs._PROFILES])
def test_other_fourteen_are_not_invented_from_all_day_year_round_or_solar(rows, ident):
    row = rows[ident]
    public, constructed, originals = _literal_inputs(row)
    assert usfs._qualify(ident, row, public, constructed, originals) is not None


def test_current_truncation_and_duplicate_id_are_not_accepted():
    payload = {
        "geometryType": "esriGeometryPoint",
        "spatialReference": {"wkid": 4326},
        "features": [{"attributes": {"recareaid": 29918}}],
        "exceededTransferLimit": True,
    }
    with pytest.raises(ValueError, match="truncation"):
        usfs._features(json.dumps(payload).encode(), "recareaid", expected=19)
    payload.pop("exceededTransferLimit")
    payload["features"] *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        usfs._features(json.dumps(payload).encode(), "recareaid")


def test_source_hash_guard_and_no_path_escape(tmp_path):
    p = tmp_path / "source.body"
    p.write_bytes(b"official source unchanged")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert usfs._read(tmp_path, p.name, sha) == p.read_bytes()
    p.write_bytes(b"official source changed")
    with pytest.raises(ValueError, match="checksum"):
        usfs._read(tmp_path, p.name, sha)
    with pytest.raises(ValueError, match="escapes"):
        usfs._read(tmp_path, "../source.body", sha)


def test_complete_authentic_offline_replay_and_corruption_gate(tmp_path):
    source_root = os.environ.get("USFS_CALENDAR_SOURCE_ROOT")
    if not source_root:
        pytest.skip("Set USFS_CALENDAR_SOURCE_ROOT to the private frozen originals")
    result = usfs.build_enrichments(source_root, reviewed_on=date(2026, 10, 15))
    assert result == usfs.build_enrichments(source_root, reviewed_on=date(2026, 10, 15))
    assert result["summary"]["positive_clock_supplements"] == 5
    assert result["summary"]["withheld_unknown"] == 14
    assert len(result["holds"]) == 19
    assert len({h["source_id"] for h in result["holds"]}) == 19
    assert sum(h["visitor_html_status"] == 403 for h in result["holds"]) == 5
    for entry in result["entries"]:
        assert all(
            {"source_url", "snapshot_sha256", "checked_at", "evidence_path"} <= set(r)
            for r in entry["source_visit_calendar"]["source_receipts"]
        )
    # Whole-batch loading fails on altered source bytes before producing entries.
    root = Path(source_root)
    baseline = tmp_path / "baseline557.preview.jsonl"
    baseline.write_bytes((root / baseline.name).read_bytes())
    first = next(iter(usfs._SOURCES.values()))
    body = tmp_path / first["evidence_path"]
    body.parent.mkdir(exist_ok=True, parents=True)
    body.write_bytes((root / first["evidence_path"]).read_bytes() + b"altered")
    with pytest.raises(ValueError, match="checksum"):
        usfs.build_enrichments(tmp_path, reviewed_on=date(2026, 10, 15))
