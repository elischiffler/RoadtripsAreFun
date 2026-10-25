"""Protect factual calendar bounds and immutable review replay."""

import hashlib
import json
from pathlib import Path

import pytest

from app.catalog import reviewed_entertainment as source

REVIEW = Path(source.__file__).with_name("entertainment_review.json")


def profiles():
    return {p["key"]: p for p in json.loads(REVIEW.read_text())["profiles"]}


def test_review_is_pinned_and_contains_no_numeric_attraction_ratings():
    assert hashlib.sha256(REVIEW.read_bytes()).hexdigest() == source.REVIEW_SHA256
    review = json.loads(REVIEW.read_text())
    assert len(review["profiles"]) == 13
    assert len({p["source_id"] for p in review["profiles"]}) == 13
    assert not any("rating" in k or "utility" in k for p in review["profiles"] for k in p)


def test_changed_review_is_rejected_before_source_replay(tmp_path):
    path = tmp_path / "review.json"
    path.write_bytes(REVIEW.read_bytes() + b" ")
    with pytest.raises(ValueError, match="identities or facts differ"):
        source.prepare(path)


def test_great_lakes_winter_tuesday_and_separate_ship_scope():
    p = profiles()["greatlakes"]
    dates = {r["date"]: r["windows"] for r in source.calendar_windows(p, "2026-10-27", 8)}
    assert dates["2026-10-27"]
    assert dates["2026-11-03"] == []
    assert "excludes" in p["description"] and "ships" in p["description"]


def test_carbon_monday_closes_after_october_and_weekend_remains_closed():
    p = profiles()["carbon"]
    dates = {r["date"]: r["windows"] for r in source.calendar_windows(p, "2026-10-26", 8)}
    assert dates["2026-10-26"][0]["closes"] == "15:00"
    assert dates["2026-11-01"] == []
    assert dates["2026-11-02"] == []


def test_clark_notice_overrides_late_hours_and_holiday_uncertainty_is_omitted():
    dates = {
        r["date"]: r["windows"]
        for r in source.calendar_windows(profiles()["clark"], "2026-10-27", 5)
    }
    assert dates["2026-10-27"][0]["closes"] == "17:00"
    assert dates["2026-10-30"][0]["closes"] == "23:00"
    dates = source.calendar_windows(profiles()["elko"], "2026-11-10", 3)
    assert "2026-11-11" not in {r["date"] for r in dates}


@pytest.mark.parametrize("days", [0, 31, True])
def test_no_extrapolation_beyond_review_horizon(days):
    with pytest.raises(ValueError, match="horizon"):
        source.calendar_windows(profiles()["reno"], "2026-10-25", days)
