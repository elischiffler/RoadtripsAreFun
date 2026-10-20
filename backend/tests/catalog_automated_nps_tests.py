"""Generic source adapter invariants; synthetic bodies make no factual claims."""

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.catalog import automated_nps as module
from app.routing.visit_calendar import source_calendar


def schedule(start="9:00 AM", end="5:00 PM", ident=1, kind="Visitor Center"):
    return {
        "operatingScheduleID": ident,
        "type": kind,
        "name": "River Museum Visitor Center",
        "description": "",
        "label": "",
        "hours": [
            {
                "dayOfWeek": n,
                "is_closed": 0,
                "sunrise_open": 0,
                "sunset_close": 0,
                "time_open": start,
                "time_close": end,
            }
            for n in range(1, 8)
        ],
        "exceptions": [],
    }


def document():
    native = schedule()
    parking = {
        "operatingScheduleID": 3,
        "type": "Parking Lot",
        "hours": [
            {
                "dayOfWeek": n,
                "isClosed": 0,
                "sunriseOpen": 0,
                "sunsetClose": 0,
                "timeOpen": "8:00 AM",
                "timeClose": "4:00 PM",
            }
            for n in range(1, 8)
        ],
    }
    return {
        "siteCode": "test",
        "physicalAddressCountryCode": "US",
        "name": "Example National Park",
        "url": "https://www.nps.gov/test/",
        "visitorCenters": [
            {
                "visitorCenterID": 7,
                "name": "River Museum Visitor Center",
                "location": {"latitude": "37.0", "longitude": "-122.0"},
                "physical_address": {"state_code": "CA", "line_1": "10 Museum Road"},
                "amenities": ["Parking - Auto"],
                "directions": "Drive on Museum Road to the visitor parking lot.",
                "description": "Open daily 9:00 AM to 5:00 PM.",
                "operatingHours": {"1": native},
                "siteURL": "https://www.nps.gov/test/visitor-center.htm",
            }
        ],
        "parkingLots": [
            {
                "lotID": "00000000-0000-0000-0000-000000000001",
                "name": "River Museum Visitor Center Parking",
                "description": "Visitor parking for River Museum Visitor Center.",
                "latitude": "37.0001",
                "longitude": "-122.0",
                "totalParkingSpaces": 10,
                "schedule": parking,
            }
        ],
        "operatingHours": [native, schedule("8:00 AM", "6:00 PM", 2, "All Park")],
    }


def receipt(checked="2026-12-20T12:00:00+00:00"):
    return {
        "source_url": "https://www.nps.gov/test/structured_data_test.json",
        "snapshot_sha256": "a" * 64,
        "checked_at": checked,
        "evidence_path": "sources/test.json",
    }


def windows(entry, day="2026-12-20"):
    return next(
        value["windows"]
        for value in entry["source_visit_calendar"]["date_overrides"]
        if value["date"] == day
    )


def test_exact_native_points_and_calendar_intersect_facility_parent_and_named_parking():
    original = document()
    pristine = copy.deepcopy(original)
    row, entry = module.transform(original, "test", 0, receipt())
    assert original == pristine
    assert row["source_id"] == "nps-public:facility:test:7"
    assert (row["latitude"], row["longitude"]) == (37.0, -122.0)
    assert windows(entry) == [{"opens": "09:00", "closes": "16:00", "end_day_offset": 0}]
    assert source_calendar({"source_provenance": [entry]}) is not None
    assert row["provenance"][0]["native_coordinates_replaced"] is False


def test_literal_prose_narrows_each_day_instead_of_matching_union_of_native_clocks():
    value = document()
    native = value["visitorCenters"][0]["operatingHours"]["1"]
    native["hours"][1]["time_open"] = "8:00 AM"
    _, entry = module.transform(value, "test", 0, receipt())
    assert windows(entry, "2026-12-21")[0]["opens"] == "09:00"


def test_named_holiday_closures_never_reopen_and_are_evaluated_in_actual_year():
    value = document()
    value["visitorCenters"][0]["description"] += " Closed on Christmas Day and New Year's Day."
    _, entry = module.transform(value, "test", 0, receipt())
    assert windows(entry, "2026-12-25") == []
    assert windows(entry, "2027-01-01") == []
    assert windows(entry, "2026-12-26")


@pytest.mark.parametrize(
    "text",
    [
        "No public parking is available.",
        "Parking is not available.",
        "Reservations are required.",
        "Requires a reservation.",
        "Permits required.",
        "A permit is required.",
        "Open only in winter.",
        "Gate closes at sunset.",
        "Closed on observed holidays.",
        "Last admission at 3pm.",
        "Open daily 9am–noon and 1pm–5pm.",
    ],
)
def test_unresolved_published_qualifications_are_held(text):
    value = document()
    value["visitorCenters"][0]["description"] = text
    with pytest.raises(module.Hold):
        module.transform(value, "test", 0, receipt())


def test_typed_other_facility_and_campground_closures_are_retained_separately():
    value = document()
    other = schedule(ident=99, kind="Campground")
    other["description"] = "Closed indefinitely due to construction."
    value["operatingHours"].append(other)
    _, entry = module.transform(value, "test", 0, receipt())
    assert windows(entry)
    assert entry["source_constraints"][-2]["scope"] == "other_native_typed_component"


def test_solar_parking_and_unknown_lot_association_cannot_use_frontage_to_bypass_hold():
    value = document()
    value["parkingLots"][0]["schedule"]["hours"][0]["sunriseOpen"] = 1
    _, entry = module.transform(value, "test", 0, receipt())
    assert not any(
        day["date"] == "2026-12-20" for day in entry["source_visit_calendar"]["date_overrides"]
    )
    assert entry["transformation"]["withheld_dates"]
    value["parkingLots"][0]["name"] = "Other attraction lot"
    value["parkingLots"][0]["description"] = "For another attraction."
    with pytest.raises(module.Hold, match="relationship_unresolved"):
        module.transform(value, "test", 0, receipt())


def bundle(tmp_path):
    checked = datetime.now(UTC).isoformat()

    def write(name, value, url):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value).encode()
        path.write_bytes(raw)
        return {
            "url": url,
            "path": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "retrieved_at": checked,
            "status": 200,
            "bytes": len(raw),
        }

    source = write("sources/test.json", document(), receipt()["source_url"])
    drive = write(
        "driving/test.json",
        {"code": "Ok", "waypoints": [{}, {"distance": 3, "name": "Museum Road"}]},
        "https://router.project-osrm.org/route/v1/driving/-122.0,37.01;-122.0,37.0?overview=false",
    )
    drive.update(
        checked_waypoint="destination",
        source_coordinates=[37.0, -122.0],
        road_name="Museum Road",
        snap_distance_m=3,
    )
    control = {
        "schema_version": module.SCHEMA,
        "inputs": {"test": source},
        "driving": {"nps-public:facility:test:7": drive},
    }
    path = tmp_path / "nps.source.json"
    path.write_text(json.dumps(control))
    licenses = {
        identifier: write(name, "synthetic rights fixture", url)
        for identifier, name, url in [
            (
                "LicenseRef-US-Government-Work",
                "rights/nps.json",
                "https://www.nps.gov/aboutus/disclaimer.htm",
            ),
            ("ODbL-1.0", "rights/odbl.json", "https://opendatacommons.org/licenses/odbl/1-0/"),
        ]
    }
    manifest = {
        "schema_version": module.SCHEMA,
        "source_url": module.SOURCE_URL,
        "attribution": module.ATTRIBUTION,
        "release": "nps-facilities-" + datetime.now(UTC).date().isoformat(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "licenses": licenses,
    }
    return path, manifest, control


def test_offline_prepare_replays_raw_drive_and_counts_auxiliary_source_records(tmp_path):
    path, manifest, _ = bundle(tmp_path)
    rows, report = module.prepare(path, manifest)
    assert len(rows) == 1
    assert report["scanned"] == 5
    assert report["source_rows"] == {
        "units": 1,
        "visitor_facilities": 1,
        "parking_lots": 1,
        "parent_schedule_slots": 2,
    }
    assert len(report["calendar_entries"]) == 1
    assert report["bytes"] > 0


def test_snapshot_tampering_and_too_small_source_budget_fail_closed(tmp_path):
    path, manifest, _ = bundle(tmp_path)
    with pytest.raises(ValueError, match="row ceiling"):
        module.prepare(path, manifest, max_rows=4)
    (tmp_path / "sources/test.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        module.prepare(path, manifest)


def test_changed_raw_driving_summary_is_an_explicit_hold(tmp_path):
    path, manifest, control = bundle(tmp_path)
    control["driving"]["nps-public:facility:test:7"]["source_coordinates"] = [37.1, -122.0]
    path.write_text(json.dumps(control))
    manifest["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    rows, report = module.prepare(path, manifest)
    assert rows == []
    assert (
        report["rejection_ledger"][0]["reason"] == "market driving query changed the native point"
    )


def test_documented_facility_auto_parking_accepts_unnamed_internal_aisle_without_inventing_lot_hours(
    tmp_path,
):
    path, manifest, control = bundle(tmp_path)
    value = document()
    value["parkingLots"] = []
    source = tmp_path / "sources/test.json"
    source.write_text(json.dumps(value))
    control["inputs"]["test"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    control["inputs"]["test"]["bytes"] = source.stat().st_size
    drive = tmp_path / "driving/test.json"
    drive.write_text(json.dumps({"code": "Ok", "waypoints": [{}, {"distance": 3, "name": ""}]}))
    control["driving"]["nps-public:facility:test:7"].update(
        road_name="",
        sha256=hashlib.sha256(drive.read_bytes()).hexdigest(),
        bytes=drive.stat().st_size,
    )
    path.write_text(json.dumps(control))
    manifest["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    rows, report = module.prepare(path, manifest)
    assert len(rows) == 1
    assert rows[0]["provenance"][0]["arrival_type"] == "documented_auto_parking_visitor_facility"
    assert rows[0]["provenance"][0]["parking_lot_ids"] == []
    assert (
        windows(report["calendar_entries"][0], datetime.now(UTC).date().isoformat())[0]["closes"]
        == "17:00"
    )
    value["visitorCenters"][0]["amenities"] = []
    with pytest.raises(module.Hold, match="auto_arrival_missing"):
        module.transform(value, "test", 0, receipt())


def test_acquire_retains_authentic_response_bytes_and_produces_offline_replayable_sidecar(
    tmp_path, monkeypatch
):
    import requests

    seen = []

    class Response:
        status_code = 200

        def __init__(self, value):
            self.raw = json.dumps(value).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, _size):
            yield self.raw

    def get(url, **kwargs):
        assert kwargs == {"timeout": (10, 30), "stream": True, "allow_redirects": False}
        seen.append(url)
        if "carto.nps.gov" in url:
            return Response({"rows": [{"unit_code": "test"}]})
        if "structured_data_test.json" in url:
            return Response(document())
        if "router.project-osrm.org" in url:
            return Response(
                {"code": "Ok", "waypoints": [{}, {"distance": 3, "name": "Museum Road"}]}
            )
        return Response("Synthetic rights fixture")

    monkeypatch.setattr(requests, "get", get)
    result = module.acquire(tmp_path / "acquired", ["test"])
    manifest = json.loads((tmp_path / "acquired/nps.source.json.manifest.json").read_text())
    rows, report = module.prepare(result["source_path"], manifest)
    assert len(rows) == 1
    assert report["scanned"] == 5
    assert len(seen) == 5
    assert not any("api_key" in url for url in seen)
    with pytest.raises(FileExistsError):
        module.acquire(tmp_path / "acquired", ["test"])


@pytest.mark.parametrize("violation", ["redirect_status", "unexpected_final_url"])
def test_acquire_rejects_redirects_and_unexpected_final_identity_before_consuming_body(
    tmp_path, monkeypatch, violation
):
    import requests

    class Response:
        status_code = 302 if violation == "redirect_status" else 200
        url = "https://example.com/other" if violation == "unexpected_final_url" else ""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, _size):
            raise AssertionError("untrusted response body must not be consumed")

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="redirected"):
        module.acquire(tmp_path / "rejected", ["test"])


def test_explicit_arrival_selectors_do_not_accept_arbitrary_hosts_or_query_endpoints(
    tmp_path, monkeypatch
):
    import requests

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("no network before selector validation"),
    )
    with pytest.raises(ValueError, match="official public HTML"):
        module.acquire(
            tmp_path / "rejected",
            ["test"],
            arrival_page_urls=["https://example.com/directions.htm"],
        )


def test_acquire_explicit_native_arrival_selector_replays_whole_car_source_without_changing_point(
    tmp_path, monkeypatch
):
    import requests

    arrival_url = "https://www.nps.gov/test/planyourvisit/directions.htm"
    value = document()
    value["directionsURL"] = arrival_url
    value["parkingLots"] = []
    facility = value["visitorCenters"][0]
    facility["directions"] = "Located inside the public office building."
    facility["physical_address"].update(city="Example City", postal_code="12345")
    html = b"<h4>River Museum Visitor Center</h4><p>10 Museum Road, Example City, CA 12345</p><h3>Getting here by:</h3><h4>Car</h4><p>Take exit 4 from Interstate 80. Turn onto Museum Road. Continue to the visitor parking lot.</p><h4>Plane</h4><p>Airport nearby.</p>"
    seen = []

    class Response:
        status_code = 200

        def __init__(self, url, data):
            self.url, self.raw = url, data if isinstance(data, bytes) else json.dumps(data).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, _size):
            yield self.raw

    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        seen.append(url)
        if "carto.nps.gov" in url:
            return Response(url, {"rows": [{"unit_code": "test"}]})
        if "structured_data_test.json" in url:
            return Response(url, value)
        if url == arrival_url:
            return Response(url, html)
        if "router.project-osrm.org" in url:
            return Response(url, {"code": "Ok", "waypoints": [{}, {"distance": 3, "name": ""}]})
        return Response(url, "Synthetic rights fixture")

    monkeypatch.setattr(requests, "get", get)
    result = module.acquire(tmp_path / "acquired", ["test"], arrival_page_urls=[arrival_url])
    manifest = json.loads(Path(result["manifest_path"]).read_text())
    rows, report = module.prepare(result["source_path"], manifest)
    assert len(rows) == 1 and seen.count(arrival_url) == 1
    assert (rows[0]["latitude"], rows[0]["longitude"]) == (37.0, -122.0)
    assert len(report["calendar_entries"][0]["source_visit_calendar"]["source_receipts"]) == 2
    assert rows[0]["provenance"][-1]["car_section"].startswith("Take exit 4")


def test_acquire_serializes_two_driving_requests_at_one_per_second(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import requests

    value = document()
    value["parkingLots"] = []
    second = copy.deepcopy(value["visitorCenters"][0])
    second.update(visitorCenterID=8, location={"latitude": "38.0", "longitude": "-122.0"})
    value["visitorCenters"].append(second)
    ticks, delays = iter([10.0, 10.25, 11.0]), []
    monkeypatch.setattr(
        module, "time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=delays.append)
    )

    class Response:
        status_code = 200

        def __init__(self, url, data):
            self.url, self.raw = url, json.dumps(data).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, _size):
            yield self.raw

    def get(url, **kwargs):
        if "carto.nps.gov" in url:
            return Response(url, {"rows": [{"unit_code": "test"}]})
        if "structured_data_test.json" in url:
            return Response(url, value)
        if "router.project-osrm.org" in url:
            return Response(url, {"code": "Ok", "waypoints": [{}, {"distance": 3, "name": ""}]})
        return Response(url, "Synthetic rights fixture")

    monkeypatch.setattr(requests, "get", get)
    result = module.acquire(tmp_path / "acquired", ["test"])
    assert result["driving_receipts"] == 2
    assert delays == [0.75]
