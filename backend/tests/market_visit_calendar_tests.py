"""Literal market calendars narrow all feeds and preserve their receipts."""

import copy
import json

import pytest

from app.catalog import market_visit_calendar as calendars


def facts(*, native="Year Round (Saturday)", canonical=None, **official):
    def fact(feed, fields, digest):
        return {
            "feed": feed,
            "source_url": "https://example.gov/market-original",
            "snapshot_sha256": digest * 64,
            "checked_at": "2026-10-15T18:00:00+00:00",
            "fields": fields,
        }

    return [
        fact("kaggle_feed", {"season": native}, "a"),
        fact("canonical_feed", {"season": native if canonical is None else canonical}, "b"),
        fact(
            "official_visitor_facts",
            {"days": "Sat", "hours": "9am - 2pm", "months": "Year Round", **official},
            "c",
        ),
    ]


def window(days, opens, closes, offset=0):
    return {"weekdays": days, "opens": opens, "closes": closes, "end_day_offset": offset}


def test_burlington_has_only_saturday_9_to_14_and_every_feed_season():
    source = facts(
        native="June to October",
        days="Every Saturday",
        hours="9:00 am - 2:00pm",
        months=None,
        start="2026-05-09",
        end="2026-10-31",
        weather_qualification="Rain or shine.",
    )
    untouched = copy.deepcopy(source)
    result = calendars.build(source)
    assert result["schema_version"] == "roadtrips-source-visit-calendar/1"
    # Thu Oct 15 and Sat Oct 17 16:00 cannot fit this emitted weekly window.
    assert result["weekly_windows"] == [window([5], "09:00", "14:00")]
    assert result["seasons"] == [{"kind": "dated", "start": "2026-06-01", "end": "2026-10-31"}]
    assert result["unknown_reasons"] == []
    assert result["date_overrides"] == result["fixed_starts"] == []
    assert "timezone" not in result
    assert source == untouched
    assert result["source_receipts"] == source


def test_native_and_canonical_weekdays_clocks_and_seasons_all_narrow_official():
    result = calendars.build(
        facts(
            native="Saturdays 8am-1pm, May to October",
            canonical="Saturday 9am-12pm, June to September",
            days="Fri and Sat",
            hours="8:30am - 2pm",
            months="Apr 1 - Oct 7",
        )
    )
    assert result["weekly_windows"] == [window([5], "09:00", "12:00")]
    assert result["seasons"] == [{"kind": "annual", "start": "06-01", "end": "09-30"}]
    assert result["unknown_reasons"] == []


@pytest.mark.parametrize("feed", [0, 1, 2])
@pytest.mark.parametrize(
    "restriction,expected",
    [
        ({"days": "Sunday"}, "empty_weekday_intersection"),
        ({"hours": "3pm - 4pm"}, "empty_clock_intersection"),
        ({"months": "November to December"}, "empty_season_intersection"),
    ],
)
def test_each_feed_can_withhold_conflicting_calendar(feed, restriction, expected):
    source = facts(native="Saturdays 9am-2pm, June to October", months="June to October")
    source[feed]["fields"].update(restriction)
    result = calendars.build(source)
    assert expected in result["unknown_reasons"]
    assert result["weekly_windows"] == result["seasons"] == []


@pytest.mark.parametrize(
    "hours",
    [
        "4-9 pm",
        "2:00-6:30 PM",
        "3:00-6:00pm",
        "2:30 - 5:30pm, 5pm winter",
        "9am - 2pm except holidays",
        "9am - 2pm weather permitting",
        "9am - 2pm and 4pm - 7pm",
        "13pm - 2pm",
        "9:60am - 2pm",
        "9am - 9am",
        "09:00 - 2pm",
        "09:00 - 02:00",
        "10:00 - 11:00",
        "9am - 2pm and",
        "open all day",
        "9 - 14",
    ],
)
def test_ambiguous_or_qualified_official_hours_are_unknown(hours):
    result = calendars.build(facts(hours=hours))
    assert result["unknown_reasons"]
    assert result["weekly_windows"] == result["seasons"] == []
    assert result["source_receipts"][2]["fields"]["hours"] == hours


@pytest.mark.parametrize("feed", [0, 1])
def test_ambiguous_native_clock_cannot_be_replaced_by_clear_official_clock(feed):
    source = facts()
    source[feed]["fields"]["season"] = "Year-round · Saturdays 2:00–6:30 PM"
    result = calendars.build(source)
    assert result["unknown_reasons"]
    assert result["weekly_windows"] == []


@pytest.mark.parametrize(
    "native,official_days,official_hours,months,expected",
    [
        (
            "Year Round (Saturday)",
            "Sat.",
            "9am -\n12:30p\nm",
            "Year-\nRound",
            window([5], "09:00", "12:30"),
        ),
        (
            "Saturdays 8am–12pm, rain or shine",
            "Sat",
            "8am-12pm",
            "Year Round",
            window([5], "08:00", "12:00"),
        ),
        (
            "Year-round Available Products: Fresh fruits",
            "Sat",
            "12pm - 4pm",
            "Year Round",
            window([5], "12:00", "16:00"),
        ),
        (None, "Friday", "9pm - 1am", "Year Round", window([4], "21:00", "01:00", 1)),
        (None, "Mon-Fri", "09:00-13:00", "Year Round", window([0, 1, 2, 3, 4], "09:00", "13:00")),
        ("Saturdays", "Every Saturday", "9am - noon", "Year Round", window([5], "09:00", "12:00")),
    ],
)
def test_literal_normalization_including_pdf_wraps_and_overnight(
    native, official_days, official_hours, months, expected
):
    result = calendars.build(
        facts(native=native, days=official_days, hours=official_hours, months=months)
    )
    assert result["unknown_reasons"] == []
    assert result["weekly_windows"] == [expected]


def test_missing_native_calendar_is_not_a_positive_claim_or_a_conflict():
    source = facts(native=None)
    result = calendars.build(source)
    assert result["weekly_windows"] == [window([5], "09:00", "14:00")]
    assert result["source_receipts"][0]["fields"] == {"season": None}


@pytest.mark.parametrize(
    "fields",
    [
        {"hours": None},
        {"days": None},
        {"months": None},
        {"days": "First and third Saturday"},
        {"months": "May to mid October"},
        {"months": "Year round except Christmas"},
        {"months": "Year round; June to October"},
        {"weather_qualification": "Weather permitting"},
        {"weather_qualification": 123},
        {"start": "2026-05-09", "end": None},
        {"start_date": "9-May", "end_date": "31-Oct"},
    ],
)
def test_incomplete_or_unsupported_official_restrictions_withhold(fields):
    result = calendars.build(facts(**fields))
    assert result["unknown_reasons"]
    assert result["weekly_windows"] == []


def test_explicit_precise_annual_end_preserved_and_dated_year_never_generalized():
    result = calendars.build(facts(native="May to October", months="Apr 1 - Oct 7"))
    assert result["seasons"] == [{"kind": "annual", "start": "05-01", "end": "10-07"}]
    result = calendars.build(
        facts(native="May 9, 2026 through October 31, 2026", months="June to October")
    )
    assert result["seasons"] == [{"kind": "dated", "start": "2026-06-01", "end": "2026-10-31"}]


def test_wrapped_annual_season_remains_alternatives_after_intersection():
    result = calendars.build(facts(native="December 1 through March 31", months="Year Round"))
    assert result["seasons"] == [
        {"kind": "annual", "start": "01-01", "end": "03-31"},
        {"kind": "annual", "start": "12-01", "end": "12-31"},
    ]


def test_dated_ranges_intersect_with_wrapped_annual_constraints():
    result = calendars.build(
        facts(
            native="December 1 through March 31", months=None, start="2026-10-15", end="2027-04-15"
        )
    )
    assert result["seasons"] == [{"kind": "dated", "start": "2026-12-01", "end": "2027-03-31"}]


@pytest.mark.parametrize(
    "native",
    [
        "June 2021 to October 2021",
        "Feb 30 - October 31",
        "May 9, 2026 through October 31",
        "May - June and August - October",
        "Saturday 9am-2pm and Sunday 10am-1pm",
        "Year-round except Christmas",
    ],
)
def test_nonrepresentable_or_invalid_native_calendar_cannot_widen_official(native):
    result = calendars.build(facts(native=native, months="June to October"))
    # An explicit historical dated season is representable, but its intersection
    # with this dated official season is empty rather than repeating annually.
    if native == "June 2021 to October 2021":
        source = facts(native=native, months=None, start="2026-05-09", end="2026-10-31")
        result = calendars.build(source)
    assert result["unknown_reasons"]
    assert result["weekly_windows"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_url", "javascript:alert(1)"),
        ("snapshot_sha256", ""),
        ("checked_at", "2026-10-15T18:00:00"),
        ("checked_at", "not a date"),
    ],
)
def test_official_clock_requires_original_receipt(field, value):
    source = facts()
    source[2][field] = value
    result = calendars.build(source)
    assert result["unknown_reasons"]
    assert result["weekly_windows"] == []


def test_missing_official_clock_and_empty_inputs_fail_closed():
    assert calendars.build([])["unknown_reasons"]
    result = calendars.build(facts()[:2])
    assert "missing_positive_official_weekly_clock" in result["unknown_reasons"]
    assert result["weekly_windows"] == []


def test_receipts_keep_literal_calendar_fields_and_original_row_locators_only():
    source = facts()
    source[2].update(pdf_page=14, table_index=0, row_index=3)
    source[0]["fields"].update(manager="not a calendar field", phone="not a calendar field")
    result = calendars.build(source)
    receipt = result["source_receipts"][2]
    assert (receipt["pdf_page"], receipt["table_index"], receipt["row_index"]) == (14, 0, 3)
    assert [row["snapshot_sha256"] for row in result["source_receipts"]] == [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    assert "not a calendar field" not in json.dumps(result)


def test_separate_official_time_fields_cannot_override_other_source_hours():
    result = calendars.build(
        facts(native="Saturdays 9am - 1pm", hours=None, start_time="8am", end_time="2pm")
    )
    assert result["weekly_windows"] == [window([5], "09:00", "13:00")]
