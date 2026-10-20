"""Synthetic corridor checks never use a hosted catalog to clear local gates."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "catalog_route_coverage",
    Path(__file__).resolve().parents[2] / "scripts/catalog_route_coverage.py",
)
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


def candidate(key="example", *, latitude=37.0, longitude=-122.0, calendar=None):
    return {
        "source_id": key,
        "provider_id": key,
        "coordinates": [latitude, longitude],
        "categories": ["daytime"],
        "source_provenance": [{"source_visit_calendar": calendar}] if calendar else [],
    }


def hours(**overrides):
    return {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [{"weekdays": list(range(7)), "opens": "09:00", "closes": "11:00"}],
        "source_receipts": [{"path": "synthetic-official-hours.json"}],
        **overrides,
    }


def route(*points):
    return {
        "id": "synthetic-road",
        "samples": list(points) or [[37.0, -122.0]],
        "receipt": {"scope": "synthetic test geometry"},
    }


def test_unknown_hours_count_only_as_structural_and_calendar_holds_fail_closed():
    result = coverage.coverage(
        [
            candidate("unknown"),
            candidate("verified", calendar=hours()),
            candidate("held", calendar=hours(unknown_reasons=["parking access unknown"])),
        ],
        [route()],
        [date(2026, 10, 20)],
    )
    corridor = result["corridors"]["synthetic-road"]
    assert corridor["source_ids"] == ["unknown", "verified"]
    assert corridor["structural_hits"] == 2
    assert corridor["verified_calendar_hits"] == 1
    assert corridor["published_clock_full_dwell_hits_by_local_date"] == {"2026-10-20": 1}
    assert "not an actual-arrival" in result["scope"]
    assert result["clock_check"]["arithmetic_zone"].startswith("artificial UTC")


def test_five_mile_radius_and_sixty_result_cap_are_applied_per_sample():
    nearby = [candidate(f"near-{n:03}") for n in range(61)]
    result = coverage.coverage(
        [*nearby, candidate("far", latitude=37.2)], [route()], [date(2026, 10, 20)]
    )["corridors"]["synthetic-road"]
    assert result["structural_hits"] == 60
    assert result["samples_exceeding_sixty_results"] == 1
    assert "near-060" not in result["source_ids"]
    assert "far" not in result["source_ids"]


def test_full_dwell_does_not_join_disjoint_windows_and_honors_source_local_dates():
    split = hours(
        weekly_windows=[
            {"weekdays": list(range(7)), "opens": "09:00", "closes": "10:00"},
            {"weekdays": list(range(7)), "opens": "11:00", "closes": "12:00"},
        ]
    )
    assert not coverage.published_clock_fit(candidate(calendar=split), date(2026, 10, 20), 7200)
    assert coverage.published_clock_fit(candidate(calendar=split), date(2026, 10, 20), 3600)
    limited = hours(
        seasons=[{"kind": "dated", "start": "2026-10-20", "end": "2026-10-22"}],
        date_overrides=[{"date": "2026-10-21", "windows": []}],
    )
    record = candidate(calendar=limited)
    assert coverage.published_clock_fit(record, date(2026, 10, 20), 7200)
    assert not coverage.published_clock_fit(record, date(2026, 10, 20), 7201)
    assert not coverage.published_clock_fit(record, date(2026, 10, 21), 7200)
    assert not coverage.published_clock_fit(record, date(2026, 10, 23), 7200)


def test_fixed_start_instants_require_actual_timezone_and_are_not_counted_as_clock_proof():
    record = candidate(calendar=hours(fixed_starts=["2026-10-20T09:00:00-07:00"]))
    assert not coverage.published_clock_fit(record, date(2026, 10, 20), 7200)


def test_empty_route_samples_and_invalid_dwell_do_not_silently_expand_scope():
    for dwell in (True, 0, 86401):
        with pytest.raises(ValueError, match="bounded"):
            coverage.coverage([], [route()], [date(2026, 10, 20)], dwell_seconds=dwell)
    with pytest.raises(ValueError, match="bounded"):
        coverage.coverage([], [route()], [])


def test_duplicate_snapshot_identity_is_rejected():
    row = {
        "source_id": "nps-public:test",
        "name": "Synthetic",
        "latitude": 37,
        "longitude": -122,
        "categories": ["daytime"],
        "provenance": [],
    }
    with pytest.raises(ValueError, match="duplicate"):
        coverage.candidates([row, row], [])
