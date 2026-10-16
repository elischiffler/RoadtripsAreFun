"""Authentic literal fixtures plus optional complete frozen-source replay.

Unit snippets contain only the source facts exercised by a transformation. They
are not admitted source snapshots: the independent byte/hash tests cover the
loader, and RECOVERED_CALENDAR_SOURCE_ROOT runs the real pinned originals.
"""

import hashlib
import json
import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.catalog import recovered_visit_calendar as recovery
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


@pytest.fixture(scope="module")
def reviewed_rows():
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/data/catalog-expansion-kaggle-20261015/additions.preview.jsonl"
    )
    return {
        row["source_id"].split(":")[-1]: row
        for row in map(json.loads, path.read_text().splitlines())
    }


def _groups(rows, ident):
    return deepcopy(rows[ident]["provenance"][0]["published_access_facts"])


def _feasible(entry, clock, *, zone="America/Los_Angeles"):
    start = datetime.fromisoformat(clock).replace(tzinfo=ZoneInfo(zone))
    record = {
        "provider_id": entry["source_id"],
        "source_provenance": [{"source_visit_calendar": entry["source_visit_calendar"]}],
    }
    try:
        _, proof = solve_visit(record, start, start + timedelta(hours=2))
        assert proof["dwell_seconds"] == 7200
        assert proof["ticket_availability"] == "unknown"
        return True
    except VisitCalendarConflict:
        return False


@pytest.fixture
def literal_bodies():
    # Verbatim visible fragments from the acquired official sources. No fixture
    # grants permission to bypass the production loader's immutable full hashes.
    fragments = {
        "301226-operator-final": b"<p>South Berkeley Tuesday: 2:00 PM - 6:30 PM</p>",
        "308659-operator": b"<p>Tuesdays: 3-6pm, May - End of October</p><p>10th St between Main and L St</p>",
        "301297-operator": (
            "<p>Friday afternoons</p><p>Summer hours are 2:30 – 5:30 pm (May - September), "
            "but we close at 5:00 pm during the winter (October - April).</p>"
        ).encode(),
        "308993-operator": (
            "<p>2026 Market Season May 20th – Oct 14th Wednesdays 4pm – 7pm</p>"
        ).encode(),
        "Q5160318-attractions-current": b"<p>HOURSWE OPEN 7 days a week, 10am-5pmWORLD-FAMOUS GRAVITY HOUSE IS OPEN!</p><p>Train Ride is closed for the season</p>",
        "confusion-faq": b"<p>The GIFT SHOP and GRAVITY HOUSE are OPEN ALL YEAR!</p>",
        "Q5160318-dated-hours": b"<p>March 22, 2026</p><p>10am till 5pm,7 days a week</p>",
        "Q26267473-visit-current": b"<p>Open 9am-5pm Daily</p><p>Guided or Self Tours, allow 1-3 hours</p><p>Admission tickets available on-site</p><p>the last Chapel tour is at 4 PM.</p>",
        "nascar-footer": ("<p>" + " ".join(text for text, _ in recovery._FOOTER) + "</p>").encode(),
        "nascar-calendar-links": (
            "<div>"
            + "".join(
                f'<img alt="{alt}" src="{recovery._SOURCES[key]["source_url"]}">'
                for key, alt in zip(
                    [f"Q131759816-calendar-{i}" for i in range(1, 4)],
                    ["OCT26", "NOV. 26", "DEC. 26"],
                )
            )
            + "</div>"
        ).encode(),
        "Q14709151-calendar": b'<div><img src="/pub/photo/October-2026-Rink-Hours.png"><img src="/pub/photo/November-2026-Rink-Hours.png"><p>Quantities are limited; purchase your tickets/wristbands online in advance for guaranteed admission.</p></div>',
    }
    return {key: b'<meta charset="utf-8">' + raw for key, raw in fragments.items()}


def test_source_reader_checks_real_bytes_and_rejects_corruption(tmp_path):
    path = tmp_path / "source.html"
    path.write_bytes(b"exact acquired source bytes")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    assert recovery._read(tmp_path, path.name, checksum) == path.read_bytes()
    path.write_bytes(b"exact acquired source bytes altered")
    with pytest.raises(ValueError, match="checksum"):
        recovery._read(tmp_path, path.name, checksum)


@pytest.mark.parametrize("name", ["../outside.html", "file with spaces.html", "/tmp/escape.html"])
def test_source_reader_rejects_unsafe_or_escaping_paths(tmp_path, name):
    with pytest.raises(ValueError):
        recovery._read(tmp_path, name, "0" * 64)


def test_source_reader_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside.html")
    outside.write_bytes(b"outside source")
    (tmp_path / "source.html").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        recovery._read(tmp_path, "source.html", hashlib.sha256(outside.read_bytes()).hexdigest())


def test_source_reader_rejects_empty_or_oversized_files(tmp_path, monkeypatch):
    path = tmp_path / "source.html"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="byte bound"):
        recovery._read(tmp_path, path.name, hashlib.sha256(b"").hexdigest())
    path.write_bytes(b"1234")
    monkeypatch.setattr(recovery, "MAX_SOURCE_BYTES", 3)
    with pytest.raises(ValueError, match="byte bound"):
        recovery._read(tmp_path, path.name, hashlib.sha256(b"1234").hexdigest())


@pytest.mark.parametrize("reviewed_on", [date(2026, 10, 14), date(2026, 11, 16)])
def test_future_or_stale_acquisition_fails_closed(tmp_path, reviewed_on):
    with pytest.raises(ValueError, match="future dated or stale"):
        recovery._load(tmp_path, reviewed_on)


def test_review_date_is_explicit(tmp_path):
    with pytest.raises(ValueError, match="explicit review date"):
        recovery._load(tmp_path, "2026-10-15")


@pytest.mark.parametrize(
    "ident,valid,invalid",
    [
        ("301226", "2026-10-20T14:00", "2026-10-15T14:00"),
        ("308659", "2026-10-20T15:00", "2026-11-03T15:00"),
        ("301297", "2026-10-16T14:30", "2026-10-16T15:30"),
        ("308993", "2026-10-14T16:00", "2026-10-21T16:00"),
    ],
)
def test_authentic_market_literals_fit_full_visit_only(
    reviewed_rows, literal_bodies, ident, valid, invalid
):
    facts = _groups(reviewed_rows, ident)
    before = deepcopy(facts)
    entry = recovery._market(ident, literal_bodies, facts)
    assert facts == before
    assert _feasible(entry, valid)
    assert not _feasible(entry, invalid)
    assert entry["transformation"]["original_catalog_row_and_provenance_modified"] is False
    assert entry["source_constraints"][0]["literal_facts"] == before[0]["fields"]
    assert entry["source_constraints"][1]["literal_facts"] == before[1]["fields"]


def test_weaverville_retains_all_conflicting_season_evidence(reviewed_rows, literal_bodies):
    entry = recovery._market("308993", literal_bodies, _groups(reviewed_rows, "308993"))
    assert entry["source_visit_calendar"]["seasons"] == [
        {"kind": "dated", "start": "2026-05-20", "end": "2026-10-14"}
    ]
    constraints = entry["source_constraints"]
    assert constraints[0]["literal_facts"]["season"] == "May–October, Wednesdays 4pm–7pm"
    assert constraints[1]["literal_facts"]["season"] == "May–October, Wednesdays 4pm–7pm"
    assert constraints[2]["literal_facts"]["months"] == "May 20 -\nOct 21"
    assert "Oct 14th" in constraints[-1]["literal_facts"]["literal"]
    assert not _feasible(entry, "2027-05-26T16:00")


def test_cambria_afternoon_context_is_required_not_inferred(reviewed_rows, literal_bodies):
    literal_bodies["301297-operator"] = literal_bodies["301297-operator"].replace(
        b"Friday afternoons", b"Friday"
    )
    with pytest.raises(ValueError, match="literal missing"):
        recovery._market("301297", literal_bodies, _groups(reviewed_rows, "301297"))


def test_unrecognized_market_restriction_is_not_silently_ignored(reviewed_rows, literal_bodies):
    facts = _groups(reviewed_rows, "308659")
    facts[0]["fields"]["season"] = "Tuesdays 3:00–6:00pm except during winter"
    with pytest.raises(ValueError, match="Unsupported Fortuna"):
        recovery._market("308659", literal_bodies, facts)


def test_precious_general_self_guided_access_has_full_dwell_cutoff(reviewed_rows, literal_bodies):
    entry = recovery._precious(literal_bodies, reviewed_rows)
    assert _feasible(entry, "2026-10-16T15:00", zone="America/Chicago")
    assert not _feasible(entry, "2026-10-16T15:01", zone="America/Chicago")
    assert "self-guided" in entry["transformation"]["scope"]
    assert "4 PM" in entry["source_constraints"][-1]["literal_facts"]["last_chapel_tour"]


def test_confusion_gravity_house_is_separate_from_closed_train(reviewed_rows, literal_bodies):
    entry = recovery._confusion(literal_bodies, reviewed_rows)
    assert _feasible(entry, "2026-10-16T15:00")
    assert not _feasible(entry, "2026-10-16T15:01")
    assert "Mountain Train excluded" in entry["transformation"]["scope"]
    assert any(
        "closed for the season" in str(c["literal_facts"]) for c in entry["source_constraints"]
    )


def test_nascar_dated_closures_and_footer_intersection(reviewed_rows, literal_bodies):
    entry = recovery._nascar(literal_bodies, reviewed_rows)
    assert len(entry["source_visit_calendar"]["date_overrides"]) == 92
    assert not _feasible(entry, "2026-10-28T11:00", zone="America/New_York")
    assert not _feasible(entry, "2026-11-26T11:00", zone="America/New_York")
    # Image October9 closes22:00, footer Friday21:00; retain both and intersect.
    assert _feasible(entry, "2026-10-09T19:00", zone="America/New_York")
    assert not _feasible(entry, "2026-10-09T19:01", zone="America/New_York")
    assert not _feasible(entry, "2027-01-01T11:00", zone="America/New_York")
    cells = entry["source_constraints"][-4]["literal_facts"]["dated_grid_cells"]
    assert next(c for c in cells if c["date"] == "2026-10-09")["literal"] == "11AM-10PM"


def test_nascar_missing_image_year_binding_fails(reviewed_rows, literal_bodies):
    literal_bodies["nascar-calendar-links"] = literal_bodies["nascar-calendar-links"].replace(
        b"OCT26", b"OCT"
    )
    with pytest.raises(ValueError, match="link/year"):
        recovery._nascar(literal_bodies, reviewed_rows)


def test_oaks_holiday_replaces_regular_afternoon_and_scopes_dates(reviewed_rows, literal_bodies):
    entry = recovery._oaks(literal_bodies, reviewed_rows)
    assert len(entry["source_visit_calendar"]["date_overrides"]) == 53
    assert _feasible(entry, "2026-11-11T13:00")
    assert not _feasible(entry, "2026-11-26T15:00")
    assert _feasible(entry, "2026-11-26T19:00")
    assert not _feasible(entry, "2026-12-01T15:00")
    assert not _feasible(entry, "2026-10-24T23:00")  # adult specialty is not Open Skate


def _fun_event(day="2026-10-17", *, title="October 17, 2026 (Kissimmee Only)"):
    return {
        "id": 28388,
        "title": title,
        "start": day + "T10:00:00+00:00",
        "end": day + "T00:00:00+00:00",
        "post_content": "<p>Midnight</p>\n",
    }


def test_funspot_source_midnight_is_wall_clock_and_next_day():
    overrides, facts, held = recovery._funspot_dates([_fun_event()])
    assert not held
    assert facts[0]["start"] == "2026-10-17T10:00:00+00:00"
    assert overrides == [
        {
            "date": "2026-10-17",
            "windows": [{"opens": "10:00", "closes": "00:00", "end_day_offset": 1}],
        }
    ]


def test_funspot_year_conflict_is_individual_unknown_not_guessed_closed():
    event = _fun_event("2026-10-21", title="October 21, 2027")
    overrides, facts, held = recovery._funspot_dates([event, _fun_event()])
    assert len(overrides) == len(facts) == 1
    assert held[0]["date"] == "2026-10-21"
    assert held[0]["event"]["title"] == "October 21, 2027"


def test_funspot_explicit_closure_does_not_become_overnight_open():
    event = {
        "id": 28136,
        "title": "December 10, 2026",
        "start": "2026-12-10T00:00:00+00:00",
        "end": "2026-12-10T00:00:00+00:00",
        "post_content": "<p><strong>CLOSED &#8211; ALL DAY</strong></p>\n",
    }
    overrides, _, held = recovery._funspot_dates([event])
    assert overrides == [{"date": "2026-12-10", "windows": []}]
    assert not held


def test_funspot_unsupported_time_is_not_filled_from_footer():
    event = _fun_event()
    event["post_content"] = "<p>hours vary</p>"
    with pytest.raises(ValueError, match="clock content"):
        recovery._funspot_dates([event])


def test_funspot_duplicate_date_fails_closed():
    with pytest.raises(ValueError, match="duplicate"):
        recovery._funspot_dates([_fun_event(), _fun_event()])


def test_full_pinned_offline_replay_and_actual_source_window_guards(tmp_path):
    source_root = os.environ.get("RECOVERED_CALENDAR_SOURCE_ROOT")
    if not source_root:
        pytest.skip("Set RECOVERED_CALENDAR_SOURCE_ROOT to the private frozen source bundle")
    first = recovery.build_enrichments(source_root, reviewed_on=date(2026, 10, 15))
    assert first == recovery.build_enrichments(source_root, reviewed_on=date(2026, 10, 15))
    assert first["summary"]["companion_entries"] == 10
    assert first["summary"]["positive_calendar_recoveries"] == 9
    assert first["summary"]["record_holds"] == 1
    assert first["holds"][0]["source_id"] == "usda-market:308735"
    # Corrupt the first authentic body and verify the full batch cannot emit
    # partial entries, even though the caller still supplies the genuine pins.
    first_receipt = next(iter(recovery._SOURCES.values()))
    corrupt = tmp_path / first_receipt["body_path"]
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes((Path(source_root) / first_receipt["body_path"]).read_bytes() + b"altered")
    with pytest.raises(ValueError, match="checksum"):
        recovery.build_enrichments(tmp_path, reviewed_on=date(2026, 10, 15))
    byid = {e["source_id"].split(":")[-1]: e for e in first["entries"]}
    assert not _feasible(byid["308993"], "2026-10-21T16:00")
    assert _feasible(byid["Q23994725"], "2026-10-17T22:00", zone="America/New_York")
    assert not _feasible(byid["Q23994725"], "2026-10-17T22:01", zone="America/New_York")
    assert not _feasible(byid["Q23994725"], "2026-10-21T14:00", zone="America/New_York")
    assert not _feasible(byid["Q23994725"], "2026-12-10T14:00", zone="America/New_York")
    assert _feasible(byid["Q6386811"], "2026-10-15T12:00", zone="America/Chicago")
    assert not _feasible(byid["Q6386811"], "2026-11-15T12:00", zone="America/Chicago")


@pytest.fixture
def kemah_literal_bodies():
    # Literal structured clocks from the official page-selected public embed,
    # represented as a small parser fixture; production still requires full pins.
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ends = ["21:00", "20:00", "20:00", "20:00", "22:00", "23:00", "21:00"]
    attributes = {"holidayHoursFormatted": None}
    schema = []
    for name, end in zip(days, ends):
        attributes[f"hours.{name.lower()}.openIntervals"] = [{"start": "12:00", "end": end}]
        attributes["hours-" + name.lower()] = f"12:00 pm - {int(end[:2]) - 12}:00 pm"
        schema.append({"dayOfWeek": name, "opens": "12:00", "closes": end})
    payload = {
        "entityIdToUid": {"KBWK": "2B5Nx"},
        "entities": [
            {
                "entityId": "KBWK",
                "attributes": attributes,
                "schema": {"openingHoursSpecification": schema},
            }
        ],
    }
    url = recovery._SOURCES["Q6386811-public-hours-embed-valid"]["source_url"]
    bodies = {
        "Q6386811-visitor-current": (
            '<meta charset="utf-8"><p>Hours shown are current month. Hours are seasonal.</p>'
            f'<script src="{url}"></script>'
        ).encode(),
        "Q6386811-public-hours-embed-valid": ("callback(" + json.dumps(payload) + ")").encode(),
    }
    return bodies, payload


def test_kemah_structured_clocks_are_bounded_to_acquisition_month(
    reviewed_rows, kemah_literal_bodies
):
    bodies, _ = kemah_literal_bodies
    entry = recovery._kemah(bodies, reviewed_rows)
    assert entry["source_visit_calendar"]["seasons"] == [
        {"kind": "dated", "start": "2026-10-01", "end": "2026-10-31"}
    ]
    assert _feasible(entry, "2026-10-20T18:00", zone="America/Chicago")
    assert not _feasible(entry, "2026-10-20T18:01", zone="America/Chicago")
    assert not _feasible(entry, "2026-11-15T12:00", zone="America/Chicago")
    assert not entry["source_visit_calendar"]["fixed_starts"]


def test_kemah_conflicting_structured_schema_fails_closed(reviewed_rows, kemah_literal_bodies):
    bodies, payload = kemah_literal_bodies
    payload["entities"][0]["schema"]["openingHoursSpecification"][0]["closes"] = "23:00"
    bodies["Q6386811-public-hours-embed-valid"] = ("callback(" + json.dumps(payload) + ")").encode()
    with pytest.raises(ValueError, match="conflicts"):
        recovery._kemah(bodies, reviewed_rows)
