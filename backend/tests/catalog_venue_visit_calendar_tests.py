"""Authentic source fragments plus negative replay and hard-visit regressions.

Fragments below retain exact factual literals from the October 15 official
snapshots; complete originals and hash/locator replay live in the reviewed
source bundle, not in the runtime application or these small test fixtures.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.catalog import venue_visit_calendar as venue
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit, source_calendar

WING_VISIBLE = "<h2>HOURS</h2><p>Wednesday - Sunday</p><p>10:00 AM - 5:00 PM</p>"
WING_STRUCTURED = "Mo 10:00-17:00, , We 10:00-17:00, Th 10:00-17:00, Fr 10:00-17:00, Sa 10:00-17:00, Su 10:00-17:00"
GLBT_VISIBLE = "Tuesday–Sunday:|11:00 a.m.–1:00 p.m. and 1:30 p.m.–5:00 p.m."
GLBT_MASK = "Please note: Masks are highly recommended in the museum, but are only required on Sundays & the first Wednesday of every month. For more details, please visit our"


def window(days, opens, closes, **more):
    return {"weekdays": days, "opens": opens, "closes": closes, "end_day_offset": 0, **more}


def layer(*windows):
    return {"windows": list(windows)}


def receipt():
    return {
        "source_url": "https://www.wingluke.org/visit",
        "snapshot_sha256": "b9067428916f476515a763b74245af0aa9c596c1500a2ac20dfbc7afa70d285a",
        "checked_at": "2026-10-15T19:44:57.685843+00:00",
    }


def structured(text):
    return venue.structured_layer({"kind": "jsonld", "path": ["openingHours"], "value": text})


def record(calendar):
    return {
        "provider_id": "overture:test",
        "categories": ["culture"],
        "source_provenance": [{"source_visit_calendar": calendar}],
    }


def compile_for(plan, layers, start="2026-10-15", end="2026-11-13"):
    return venue.compile_calendar(
        plan, layers, date.fromisoformat(start), date.fromisoformat(end), [receipt()]
    )


def test_authentic_wing_visible_and_structured_intersect_without_monday_or_extension():
    raw = (
        WING_VISIBLE
        + '<script type="application/ld+json">'
        + json.dumps({"openingHours": WING_STRUCTURED})
        + "</script>"
    ).encode()
    venue.validate_extraction(
        raw,
        {
            "kind": "visible_lines",
            "start_line": 2,
            "end_line": 3,
            "literal": "Wednesday - Sunday\n10:00 AM - 5:00 PM",
        },
    )
    venue.validate_extraction(
        raw,
        {"kind": "jsonld", "script_index": 0, "path": ["openingHours"], "value": WING_STRUCTURED},
    )
    layers = [layer(window([2, 3, 4, 5, 6], "10:00", "17:00")), structured(WING_STRUCTURED)]
    assert venue.intersect_layers(layers, date(2026, 10, 19)) == []
    assert venue.intersect_layers(layers, date(2026, 10, 15)) == [
        {"opens": "10:00", "closes": "17:00", "end_day_offset": 0}
    ]


def test_authentic_glbt_split_conflict_mask_and_dated_gala():
    raw = (
        '<meta charset="utf-8"><p>'
        + GLBT_VISIBLE.replace("|", "</p><p>")
        + "</p><p>"
        + GLBT_MASK
        + "</p>"
    ).encode()
    venue.validate_extraction(
        raw,
        {
            "kind": "visible_lines",
            "start_line": 2,
            "end_line": 2,
            "literal": GLBT_VISIBLE.split("|")[1],
        },
    )
    layers = [
        layer(
            window([1, 2, 3, 4, 5, 6], "11:00", "13:00"),
            window([1, 2, 3, 4, 5, 6], "13:30", "17:00"),
        ),
        structured(
            ", , We 10:30-17:00, Th 10:30-17:00, Fr 10:30-17:00, Sa 10:30-17:00, Su 10:30-17:00"
        ),
    ]
    plan = {
        "dated_closures": ["2026-10-17"],
        "omit_conditions": [
            {"kind": "weekday", "weekday": 6, "reason": "Sunday mask eligibility unknown"},
            {
                "kind": "first_weekday",
                "weekday": 2,
                "reason": "First-Wednesday mask eligibility unknown",
            },
        ],
    }
    calendar, withheld = compile_for(plan, layers)
    rows = {row["date"]: row["windows"] for row in calendar["date_overrides"]}
    assert rows["2026-10-17"] == []
    assert "2026-10-18" not in rows and "2026-11-04" not in rows
    assert "2026-10-20" not in rows  # Visible Tuesday conflicts with structured weekdays.
    assert {row["date"] for row in withheld} >= {"2026-10-18", "2026-11-04"}
    zone = ZoneInfo("America/Los_Angeles")
    start, proof = solve_visit(
        record(calendar),
        datetime(2026, 10, 15, 12, tzinfo=zone),
        datetime(2026, 10, 15, 17, tzinfo=zone),
    )
    assert (start.hour, start.minute) == (13, 30)
    assert proof["visit_end"].startswith("2026-10-15T15:30")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            record(calendar),
            datetime(2026, 10, 17, 11, tzinfo=zone),
            datetime(2026, 10, 17, 17, tzinfo=zone),
        )


def test_last_entry_clips_entire_visit_and_party_conditions_stay_held():
    # Authentic Connections: 10 am–3 pm Sunday, doors close at 2:30pm;
    # parents of under-twelves are asked to visit first. No party proof is fabricated.
    plan = {"holds": ["Unknown prior parent visit and child ages"]}
    calendar, _ = compile_for(plan, [layer(window([6], "10:00", "15:00", last_entry="14:30"))])
    sunday = next(row for row in calendar["date_overrides"] if row["date"] == "2026-10-18")
    assert sunday["windows"][0]["closes"] == "14:30"
    zone = ZoneInfo("America/Los_Angeles")
    with pytest.raises(VisitCalendarConflict, match="unknown"):
        solve_visit(
            record(calendar),
            datetime(2026, 10, 18, 10, tzinfo=zone),
            datetime(2026, 10, 18, 17, tzinfo=zone),
        )
    # Even with eligible party support, 13:00 + full two-hour dwell cannot fit the cutoff.
    calendar["unknown_reasons"] = []
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            record(calendar),
            datetime(2026, 10, 18, 13, tzinfo=zone),
            datetime(2026, 10, 18, 17, tzinfo=zone),
        )


def test_conflicting_richmond_hidden_clocks_do_not_get_silently_discarded():
    assert (
        venue.intersect_layers(
            [
                layer(window([2, 3, 4, 5, 6], "11:00", "16:00")),
                structured(
                    ", , We 01:00-05:00, Th 01:00-05:00, Fr 01:00-05:00, Sa 01:00-05:00, Su 01:00-05:00"
                ),
            ],
            date(2026, 10, 15),
        )
        == []
    )


def test_alaska_literal_season_branch_does_not_open_winter_sundays():
    layers = [
        layer(
            window([0, 1, 2, 3, 4, 5], "10:00", "17:00", months=[1, 2]),
            window(list(range(7)), "10:00", "17:00", months=list(range(3, 13))),
        )
    ]
    assert venue.intersect_layers(layers, date(2027, 1, 3)) == []
    assert venue.intersect_layers(layers, date(2026, 11, 1))


def test_operator_holidays_are_exact_not_guessed_observed_holidays():
    # Wing Luke literally names July 4th, not the federal July 3 observance.
    calendar, _ = compile_for(
        {"annual_closures": ["07-04"]},
        [layer(window(list(range(7)), "10:00", "17:00"))],
        "2026-07-01",
        "2026-07-10",
    )
    rows = {row["date"]: row["windows"] for row in calendar["date_overrides"]}
    assert rows["2026-07-03"] and rows["2026-07-04"] == []
    zone = ZoneInfo("America/Los_Angeles")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            record(calendar),
            datetime(2026, 7, 4, 10, tzinfo=zone),
            datetime(2026, 7, 4, 17, tzinfo=zone),
        )


def test_this_week_does_not_invent_future_annual_recurrence_or_timezone():
    calendar, _ = compile_for(
        {},
        [
            {
                "windows": [window(list(range(7)), "11:00", "22:00")],
                "start": "2026-10-15",
                "end": "2026-10-21",
            }
        ],
    )
    assert [row["date"] for row in calendar["date_overrides"]] == [
        f"2026-10-{n}" for n in range(15, 22)
    ]
    assert calendar["weekly_windows"] == calendar["seasons"] == calendar["fixed_starts"] == []
    assert source_calendar(record(calendar)) is not None
    zone = ZoneInfo("America/Los_Angeles")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            record(calendar),
            datetime(2026, 10, 22, 11, tzinfo=zone),
            datetime(2026, 10, 22, 22, tzinfo=zone),
        )


@pytest.mark.parametrize("bad", ["Mo 4:30-8:30", "Sa 11pm-5pm", "Th 10:00-", "XX 10:00-17:00"])
def test_ambiguous_or_incomplete_clock_syntax_fails_closed(bad):
    with pytest.raises(venue.VenueCalendarError):
        structured(bad)


def test_missing_or_mutated_literal_locator_is_rejected():
    raw = WING_VISIBLE.encode()
    with pytest.raises(venue.VenueCalendarError, match="literal"):
        venue.validate_extraction(
            raw,
            {
                "kind": "visible_lines",
                "start_line": 3,
                "end_line": 3,
                "literal": "10:00 AM - 8:00 PM",
            },
        )
    with pytest.raises(venue.VenueCalendarError, match="bounds"):
        venue.validate_extraction(
            raw, {"kind": "visible_lines", "start_line": 99, "end_line": 99, "literal": ""}
        )


def test_receipt_rejects_changed_bytes_stale_and_future_sources(tmp_path):
    raw = WING_VISIBLE.encode()
    file = tmp_path / "source.bin"
    file.write_bytes(raw)
    source = {
        "source_url": "https://www.wingluke.org/visit",
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "checked_at": "2026-10-15T19:00:00+00:00",
        "body_path": "source.bin",
        "bytes": len(raw),
        "role": "current",
        "extractions": [
            {
                "kind": "visible_lines",
                "start_line": 2,
                "end_line": 2,
                "literal": "Wednesday - Sunday",
            }
        ],
    }
    venue._receipt(tmp_path, source, datetime(2026, 10, 15, 20, tzinfo=UTC))
    with pytest.raises(venue.VenueCalendarError, match="future"):
        venue._receipt(tmp_path, source, datetime(2026, 10, 15, 18, tzinfo=UTC))
    with pytest.raises(venue.VenueCalendarError, match="thirty"):
        venue._receipt(tmp_path, source, datetime(2026, 11, 16, tzinfo=UTC))
    file.write_bytes(raw.replace(b"10:00", b"12:00"))
    with pytest.raises(venue.VenueCalendarError, match="SHA256"):
        venue._receipt(tmp_path, source, datetime(2026, 10, 15, 20, tzinfo=UTC))


def test_unreviewed_inventory_cannot_change_admissions(tmp_path):
    (tmp_path / venue.INVENTORY_FILE).write_text('{"items":[]}')
    with pytest.raises(venue.VenueCalendarError, match="inventory SHA256"):
        venue.build_entries(tmp_path, checked_at="2026-10-15T21:00:00+00:00")


def test_authentic_phoenix_embedded_dated_admission_closure_and_member_preview():
    # Literal dated card facts from the retained official calendar script.
    events = [
        {
            "date": "10/21/2026",
            "events": [
                {
                    "card": '<p class="event-item__title">General Admission</p><em>10:00 am - 3:00 pm</em>'
                }
            ],
        }
    ]
    raw = (
        "<script>var eventsList = " + json.dumps(events) + ";var following = 1;</script>"
    ).encode()
    venue.validate_extraction(
        raw,
        {
            "kind": "javascript_json",
            "script_index": 0,
            "assignment": "eventsList",
            "path": [0, "date"],
            "value": "10/21/2026",
        },
    )
    venue.validate_extraction(
        raw,
        {
            "kind": "javascript_json",
            "script_index": 0,
            "assignment": "eventsList",
            "path": [0, "events", 0, "card"],
            "html_xpath": "string(//em)",
            "value": "10:00 am - 3:00 pm",
        },
    )
    layers = [
        layer(window([2, 4], "10:00", "20:00")),
        {
            "date_windows": {
                "2026-10-21": [window(list(range(7)), "10:00", "15:00")],
                "2026-11-13": [window(list(range(7)), "10:00", "20:00")],
            }
        },
    ]
    plan = {
        "dated_closures": ["2026-10-20"],
        "omit_conditions": [
            {
                "kind": "date",
                "date": "2026-11-13",
                "reason": "Member Preview membership/scope unknown",
            }
        ],
    }
    cal, held = compile_for(plan, layers)
    rows = {row["date"]: row["windows"] for row in cal["date_overrides"]}
    assert rows["2026-10-21"][0]["closes"] == "15:00"
    assert rows["2026-10-20"] == []
    assert "2026-11-13" not in rows
    assert held == [
        {"date": "2026-11-13", "unknown_reasons": ["Member Preview membership/scope unknown"]}
    ]
    zone = ZoneInfo("America/Phoenix")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            record(cal),
            datetime(2026, 10, 21, 14, tzinfo=zone),
            datetime(2026, 10, 21, 20, tzinfo=zone),
        )


def test_equal_structured_clocks_do_not_guess_closed_or_twenty_four_hours():
    with pytest.raises(venue.VenueCalendarError, match="equal"):
        structured("Mo 10:00-10:00")
