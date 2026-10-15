"""Source clocks and negative facts remain hard limits, never default availability."""

import hashlib

import pytest

from app.catalog import park_visit_calendar as calendars


def build(monkeypatch, qid, bodies):
    originals = []
    for index, body in enumerate(bodies):
        raw = f'<html><head><meta charset="utf-8"></head><body>{body}</body></html>'.encode()
        originals.append(
            (
                {
                    "url": f"https://example.org/{qid}/{index}",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "retrieved_at": "2026-10-15T17:52:00+00:00",
                    "required_facts": [],
                    "restrictions": ["Retained separately attributed component restriction."],
                },
                raw,
            )
        )
    monkeypatch.setitem(
        calendars._PINS,
        qid,
        [(receipt["url"], receipt["sha256"]) for receipt, _ in originals],
    )
    return calendars.build({"qid": qid}, originals), originals


def dated(day, title, hours, state, featured="yes"):
    return (
        f'<div data-date="{day}" data-hours="{hours}" data-featured="{featured}">'
        f"<h2>{title}</h2><p>{state}</p></div>"
    )


def test_belmont_exact_date_and_component_closure_do_not_become_weekly_hours(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q44041",
        [
            dated("10/15/2026", "Park Hours", "12:00pm - 7:00pm", "Open From 12:00pm To 7:00pm")
            + dated("10/15/2026", "Zipline", "12:00am - 12:00am", "Closed all day", "no")
        ],
    )
    assert result["unknown_reasons"] == []
    assert result["weekly_windows"] == []
    assert result["date_overrides"] == [
        {
            "date": "2026-10-15",
            "windows": [{"opens": "12:00", "closes": "19:00", "end_day_offset": 0}],
        }
    ]
    assert result["source_receipts"][0]["calendar_entries"][1]["title_literal"] == "Zipline"


def test_belmont_park_wide_negative_overrides_positive_and_other_open_component(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q44041",
        [
            dated("12/25/2026", "Park Hours", "11:00am - 8:00pm", "Open From 11:00am To 8:00pm")
            + dated("12/25/2026", "Closed Christmas Day", "12:00am - 12:00am", "Closed all day")
            + dated(
                "12/25/2026", "Lazerblast Arcade", "10:00am - 5:00pm", "Open From 10:00am To 5:00pm"
            )
        ],
    )
    assert result["date_overrides"] == [{"date": "2026-12-25", "windows": []}]


def test_belmont_partial_negative_subtracts_only_verified_positive_windows(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q44041",
        [
            dated("10/15/2026", "Park Hours", "11:00am - 8:00pm", "Open From 11:00am To 8:00pm")
            + dated(
                "10/15/2026",
                "RIDES AND ATTRACTIONS CLOSED",
                "1:00pm - 3:00pm",
                "Closed From 1:00pm To 3:00pm",
            )
            + dated(
                "10/16/2026",
                "RIDES AND ATTRACTIONS CLOSED",
                "1:00am - 12:00pm",
                "Closed From 1:00am To 12:00pm",
            )
        ],
    )
    assert result["date_overrides"] == [
        {
            "date": "2026-10-15",
            "windows": [
                {"opens": "11:00", "closes": "13:00", "end_day_offset": 0},
                {"opens": "15:00", "closes": "20:00", "end_day_offset": 0},
            ],
        }
    ]


@pytest.mark.parametrize("hours", ["12:00am - 12:00am", "8:00pm - 1:00am", "25:00 - 30:00"])
def test_belmont_zero_overnight_or_malformed_positive_clock_is_unknown(monkeypatch, hours):
    result, _ = build(
        monkeypatch, "Q44041", [dated("10/15/2026", "Park Hours", hours, "Open From unknown")]
    )
    assert result["unknown_reasons"]
    assert result["date_overrides"] == []


def test_belmont_conflicting_general_open_hours_are_unknown(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q44041",
        [
            "".join(
                dated("10/15/2026", "Park Hours", f"{start} - 7:00pm", "Open From literal")
                for start in ["11:00am", "12:00pm"]
            )
        ],
    )
    assert result["unknown_reasons"]
    assert result["date_overrides"] == []


def test_changed_operator_original_cannot_keep_old_calendar(monkeypatch):
    _, originals = build(
        monkeypatch, "Q689585", ["WE’RE OPEN DAILY 10AM – 5PM We are also open on ALL holidays."]
    )
    receipt, _ = originals[0]
    result = calendars.build({"qid": "Q689585"}, [(receipt, b"<body>Permanently closed</body>")])
    assert result["weekly_windows"] == []
    assert result["unknown_reasons"]


def test_unreviewed_identity_stays_explicitly_unknown_without_clock_inference():
    result = calendars.build({"qid": "Q999999999999999"}, [])
    assert result["weekly_windows"] == []
    assert result["seasons"] == []
    assert result["unknown_reasons"]
    assert "fixed_starts" not in result
    assert "timezone" not in result


def test_dinosaur_florida_clocks_and_recurring_christmas_closure(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q14685852",
        [
            "FLORIDA 5145 Harvey Tew Road Open Daily: 10:00am to 5:00pm Closed Christmas Day KENTUCKY Open Daily: 8:30am to 5:00pm"
        ],
    )
    assert result["unknown_reasons"] == []
    assert result["weekly_windows"] == [
        {"weekdays": list(range(7)), "opens": "10:00", "closes": "17:00", "end_day_offset": 0}
    ]
    assert result["annual_closures"] == ["12-25"]
    assert result["seasons"] == [{"kind": "annual", "start": "12-26", "end": "12-24"}]


def test_other_dinosaur_location_cannot_supply_florida_hours(monkeypatch):
    result, _ = build(
        monkeypatch, "Q14685852", ["KENTUCKY Open Daily: 8:30am to 5:00pm Closed Christmas Day"]
    )
    assert result["weekly_windows"] == []
    assert result["unknown_reasons"]


def test_oaks_split_sessions_and_unresolved_season_withhold_automatic_scheduling(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q14709151",
        [
            "Roller skating is open year-round.",
            "Fall/Winter Hours: TUE: 3-5 PM WED: 3-5 PM and 7-9:30 PM THU: 3-5 PM and 7-9:30 PM FRI: 1-5 PM and 7-10:30 PM SAT: 1-5 PM and 7-10:30 PM SUN: 1-5 PM and 7-9:30 PM For holiday and school-out hours, view our hours calendar . Every Tuesday 7-9:30 PM Adult Skate",
        ],
    )
    assert len(result["weekly_windows"]) == 11
    assert all(0 not in entry["weekdays"] for entry in result["weekly_windows"])
    assert [e["opens"] for e in result["weekly_windows"] if e["weekdays"] == [1]] == ["15:00"]
    assert [e["opens"] for e in result["weekly_windows"] if e["weekdays"] == [3]] == [
        "15:00",
        "19:00",
    ]
    assert result["seasons"] == []
    assert any("season boundary" in reason for reason in result["unknown_reasons"])
    assert any("holiday" in reason for reason in result["unknown_reasons"])


@pytest.mark.parametrize("qid", ["Q5160318", "Q23994725", "Q6386811"])
def test_daily_access_and_other_component_clocks_never_imply_24_hour_opening(monkeypatch, qid):
    result, _ = build(monkeypatch, qid, ["Open daily. Train 10am-5pm Memorial Day to Labor Day."])
    assert result["weekly_windows"] == []
    assert result["unknown_reasons"]


def test_last_chapel_tour_is_retained_and_prevents_general_close_from_bypassing_cutoff(monkeypatch):
    result, _ = build(
        monkeypatch, "Q26267473", ["Open Daily 9:00am – 5:00pm the last Chapel tour is at 4 PM."]
    )
    assert result["weekly_windows"][0]["closes"] == "17:00"
    assert result["unknown_reasons"]
    assert "the last Chapel tour is at 4 PM." in result["source_receipts"][0]["literal"]


def test_gatorland_year_round_clocks_and_source_receipts(monkeypatch):
    result, originals = build(
        monkeypatch, "Q689585", ["WE’RE OPEN DAILY 10AM – 5PM We are also open on ALL holidays."]
    )
    assert result["unknown_reasons"] == []
    assert result["weekly_windows"][0]["weekdays"] == list(range(7))
    assert result["weekly_windows"][0]["opens"] == "10:00"
    receipt = result["source_receipts"][0]
    assert receipt["snapshot_sha256"] == originals[0][0]["sha256"]
    assert receipt["source_url"] == originals[0][0]["url"]
    assert receipt["checked_at"] == originals[0][0]["retrieved_at"]
    assert receipt["restrictions"] == originals[0][0]["restrictions"]


def test_old_town_published_weekday_groups_are_exact(monkeypatch):
    result, _ = build(
        monkeypatch, "Q7085259", ["SUnday - Thursday: 11AM - 9pm Friday - Saturday: 11am - 11pm"]
    )
    assert result["unknown_reasons"] == []
    assert result["weekly_windows"][0]["weekdays"] == [6, 0, 1, 2, 3]
    assert result["weekly_windows"][1]["weekdays"] == [4, 5]
    assert result["weekly_windows"][1]["closes"] == "23:00"


def test_dezerland_complete_weekly_table_excludes_bar_happy_hour_clocks(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q24192030",
        [
            "Happy Hour Monday – Friday: 4 PM – 9 PM Hours "
            "Monday 11:00 am - 9:00 pm Tuesday 12:00 pm - 9:00 pm "
            "Wednesday 12:00 pm - 9:00 pm Thursday 12:00 pm - 9:00 pm "
            "Friday 12:00 pm - 10:00 pm Saturday 11:00 am - 11:00 pm Sunday 11:00 am - 10:00 pm"
        ],
    )
    assert not result["unknown_reasons"]
    assert len(result["weekly_windows"]) == 7
    assert result["weekly_windows"][0]["opens"] == "11:00"
    assert result["weekly_windows"][3]["opens"] == "12:00"
    assert result["weekly_windows"][5]["closes"] == "23:00"


def test_nascar_generic_footer_cannot_override_unacquired_monthly_calendars(monkeypatch):
    result, _ = build(
        monkeypatch,
        "Q131759816",
        [
            "Monday 11:00 AM – 9:00 PM Tuesday 11:00 AM – 8:00 PM Wednesday 11:00 AM – 8:00 PM "
            "Thursday 11:00 AM – 8:00 PM Friday 11:00 AM – 9:00 PM Saturday 11:00 AM – 10:00 PM "
            "Sunday 11:00 AM – 10:00 PM"
        ],
    )
    assert len(result["weekly_windows"]) == 7
    assert any("monthly calendar images" in reason for reason in result["unknown_reasons"])


def test_missing_weekday_cannot_be_filled_from_neighboring_day(monkeypatch):
    result, _ = build(monkeypatch, "Q24192030", ["Monday 11:00 am - 9:00 pm"])
    assert result["weekly_windows"] == []
    assert result["unknown_reasons"]
