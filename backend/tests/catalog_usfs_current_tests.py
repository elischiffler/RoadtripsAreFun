"""Current USFS refresh stays literal, attributable, and conservative."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from app.catalog import usfs, usfs_current
from app.routing.visit_calendar import source_calendar


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Open 24 hours/day", (0, 1440)),
        ("Day use only: open 6:00 a.m. to 10:00 p.m.", (360, 1320)),
        ("Open Year-Round, 6am-10pm daily", (360, 1320)),
        ("Open 7 days a week from 6:00 am to 8:00 pm.", (360, 1200)),
        ("Daily, 8:00 a.m. to 5:00 p.m.", (480, 1020)),
        ("Open 24 hours a day, 7 days a week unless otherwise posted.", None),
        ("Open 24 hours/day May - October", None),
        ("Day use only: open sunrise to sunset", None),
        ("Monday - Friday 9am-5pm", None),
        ("9am-5pm except holidays", None),
        ("13am-5pm", None),
        ("5pm-9am", None),
        ("Quiet hours are 10pm to 6am", None),
    ],
)
def test_literal_clock_parser(text, expected):
    assert usfs_current.clock_windows(text) == expected


def inputs():
    facility = {
        "site_cn": "1234.001",
        "usda_portal_id": "5678",
        "globalid": "native-global-id",
        "site_type": "TRAILHEAD",
        "development_status": "EXISTING",
        "recarea_enable": "Y",
        "seasonal_operational_status": "OPEN",
        "public_site_name": "Example Trailhead",
        "directions": "Take Highway 1 and turn into the trailhead parking lot.",
        "latitude": 40.0,
        "longitude": -120.0,
        "operational_hours": "Open 24 hours/day",
    }
    public = {
        "recareaid": 5678,
        "openstatus": "open",
        "latitude": 40.0,
        "longitude": -120.0,
        "recareaurl": "https://www.fs.usda.gov/recarea/example/",
        "operational_hours": None,
    }
    shapes = [
        ("CA", -121, -119, 39, 41, [[[-121, 39], [-119, 39], [-119, 41], [-121, 41], [-121, 39]]])
    ]
    return facility, public, shapes


def test_intersects_both_sources_and_preserves_native_arrival():
    a, b, shapes = inputs()
    a["operational_hours"] = "Day use only: open 6:00 a.m. to 10:00 p.m."
    b["operational_hours"] = "Day-use hours are 6 a.m. to 8 p.m."
    (row, hours), reason = usfs_current.qualify(a, b, shapes, date(2026, 10, 20))
    assert reason is None and hours == (360, 1200)
    assert row["source_id"] == "usfs:facility:1234.001"
    assert (row["latitude"], row["longitude"]) == (40, -120)


@pytest.mark.parametrize(
    "warning",
    [
        "Reservations are required.",
        "Requires a reservation.",
        "Permits required.",
        "A permit is required.",
        "Gates close at 5pm.",
        "Not accessible by car.",
        "Access may be limited by snow.",
        "Call for current restrictions.",
        "No car parking.",
        "No vehicle parking.",
        "Parking is not available.",
        "Parking prohibited.",
    ],
)
def test_positive_status_never_overrides_access_warning(warning):
    a, b, shapes = inputs()
    a["restrictions"] = warning
    result, reason = usfs_current.qualify(a, b, shapes, date(2026, 10, 20))
    assert result is None and reason


@pytest.mark.parametrize(
    "change",
    [
        "public_closed",
        "missing_public",
        "season",
        "unparsed_hours",
        "remote_point",
        "no_parking",
        "rough_road",
    ],
)
def test_unresolved_sources_are_held(change):
    a, b, shapes = inputs()
    if change == "public_closed":
        b["openstatus"] = "temporarily closed"
    if change == "missing_public":
        b = None
    if change == "season":
        a["open_season"] = "May - October"
    if change == "unparsed_hours":
        b["operational_hours"] = "Daylight hours"
    if change == "remote_point":
        b["latitude"] = 41
    if change == "no_parking":
        a["directions"] = "Take the trail uphill."
    if change == "rough_road":
        a["directions"] += " High-clearance vehicle required."
    result, reason = usfs_current.qualify(a, b, shapes, date(2026, 10, 20))
    assert result is None and reason


def bundle(tmp_path):
    a, b, _ = inputs()

    def retain(name, value, url):
        raw = json.dumps(value).encode()
        (tmp_path / name).write_bytes(raw)
        return {
            "path": name,
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "retrieved_at": "2026-10-20T02:00:00+00:00",
            "status": 200,
        }

    states = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"STUSAB": "CA" if i == 0 else "NV"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-121, 39], [-119, 39], [-119, 41], [-121, 41], [-121, 39]]]
                    if i == 0
                    else [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                },
            }
            for i in range(56)
        ],
    }
    drive = retain(
        "drive.json",
        {"code": "Ok", "waypoints": [{"distance": 0}, {"distance": 12, "name": "Visitor Road"}]},
        "https://router.project-osrm.org/route/v1/driving/-120.0,40.01;-120.0,40.0?overview=false",
    )
    drive.update(
        checked_waypoint="destination",
        source_coordinates=[40.0, -120.0],
        snap_distance_m=12,
        road_name="Visitor Road",
    )
    data = {
        "schema_version": usfs_current.SCHEMA,
        "reviewed_on": "2026-10-20",
        "selected_site_ids": [a["site_cn"]],
        "facilities": [
            retain(
                "facility.json", {"features": [{"attributes": a}]}, usfs.FACILITY_URL + "?f=json"
            )
        ],
        "public": [
            retain(
                "public.json",
                {"features": [{"attributes": b}]},
                usfs.PUBLIC_URL
                + "?f=json&where=recareaid+IN+%285678%29&outFields=*&returnGeometry=true&outSR=4326",
            )
        ],
        "states": retain("states.json", states, usfs.STATE_URL + "?f=geojson"),
        "driving": [{"site_cn": a["site_cn"], "receipt": drive}],
    }
    path = tmp_path / "bundle.json"

    def write():
        raw = json.dumps(data).encode()
        path.write_bytes(raw)
        licenses = {}
        for key, digest in usfs_current.LICENSE_PINS.items():
            source = (
                Path(__file__).resolve().parents[2]
                / "frontend"
                / "public"
                / "licenses"
                / (key + ".txt")
            )
            (tmp_path / (key + ".txt")).write_bytes(source.read_bytes())
            licenses[key] = {
                "path": key + ".txt",
                "sha256": digest,
                "url": usfs_current.LICENSE_URLS[key],
            }
        return {
            "schema_version": usfs_current.SCHEMA,
            "licenses": licenses,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_url": usfs_current.SOURCE_URL,
            "attribution": usfs_current.ATTRIBUTION,
            "release": "usfs-current-2026-10-20",
        }

    return data, path, write


def test_replays_hashed_evidence_into_bounded_calendar(tmp_path):
    _, path, write = bundle(tmp_path)
    rows, report = usfs_current.prepare(path, write())
    assert len(rows) == 1 and report["accepted"] == 1
    calendar = source_calendar({"source_provenance": [report["calendar_entries"][0]]})
    assert calendar and calendar.weekly_windows[0].end_day_offset == 1
    assert calendar.seasons[0].start == "2026-10-20"
    assert calendar.seasons[0].end == "2026-11-18"
    assert (
        rows[0]["provenance"][0]["published_access_facts"]["construction_feed"]["record_id"]
        == "1234.001"
    )
    assert report["calendar_entries"][0]["source_constraints"][0]["fields"]["directions"].endswith(
        "parking lot."
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "bad_hash",
        "escaped_path",
        "old_receipt",
        "future_receipt",
        "wrong_endpoint",
        "duplicate_source",
        "truncated_public",
        "wrong_release",
        "row_ceiling",
        "byte_ceiling",
    ],
)
def test_replay_rejects_untrusted_or_unbounded_artifacts(tmp_path, mutation):
    data, path, write = bundle(tmp_path)
    if mutation == "bad_hash":
        data["facilities"][0]["sha256"] = "0" * 64
    if mutation == "escaped_path":
        data["facilities"][0]["path"] = "../facility.json"
    if mutation == "old_receipt":
        data["facilities"][0]["retrieved_at"] = "2026-10-10T02:00:00+00:00"
    if mutation == "future_receipt":
        data["facilities"][0]["retrieved_at"] = "2026-10-21T02:00:00+00:00"
    if mutation == "wrong_endpoint":
        data["facilities"][0]["url"] = "https://example.com/source"
    if mutation == "duplicate_source":
        data["facilities"].append(data["facilities"][0])
    if mutation == "truncated_public":
        p = tmp_path / "public.json"
        j = json.loads(p.read_bytes())
        j["exceededTransferLimit"] = True
        raw = json.dumps(j).encode()
        p.write_bytes(raw)
        data["public"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest = write()
    if mutation == "wrong_release":
        manifest["release"] = "usfs-current-2026-10-21"
    with pytest.raises(ValueError):
        usfs_current.prepare(
            path,
            manifest,
            max_rows=0 if mutation == "row_ceiling" else 10_000,
            max_bytes=1 if mutation == "byte_ceiling" else 64 * 1024 * 1024,
        )


def test_road_snap_holds_instead_of_substituting_nearest_coordinate(tmp_path):
    data, path, write = bundle(tmp_path)
    data["driving"] = []
    rows, report = usfs_current.prepare(path, write())
    assert rows == [] and report["rejects"] == {"native_arrival_driving_check_missing": 1}


def add_publication(tmp_path, data):
    contracts = []
    for index, endpoint in enumerate(usfs_current.PUBLICATION_ENDPOINTS):
        body = json.dumps(
            {
                "description": usfs_current.PUBLICATION_STATEMENT,
                "capabilities": "Map,Query,Data",
                "fields": [
                    {"name": name}
                    for name in [
                        "site_cn",
                        "latitude",
                        "longitude",
                        "operational_hours",
                        "directions",
                        "seasonal_operational_status",
                        "recarea_enable",
                    ]
                ],
            }
        ).encode()
        name = f"publication-{index}.json"
        (tmp_path / name).write_bytes(body)
        contracts.append(
            {
                "path": name,
                "url": endpoint + "?f=json",
                "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at": "2026-10-20T02:00:00+00:00",
                "status": 200,
            }
        )
    data["publication_contract"] = contracts


@pytest.mark.parametrize("status", [None, "none", "open"])
def test_separate_primary_path_preserves_independent_legacy_unknowns(status):
    a, b, shapes = inputs()
    b["openstatus"] = status
    row, reason = usfs_current.qualify(a, b, shapes, date(2026, 10, 20), primary_publication=True)
    assert row is not None and reason is None
    if status != "open":
        assert usfs_current.qualify(a, b, shapes, date(2026, 10, 20))[0] is None


def test_primary_path_accepts_missing_legacy_without_inventing_open(tmp_path):
    data, path, write = bundle(tmp_path)
    add_publication(tmp_path, data)
    public_path = tmp_path / "public.json"
    raw = b'{"features": []}'
    public_path.write_bytes(raw)
    data["public"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    rows, report = usfs_current.prepare(path, write())
    assert len(rows) == 1
    assert rows[0]["provenance"][0]["legacy_public_status"] == "record missing; not asserted open"
    assert len(report["calendar_entries"][0]["source_visit_calendar"]["source_receipts"]) == 4
    assert report["calendar_entries"][0]["source_constraints"][1]["published_status"].startswith(
        "record missing"
    )


@pytest.mark.parametrize("status", ["closed", "temporarily closed", "not open", "unrecognized"])
def test_primary_source_never_overrides_known_legacy_negative(status):
    a, b, shapes = inputs()
    b["openstatus"] = status
    result, reason = usfs_current.qualify(
        a, b, shapes, date(2026, 10, 20), primary_publication=True
    )
    assert result is None and reason == "known_public_negative_or_unrecognized_status"


@pytest.mark.parametrize("point", [float("nan"), float("inf"), True, 91, -91])
def test_primary_public_corrobation_requires_real_finite_coordinates(point):
    a, b, shapes = inputs()
    b["latitude"] = point
    result, reason = usfs_current.qualify(
        a, b, shapes, date(2026, 10, 20), primary_publication=True
    )
    assert result is None and reason == "public_coordinates_missing"


@pytest.mark.parametrize(
    "mutation",
    [
        "omitted_lookup",
        "filtered_lookup",
        "omitted_status_fields",
        "extra_object_ids",
        "wrong_purpose",
        "missing_fields",
        "changed_license",
        "missing_license",
        "scan_budget",
    ],
)
def test_primary_contract_cannot_hide_negatives_or_change_rights(tmp_path, mutation):
    data, path, write = bundle(tmp_path)
    add_publication(tmp_path, data)
    if mutation == "omitted_lookup":
        data["public"] = []
    if mutation == "filtered_lookup":
        data["public"][0]["url"] = data["public"][0]["url"].replace(
            "%285678%29", "%285678%29+AND+openstatus%3D%27open%27"
        )
    if mutation == "omitted_status_fields":
        data["public"][0]["url"] = data["public"][0]["url"].replace(
            "outFields=*", "outFields=recareaid,latitude,longitude"
        )
    if mutation == "extra_object_ids":
        data["public"][0]["url"] += "&objectIds=999"
    if mutation in {"wrong_purpose", "missing_fields"}:
        receipt = data["publication_contract"][1]
        body = json.loads((tmp_path / receipt["path"]).read_bytes())
        if mutation == "wrong_purpose":
            body["description"] = "For internal administrative use only."
        else:
            body["fields"] = []
        raw = json.dumps(body).encode()
        (tmp_path / receipt["path"]).write_bytes(raw)
        receipt["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest = write()
    if mutation == "changed_license":
        manifest["licenses"]["ODbL-1.0"]["sha256"] = "0" * 64
    if mutation == "missing_license":
        del manifest["licenses"]["ODbL-1.0"]
    with pytest.raises(ValueError):
        usfs_current.prepare(path, manifest, max_rows=1 if mutation == "scan_budget" else 10_000)


def test_continuous_corridor_checks_segments_between_sparse_vertices():
    grid = usfs_current.corridor_grid([("route", [[-121, 40], [-119, 40]])])
    assert usfs_current.nearby_corridors(40, -120, grid) == ["route"]
    assert usfs_current.nearby_corridors(41, -120, grid) == []


def test_acquisition_replays_public_unknowns_and_serializes_road_requests(tmp_path, monkeypatch):
    from urllib.parse import urlsplit

    import requests

    template = tmp_path / "template"
    template.mkdir()
    fixture, _, write = bundle(template)
    add_publication(template, fixture)
    write()
    a, _, _ = inputs()
    second = {
        **a,
        "site_cn": "1234.002",
        "usda_portal_id": "5679",
        "longitude": -120.01,
        "public_site_name": "Second Trailhead",
    }
    states = json.loads((template / "states.json").read_bytes())
    contract = json.loads((template / "publication-1.json").read_bytes())
    route_root = tmp_path / "routes"
    route_root.mkdir()
    raw = json.dumps(
        {
            "code": "Ok",
            "routes": [
                {"geometry": {"type": "LineString", "coordinates": [[-121, 40], [-119, 40]]}}
            ],
        }
    ).encode()
    (route_root / "route.json").write_bytes(raw)
    (route_root / "index.json").write_text(
        json.dumps(
            {
                "routes": [{"id": "test", "response_path": "route.json"}],
                "receipts": [
                    {
                        "path": "route.json",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "url": "https://router.project-osrm.org/route/v1/driving/-121,40;-119,40",
                        "status": 200,
                    }
                ],
            }
        )
    )
    calls, sleeps = [], []

    class Response:
        status_code = 200

        def __init__(self, value):
            self.body = json.dumps(value).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_content(self, size):
            yield self.body

    def get(url, **kwargs):
        calls.append((url, kwargs))
        endpoint = url.split("?")[0]
        if endpoint in usfs_current.PUBLICATION_ENDPOINTS:
            return Response(contract)
        if endpoint == usfs.FACILITY_URL:
            return Response({"features": [{"attributes": a}, {"attributes": second}]})
        if endpoint == usfs.PUBLIC_URL:
            return Response({"features": []})
        if endpoint == usfs.STATE_URL:
            return Response(states)
        if urlsplit(url).hostname == "router.project-osrm.org":
            return Response(
                {
                    "code": "Ok",
                    "waypoints": [{"distance": 0}, {"distance": 12, "name": "Visitor Road"}],
                }
            )
        raise AssertionError("unexpected remote endpoint")

    monkeypatch.setattr(requests, "get", get)
    ticks = iter([0, 0.2, 1.0])
    monkeypatch.setattr(usfs_current.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(usfs_current.time, "sleep", sleeps.append)
    result = usfs_current.acquire(
        tmp_path / "output",
        parent_rows=[],
        routes_index=route_root / "index.json",
        route_root=route_root,
    )
    assert result["accepted"] == 2 and result["database_write"] is False
    assert result["driving_receipts"] == 2 and sleeps == [0.8]
    assert all(call[1]["allow_redirects"] is False and call[1]["stream"] for call in calls)
    rows, replay = usfs_current.prepare(result["source_path"])
    assert len(rows) == 2 and replay["scanned"] == 2
    assert all(
        row["provenance"][0]["legacy_public_status"].startswith("record missing") for row in rows
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("season_name", "SUMMER"),
        ("site_season_start_date", 0),
        ("site_season_end_date", 1790000000000),
        ("op_status_reason", "Road closed due to flood"),
    ],
)
def test_native_season_or_status_reason_is_not_discarded(field, value):
    a, b, shapes = inputs()
    a[field] = value
    result, reason = usfs_current.qualify(
        a, b, shapes, date(2026, 10, 20), primary_publication=True
    )
    assert result is None and reason
