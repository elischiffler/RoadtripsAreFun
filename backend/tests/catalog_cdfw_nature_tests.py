"""Solar boundaries and reviewed-arrival rejection; synthetic geometry stays test-only."""

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from astral import Observer
from astral.sun import sun

from app.catalog import cdfw_nature as source
from app.routing.visit_calendar import Calendar


def test_solar_windows_follow_dst_round_inward_and_end_without_weekly_fallback():
    zone = ZoneInfo("America/Los_Angeles")
    windows = source.solar_windows(33.69, -118.04, "2026-10-31", 3, str(zone))
    for item in windows:
        day = date.fromisoformat(item["date"])
        actual = sun(Observer(33.69, -118.04), date=day, tzinfo=zone)
        w = item["windows"][0]
        opening = datetime.fromisoformat(item["date"] + "T" + w["opens"]).replace(tzinfo=zone)
        closing = datetime.fromisoformat(item["date"] + "T" + w["closes"]).replace(tzinfo=zone)
        assert 0 <= (opening - actual["sunrise"]).total_seconds() < 60
        assert 0 <= (actual["sunset"] - closing).total_seconds() < 60
    assert windows[0]["windows"][0]["opens"] > windows[1]["windows"][0]["opens"]
    calendar = Calendar.model_validate(
        {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "source_receipts": [{"fixture": True}],
            "date_overrides": windows,
        }
    )
    assert not calendar.weekly_windows and len(calendar.date_overrides) == 3
    assert str(calendar.date_overrides[-1].date) == "2026-11-02"


def test_source_fixed_clocks_intersect_instead_of_extending_daylight():
    w = source.solar_windows(
        33.69, -118.04, "2026-10-24", 1, "America/Los_Angeles", ["10:00", "16:00"]
    )
    assert w[0]["windows"][0] == {"opens": "10:00", "closes": "16:00", "end_day_offset": 0}
    for lat, lon, days in [(float("nan"), 0, 1), (91, 0, 1), (0, 181, 1), (0, 0, 31)]:
        with pytest.raises(ValueError):
            source.solar_windows(lat, lon, "2026-10-24", days, "UTC")


def test_review_cannot_self_authorize_changed_places_dates_or_hashes(tmp_path):
    pinned = Path(source.__file__).with_name("cdfw_nature_review.json")
    review = json.loads(pinned.read_text())
    review["profiles"][0]["node"] = 123
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="bindings differ"):
        source.prepare(path)


@pytest.mark.parametrize(
    "access", ['<tag k="access" v="private"/>', '<tag k="motor_vehicle" v="no"/>']
)
def test_private_native_road_never_becomes_public_parking(access):
    xml = f"""<osm><node id="1" lat="33.7" lon="-118.1"/><node id="2" lat="33.7001" lon="-118.1"/>
      <way id="3"><nd ref="1"/><tag k="highway" v="service"/>{access}</way>
      <way id="4"><nd ref="2"/><tag k="amenity" v="parking"/></way></osm>""".encode()
    with pytest.raises(ValueError, match="public driving"):
        source.native_arrival(
            {"ways": [3], "road": 3, "parking": 4, "node": 1}, {"osm-way-3.xml": xml}
        )
