"""Authentic visitor-clock excerpts plus bounded synthetic archive/road fixtures.

The test receipts deliberately are not the production evidence bundle. Real
source archives, operator pages and road receipts are pinned by the adapter's
review fingerprint and replayed separately before admission.
"""

import copy
import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.catalog import kaggle_cultural as cultural
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit

WATTS_HOURS = "Wednesday- Saturday, 10:00AM - 4:00PM; Sunday, 12:00PM - 4:00PM"
WATTS_PAGE = b"""<body><section><h3>Hours</h3>
<p>Galleries: Wednesday to Saturday from 10:00 a.m. to 4:00 p.m.</p>
<p>Watts Towers Guided Tours: Thursday to Saturday from 11:00 a.m. to 3:00 p.m.</p>
</section><p>Beginning July 8, 2026, the campus has reopened to the public
following a temporary closure during the month of June.</p>
<p>Campus renovations will continue through Spring 2028.</p>
<p>Watts Towers Arts Center Campus Parking, 10624 Graham Avenue, Los Angeles, CA 90002</p>
<p>1727 East 107th Street, Los Angeles, CA 90002</p></body>"""
PHILIPSE_OFFICIAL = """<html><head><meta charset="utf-8"></head><body>Wednesday – 10 am to 5 pm.
The site may be closed for holidays or open additional hours for special programs.
<a href="https://www.google.com/maps?q=40.93602053,-73.8990062">Main Entrance</a>
</body></html>""".encode()
PHILIPSE_VISIT = b"""<body>Philipse Manor Hall State Historic Site is self-guided.
Wednesday: 10 am-5 pm Saturday: 10 am-5 pm
The main entrance for pedestrians and to the small parking lot is on Warburton Ave.
Parking: Limited parking available in the small Philipse Manor Hall lot, entrance located on Warburton Ave.
29 Warburton Avenue, Yonkers, NY 10701. Guided tour reservations are recommended.
</body>"""
PHILIPSE_EVENT = b"""<body>Family Halloween Day
Saturday, October 31, 2026 12:00 PM - 4:00 PM Spooky Crafts
</body>"""


@pytest.fixture
def sample(tmp_path, monkeypatch):
    instant = datetime(2026, 10, 15, 23, tzinfo=UTC)
    monkeypatch.setattr(cultural, "now", lambda: instant)

    def save(name, body, url="https://example.org/source"):
        (tmp_path / name).write_bytes(body)
        return {
            "path": name,
            "url": url,
            "sha256": cultural.digest(body),
            "retrieved_at": instant.isoformat(),
        }

    originals = {
        "la": {
            **dict.fromkeys(cultural.SOURCES["la"]["columns"], ""),
            "CENTER NAME": "Watts Towers Campus - Watts Towers Arts Center",
            "HOURS": WATTS_HOURS,
            "PARKING": "Off-street parking, lot available",
            "ADDRESS": "{'longitude': '-118.241932', 'latitude': '33.938627'}",
        },
        "ny": {
            **dict.fromkeys(cultural.SOURCES["ny"]["columns"], ""),
            "Name": "Philipse Manor Hall",
            "Latitude": "40.93555005",
            "Longitude": "-73.89931286",
            "Facility URL": "{'url': 'https://parks.ny.gov/historic-sites/37/details.aspx'}",
        },
    }
    sources, specs, profiles = {}, copy.deepcopy(cultural.SOURCES), []
    for dataset, original in originals.items():
        spec = specs[dataset]
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=spec["columns"])
        writer.writeheader()
        writer.writerow(original)
        csv_raw = text.getvalue().encode()
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr(spec["csv"], csv_raw)
        spec.update(
            count=1,
            archive_sha256=cultural.digest(zipped.getvalue()),
            csv_sha256=cultural.digest(csv_raw),
        )
        metadata = {
            "ref": spec["ref"],
            "currentVersionNumber": spec["version"],
            "licenseName": "CC0: Public Domain",
        }
        registry_meta = {"id": spec["upstream_id"], "provenance": "official", "licenseId": "CC0_10"}
        lat, lon = cultural.source_point(dataset, original)
        registry = (
            [
                {
                    "center_name": original["CENTER NAME"],
                    "address": {"latitude": str(lat), "longitude": str(lon)},
                    "hours": original["HOURS"],
                    "parking": original["PARKING"],
                }
            ]
            if dataset == "la"
            else [
                {
                    "name": original["Name"],
                    "x": str(lon),
                    "y": str(lat),
                    "facility_url": {"url": "https://parks.ny.gov/historic-sites/37/details.aspx"},
                }
            ]
        )
        sources[dataset] = {
            "archive": save(dataset + ".zip", zipped.getvalue()),
            "metadata": save(dataset + "-metadata.json", json.dumps(metadata).encode()),
            "registry_metadata": save(
                dataset + "-registry-metadata.json", json.dumps(registry_meta).encode()
            ),
            "registry": save(dataset + "-registry.json", json.dumps(registry).encode()),
            "rights": {
                right: save(dataset + "-rights-" + str(n) + ".txt", right.encode())
                for n, right in enumerate(sorted(spec["rights"]))
            },
        }
        if dataset == "la":
            bodies, kind = [WATTS_PAGE], "watts-campus-galleries"
            address = "1727 East 107th Street, Los Angeles, CA 90002"
            parking = [
                "Watts Towers Arts Center Campus Parking, 10624 Graham Avenue, Los Angeles, CA 90002",
                "1727 East 107th Street",
            ]
            method, road, road_name = "operator-street-frontage", 166068758, "East 107th Street"
            snap, metres = [-118.241932, 33.938638], 1.220131353
        else:
            bodies, kind = (
                [PHILIPSE_OFFICIAL, PHILIPSE_VISIT, PHILIPSE_EVENT],
                "philipse-affirmative-halloween-visit",
            )
            address = "29 Warburton Avenue, Yonkers, NY 10701"
            parking = [
                "The main entrance for pedestrians and to the small parking lot is on Warburton Ave.",
                "Parking: Limited parking available in the small Philipse Manor Hall lot, entrance located on Warburton Ave.",
            ]
            method, road, road_name = "operator-entry-frontage", 23525737, "Dock Street"
            snap, metres = [-73.899346, 40.935421], 14.59293711
        pages = []
        for n, body in enumerate(bodies):
            evidence = save(f"{dataset}-operator-{n}.html", body)
            evidence.update(
                required_facts=[cultural.plain(body)],
                restrictions=["Retain selected visitor component; other access is unknown."],
                extraction_pointer="visible visitor text",
            )
            pages.append(evidence)
        route = {
            "code": "Ok",
            "routes": [{"distance": 100, "duration": 60}],
            "waypoints": [
                {"location": [lon + 0.002, lat + 0.002], "distance": 0},
                {"location": snap, "distance": metres, "name": road_name},
            ],
        }
        osm = f'<osm version="0.6"><node id="1" lat="{snap[1]}" lon="{snap[0] - 0.001}"/><node id="2" lat="{snap[1]}" lon="{snap[0] + 0.001}"/><way id="{road}"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="name" v="{road_name}"/></way></osm>'.encode()
        profiles.append(
            {
                "dataset": dataset,
                "name": original[spec["name"]],
                "source_row": original,
                "calendar_kind": kind,
                "component": "Published public gallery"
                if dataset == "la"
                else "Affirmatively dated self-guided public museum event",
                "address": address,
                "address_parts": [address],
                "public_url": pages[0]["url"],
                "pages": pages,
                "driving": save(
                    dataset + "-route.json",
                    json.dumps(route).encode(),
                    f"https://router.project-osrm.org/route/v1/driving/{lon + 0.002},{lat + 0.002};{lon},{lat}?overview=false&steps=false",
                ),
                "osm": save(dataset + "-osm.xml", osm),
                "arrival": {
                    "method": method,
                    "road_way_id": road,
                    "operator_parking_facts": parking,
                },
                "transformation": "Intersect source windows for this selected component only.",
            }
        )
    monkeypatch.setattr(cultural, "SOURCES", specs)
    baseline = [{"source_id": "preserved:1", "latitude": 51.0, "longitude": 0.0}]
    baseline_raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in baseline).encode()
    monkeypatch.setattr(cultural, "BASELINE_COUNT", 1)
    monkeypatch.setattr(cultural, "BASELINE_ROWS_SHA256", cultural.canonical_rows_digest(baseline))
    review = {
        "schema_version": cultural.SCHEMA,
        "baseline": save("baseline.jsonl", baseline_raw),
        "sources": sources,
        "admissions": profiles,
        "dispositions": [
            {
                "dataset": p["dataset"],
                "name": p["name"],
                "status": "admit",
                "reason": "Concrete fixture visitor calendar/arrival",
            }
            for p in profiles
        ],
    }

    def pin():
        raw = json.dumps(review).encode()
        path = tmp_path / "review.json"
        path.write_bytes(raw)
        monkeypatch.setattr(cultural, "REVIEW_SHA256", cultural.digest(raw))
        return path

    def replace(evidence, raw):
        (tmp_path / evidence["path"]).write_bytes(raw)
        evidence["sha256"] = cultural.digest(raw)

    return {
        "root": tmp_path,
        "review": review,
        "profiles": profiles,
        "pin": pin,
        "replace": replace,
        "save": save,
        "instant": instant,
    }


def pages(sample, profile):
    return [(e, (sample["root"] / e["path"]).read_bytes()) for e in profile["pages"]]


def calendar(sample, index):
    p = sample["profiles"][index]
    return cultural.calendar_for(p, p["source_row"], pages(sample, p))


def record(calendar):
    return {
        "provider_id": "fixture-cultural",
        "categories": ["culture"],
        "source_provenance": [{"source_visit_calendar": calendar}],
    }


def at(day, clock, zone="America/Los_Angeles"):
    return datetime.fromisoformat(day + "T" + clock).replace(tzinfo=ZoneInfo(zone))


def test_offline_replay_preserves_coordinates_baseline_and_separate_calendars(sample):
    path = sample["pin"]()
    before = (sample["root"] / "baseline.jsonl").read_bytes()
    rows, report = cultural.prepare(
        path, {"schema_version": cultural.SCHEMA, "sha256": cultural.REVIEW_SHA256}
    )
    assert report["scanned"] == report["accepted"] == 2
    assert report["held"] == 0
    assert report["bytes"] == sum(f["bytes"] for f in report["input_files"])
    assert report["new_evidence_bytes"] == report["bytes"] - len(before)
    assert [(r["latitude"], r["longitude"]) for r in rows] == [
        (33.938627, -118.241932),
        (40.93555005, -73.89931286),
    ]
    assert rows[1]["source_id"] == "nys-historic:37"
    assert rows[0]["provenance"][0]["source_id_method"].startswith("SHA256 of exact native")
    assert all("source_visit_calendar" not in r for r in rows)
    assert len(report["calendar_entries"]) == 2
    assert all(e["source_constraints"] for e in report["calendar_entries"])
    assert {e["id"] for e in report["public_osm_subset"]["elements"]} == {166068758, 23525737}
    assert (sample["root"] / "baseline.jsonl").read_bytes() == before
    assert cultural.prepare(path)[0] == rows


def test_watts_intersects_old_sunday_and_current_gallery_clocks_without_using_tours(sample):
    value = calendar(sample, 0)
    assert value["weekly_windows"] == [
        {"weekdays": [2, 3, 4, 5], "opens": "10:00", "closes": "16:00", "end_day_offset": 0}
    ]
    start, _ = solve_visit(record(value), at("2026-10-21", "09:00"), at("2026-10-21", "18:00"))
    assert start == at("2026-10-21", "10:00")  # Wednesday has galleries but no tower tour.
    with pytest.raises(VisitCalendarConflict):
        solve_visit(record(value), at("2026-10-18", "12:00"), at("2026-10-18", "18:00"))


@pytest.mark.parametrize("day", ["2026-06-03", "2026-07-01", "2026-07-07"])
def test_watts_temporary_closure_is_hard_not_a_penalty(sample, day):
    with pytest.raises(VisitCalendarConflict):
        solve_visit(record(calendar(sample, 0)), at(day, "10:00"), at(day, "18:00"))


def test_watts_positive_reopening_and_full_two_hours_are_required(sample):
    value = calendar(sample, 0)
    assert solve_visit(record(value), at("2026-07-08", "14:00"), at("2026-07-08", "18:00"))[
        0
    ] == at("2026-07-08", "14:00")
    with pytest.raises(VisitCalendarConflict):
        solve_visit(record(value), at("2026-07-08", "14:01"), at("2026-07-08", "18:00"))
    p = sample["profiles"][0]
    changed = pages(sample, p)
    changed[0] = (changed[0][0], changed[0][1].replace(b"has reopened", b"has not reopened"))
    with pytest.raises(ValueError, match="reopening"):
        cultural.calendar_for(p, p["source_row"], changed)


def test_philipse_only_affirmative_event_day_admits_two_hour_self_guided_visit(sample):
    value = calendar(sample, 1)
    assert value["weekly_windows"] == value["fixed_starts"] == []
    assert value["seasons"] == [{"kind": "dated", "start": "2026-10-31", "end": "2026-10-31"}]
    zone = "America/New_York"
    assert solve_visit(
        record(value), at("2026-10-31", "09:00", zone), at("2026-10-31", "18:00", zone)
    )[0] == at("2026-10-31", "12:00", zone)
    assert solve_visit(
        record(value), at("2026-10-31", "14:00", zone), at("2026-10-31", "18:00", zone)
    )[0] == at("2026-10-31", "14:00", zone)
    for day, clock in [("2026-10-31", "14:01"), ("2026-10-30", "12:00"), ("2026-11-01", "12:00")]:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(record(value), at(day, clock, zone), at(day, "18:00", zone))


@pytest.mark.parametrize(
    "index,old,new",
    [
        (0, "Wednesday – 10 am to 5 pm", "Wednesday – Closed"),
        (1, "is self-guided", "is guided"),
        (2, "October 31, 2026", "October 31, 2025"),
        (2, "12:00 PM - 4:00 PM", "12:00 PM - 1:00 PM"),
    ],
)
def test_philipse_changed_component_or_clocks_fail_closed(sample, index, old, new):
    p = sample["profiles"][1]
    changed = pages(sample, p)
    e, body = changed[index]
    changed[index] = (e, body.replace(old.encode(), new.encode()))
    with pytest.raises(ValueError, match="source-bound"):
        cultural.calendar_for(p, p["source_row"], changed)


def test_unreviewed_calendar_and_native_clock_fail_closed(sample):
    p = copy.deepcopy(sample["profiles"][0])
    p["source_row"]["HOURS"] = "Daily 24 hours"
    with pytest.raises(ValueError, match="native Watts"):
        cultural.calendar_for(p, p["source_row"], pages(sample, p))
    p["calendar_kind"] = "guided-tour-with-assumed-two-hour-grounds"
    with pytest.raises(ValueError, match="unsupported"):
        cultural.calendar_for(p, p["source_row"], pages(sample, p))


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("baseline", "exact full preserved"),
        ("campus", "overlaps preserved"),
        ("registry-coordinate", "unchanged native"),
        ("registry-hours", "clock conflict"),
        ("registry-parking", "parking conflict"),
        ("registry-url", "facility URL identity"),
        ("rights", "rights evidence missing"),
        ("publisher", "publisher/version"),
        ("ledger", "every source row"),
        ("unknown-status", "held row"),
        ("native-row", "native source facts"),
        ("calendar-body", "restriction absent"),
    ],
)
def test_replay_refuses_incomplete_or_changed_evidence(sample, monkeypatch, mutation, match):
    review = sample["review"]
    if mutation in {"baseline", "campus"}:
        baseline = [{"source_id": "other", "latitude": 33.9387, "longitude": -118.2419}]
        raw = "".join(json.dumps(r, sort_keys=True) + "\n" for r in baseline).encode()
        sample["replace"](review["baseline"], raw)
        if mutation == "campus":
            monkeypatch.setattr(
                cultural, "BASELINE_ROWS_SHA256", cultural.canonical_rows_digest(baseline)
            )
    elif mutation in {"registry-coordinate", "registry-hours", "registry-parking", "registry-url"}:
        if mutation == "registry-url":
            e = review["sources"]["ny"]["registry"]
            rows = json.loads((sample["root"] / e["path"]).read_bytes())
            rows[0]["facility_url"] = {"url": "https://parks.ny.gov/historic-sites/99/details.aspx"}
            sample["replace"](e, json.dumps(rows).encode())
        else:
            e = review["sources"]["la"]["registry"]
            rows = json.loads((sample["root"] / e["path"]).read_bytes())
            if mutation == "registry-coordinate":
                rows[0]["address"]["latitude"] = "33.9"
            elif mutation == "registry-parking":
                rows[0]["parking"] = "No visitor parking"
            else:
                rows[0]["hours"] = "Sunday 12-16"
            sample["replace"](e, json.dumps(rows).encode())
    elif mutation == "rights":
        review["sources"]["ny"]["rights"].pop("LicenseRef-Open-NY-Factual-Data")
    elif mutation == "publisher":
        e = review["sources"]["ny"]["metadata"]
        body = json.loads((sample["root"] / e["path"]).read_bytes())
        body["currentVersionNumber"] = 999
        sample["replace"](e, json.dumps(body).encode())
    elif mutation == "ledger":
        review["dispositions"].pop()
    elif mutation == "unknown-status":
        review["dispositions"][0]["status"] = "maybe"
    elif mutation == "native-row":
        review["admissions"][0]["source_row"] = {
            **review["admissions"][0]["source_row"],
            "HOURS": "Daily",
        }
    else:
        e = review["admissions"][0]["pages"][0]
        sample["replace"](e, b"<body>Closed for renovations.</body>")
    with pytest.raises(ValueError, match=match):
        cultural.prepare(sample["pin"]())


def test_source_archive_has_exact_hash_schema_and_decoded_bounds(sample):
    spec = cultural.SOURCES["la"]
    archive = (sample["root"] / "la.zip").read_bytes()
    assert len(cultural._archive(archive, spec)) == 1
    with pytest.raises(ValueError, match="unreviewed"):
        cultural._archive(archive + b"unreviewed", spec)
    with pytest.raises(ValueError, match="schema"):
        cultural._archive(archive, {**spec, "columns": ["wrong"]})
    with pytest.raises(ValueError, match="row count"):
        cultural._archive(archive, {**spec, "count": 2})
    value = io.BytesIO()
    with zipfile.ZipFile(value, "w") as z:
        z.writestr("../escape.csv", b"bad")
        z.writestr(spec["csv"], b"bad")
    raw = value.getvalue()
    with pytest.raises(ValueError, match="archive inventory"):
        cultural._archive(raw, {**spec, "archive_sha256": cultural.digest(raw)})


def test_held_distance_has_retained_measured_proof_and_counts_input_bytes(sample):
    p = sample["review"]["admissions"].pop()
    d = sample["review"]["dispositions"][-1]
    d.update(
        status="hold",
        reason="Actual unchanged-native driving destination is over 75m.",
        driving_evidence=p["driving"],
    )
    with pytest.raises(ValueError, match="held over-distance"):
        cultural.prepare(sample["pin"]())
    e = p["driving"]
    route = json.loads((sample["root"] / e["path"]).read_bytes())
    route["waypoints"][-1].update(location=[-73.89931286, 40.93655005], distance=111.2)
    sample["replace"](e, json.dumps(route).encode())
    rows, report = cultural.prepare(sample["pin"]())
    assert len(rows) == report["accepted"] == report["held"] == 1
    assert report["scanned"] == 2
    assert any(i["path"] == e["path"] for i in report["input_files"])


@pytest.mark.parametrize(
    "value",
    [
        "../outside",
        "/absolute",
        "a\\b",
        "evidence:x",
        "a?.txt",
        "a|b",
        "",
        "CON",
        "aux.txt",
        "space ",
        "dot.",
        "control\x01.txt",
    ],
)
def test_reader_rejects_nonportable_or_escaped_paths(sample, value):
    with pytest.raises(ValueError, match="portable"):
        cultural.Reader(sample["root"], 100).read({"path": value})


@pytest.mark.parametrize(
    "offset,naive",
    [(timedelta(days=-31), False), (timedelta(seconds=1), False), (timedelta(), True)],
)
def test_reader_requires_actual_fresh_aware_receipts(sample, offset, naive):
    e = sample["save"]("fresh.txt", b"source body")
    checked = sample["instant"] + offset
    e["retrieved_at"] = checked.replace(tzinfo=None).isoformat() if naive else checked.isoformat()
    with pytest.raises(ValueError, match="aware genuine acquisition"):
        cultural.Reader(sample["root"], 1000).read(e)


def test_reader_checks_hash_aggregate_unique_bytes_and_symlink_escape(sample, tmp_path):
    e = sample["save"]("body.txt", b"real evidence")
    reader = cultural.Reader(sample["root"], 100)
    reader.read(e)
    reader.read(e)
    assert reader.bytes == len(b"real evidence")
    with pytest.raises(ValueError, match="aggregate"):
        cultural.Reader(sample["root"], 1).read(e)
    with pytest.raises(ValueError, match="checksum"):
        reader.read({**e, "sha256": "0" * 64})
    outside = tmp_path.parent / (tmp_path.name + "-outside.txt")
    outside.write_bytes(b"outside")
    (tmp_path / "escaped").symlink_to(outside)
    with pytest.raises(ValueError, match="escaped"):
        reader.read({**e, "path": "escaped"})


def arrive(sample, profile=None, route=None, osm=None):
    p = profile or sample["profiles"][0]
    return cultural.arrival_for(
        p,
        p["source_row"],
        pages(sample, p),
        route or (sample["root"] / p["driving"]["path"]).read_bytes(),
        osm or (sample["root"] / p["osm"]["path"]).read_bytes(),
    )


def test_actual_public_street_and_operator_entry_are_distinct_proofs(sample):
    for p, metres in zip(sample["profiles"], [1.220131353, 14.59293711], strict=True):
        arrival, road = arrive(sample, p)
        assert arrival["snap_distance_m"] == metres
        assert arrival["coordinate_replaced"] is False
        assert arrival["parking_availability"] == "unknown"
        assert road["id"] == p["arrival"]["road_way_id"]


@pytest.mark.parametrize(
    "tag",
    ['<tag k="access" v="private"/>', '<tag k="motor_vehicle" v="no"/>', '<tag k="layer" v="-1"/>'],
)
def test_private_or_tunnel_road_never_establishes_visitor_access(sample, tag):
    p = sample["profiles"][0]
    osm = (
        (sample["root"] / p["osm"]["path"])
        .read_bytes()
        .replace(b"</way>", tag.encode() + b"</way>")
    )
    with pytest.raises(ValueError, match="public visitor vehicle access"):
        arrive(sample, osm=osm)


def test_footway_wrong_geometry_and_unnamed_service_fail(sample):
    p = sample["profiles"][0]
    original = (sample["root"] / p["osm"]["path"]).read_bytes()
    for body, match in [
        (original.replace(b'v="residential"', b'v="footway"'), "public visitor"),
        (original.replace(b"33.938638", b"33.94"), "actual snapped"),
        (original.replace(b'v="residential"', b'v="service"'), "unnamed/internal"),
    ]:
        with pytest.raises(ValueError, match=match):
            arrive(sample, osm=body)


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("large", "75 metres"),
        ("inconsistent", "disagrees"),
        ("boolean", "malformed"),
        ("nan", "malformed"),
        ("failed", "failed"),
    ],
)
def test_driving_snap_is_measured_and_bound_to_unchanged_native_coordinate(sample, mutation, match):
    p = sample["profiles"][0]
    route = json.loads((sample["root"] / p["driving"]["path"]).read_bytes())
    if mutation == "large":
        route["waypoints"][-1].update(location=[-118.241932, 33.939627], distance=111.2)
    elif mutation == "inconsistent":
        route["waypoints"][-1]["location"] = [-118.0, 33.0]
    elif mutation == "failed":
        route["code"] = "NoRoute"
    else:
        route["waypoints"][-1]["distance"] = True if mutation == "boolean" else float("nan")
    with pytest.raises(ValueError, match=match):
        arrive(sample, route=json.dumps(route).encode())


def test_operator_parking_entry_and_exact_route_endpoint_are_required(sample):
    p = copy.deepcopy(sample["profiles"][0])
    p["arrival"]["operator_parking_facts"] = []
    with pytest.raises(ValueError, match="parking/directions"):
        arrive(sample, p)
    p = copy.deepcopy(sample["profiles"][1])
    e = p["pages"][0]
    sample["replace"](e, PHILIPSE_OFFICIAL.replace(b"40.93602053,-73.8990062", b"41.0,-74.0"))
    with pytest.raises(ValueError, match="main entry differs"):
        arrive(sample, p)
    p = copy.deepcopy(sample["profiles"][0])
    p["driving"]["url"] = p["driving"]["url"].replace(";", ";0,")
    with pytest.raises(ValueError, match="exact unchanged"):
        arrive(sample, p)


def test_import_ceilings_manifest_and_review_fingerprint_cannot_be_bypassed(sample):
    path = sample["pin"]()
    for kwargs in [{"max_rows": 50001}, {"max_bytes": 104857601}, {"max_rows": 0}, {"max_rows": 1}]:
        with pytest.raises(ValueError, match="ceiling"):
            cultural.prepare(path, **kwargs)
    with pytest.raises(ValueError, match="companion manifest"):
        cultural.prepare(path, {"schema_version": cultural.SCHEMA, "sha256": "0" * 64})
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="fingerprint"):
        cultural.prepare(path)
