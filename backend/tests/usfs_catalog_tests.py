"""Source admission boundaries, native-point fidelity and raw-receipt checks."""

import copy
import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from app.catalog import identity, usfs


def sources():
    facility = {
        "site_cn": "1234567890",
        "site_type": "TRAILHEAD",
        "development_status": "EXISTING",
        "recarea_enable": "Y",
        "seasonal_operational_status": "OPEN",
        "usda_portal_id": "42",
        "directions": "Drive along Highway 1 to the public parking lot at the trailhead.",
        "recarea_description": "Public visitor trailhead with parking.",
        "latitude": 37.8,
        "longitude": -122.4,
        "public_site_name": "Source Trailhead",
        "globalid": "{00000000-0000-0000-0000-000000000042}",
        "states_spanned": "CA",
    }
    public = {
        "recareaid": 42,
        "openstatus": "open",
        "latitude": "37.8001",
        "longitude": "-122.4",
        "recareadescription": "Designated public visitor parking and trail access.",
        "recareaurl": "https://www.fs.usda.gov/recarea/example/recarea/?recid=42",
    }
    polygon = [[[-123, 37], [-122, 37], [-122, 38], [-123, 38], [-123, 37]]]
    shapes = [("CA", -123, -122, 37, 38, polygon)]
    return facility, public, shapes


def test_native_facility_point_and_identity_are_preserved():
    facility, public, shapes = sources()
    row, reason = usfs.qualification(facility, public, shapes)
    assert reason is None
    assert (row["latitude"], row["longitude"]) == (37.8, -122.4)
    assert row["latitude"] != float(public["latitude"])
    assert row["source_id"] == "usfs:42"
    assert identity.identity(row["source_id"]) == ("usfs:42", "usfs")
    assert row["address"] is None and row["source_updated_at"] is None
    assert "opening_hours" not in row and "rating" not in row and "price" not in row


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("site_type", "CAMPGROUND", "ineligible_facility_type_or_development"),
        ("development_status", "PLANNED", "ineligible_facility_type_or_development"),
        ("recarea_enable", "N", "not_published_open"),
        ("seasonal_operational_status", "CLOSED", "not_published_open"),
        ("directions", None, "parking_or_directions_not_documented"),
        ("latitude", float("nan"), "coordinates"),
        ("latitude", True, "coordinates"),
        ("states_spanned", "NV", "published_state_conflict"),
        ("site_cn", "../42", "native_identity"),
    ],
)
def test_invalid_or_unusable_facility_is_not_counted(field, value, reason):
    facility, public, shapes = sources()
    facility[field] = value
    assert usfs.qualification(facility, public, shapes) == (None, reason)


@pytest.mark.parametrize("status", [None, "none", "closed", "unreachable", "temporarily closed"])
def test_open_construction_enum_cannot_override_public_access_evidence(status):
    facility, public, shapes = sources()
    public["openstatus"] = status
    assert usfs.qualification(facility, public, shapes)[1] == "public_status_not_open_or_missing"


@pytest.mark.parametrize(
    "warning",
    [
        "A four-wheel drive vehicle is best for the approach.",
        "The road is extremely rough and not recommended for passenger cars.",
        "This is human powered snow access only.",
        "The last two miles are not recommended for low clearance vehicles.",
    ],
)
def test_vehicle_qualifications_are_withheld(warning):
    facility, public, shapes = sources()
    facility["important_info"] = warning
    assert usfs.qualification(facility, public, shapes)[1] == "published_vehicle_access_warning"


@pytest.mark.parametrize("site", list(usfs.REVIEW_HOLDS))
def test_inspected_conflicting_seasons_and_point_roles_remain_withheld(site):
    facility, public, shapes = sources()
    facility["site_cn"] = site
    assert usfs.qualification(facility, public, shapes)[1].startswith("review_hold:")


def test_record_id_and_spatial_disagreements_fail():
    facility, public, shapes = sources()
    public["recareaid"] = 43
    assert usfs.qualification(facility, public, shapes)[1] == "public_identity_mismatch"
    public["recareaid"] = 42
    public["latitude"] = "38.0"
    assert (
        usfs.qualification(facility, public, shapes)[1]
        == "public_identity_point_more_than_500m_away"
    )


def test_state_holes_overlaps_and_territories_do_not_become_us_states():
    _, _, shapes = sources()
    assert usfs.state_for([37.8, -122.4], shapes) == "CA"
    assert usfs.state_for([0, 0], shapes) is None
    hole = [[-122.5, 37.7], [-122.3, 37.7], [-122.3, 37.9], [-122.5, 37.9], [-122.5, 37.7]]
    with_hole = copy.deepcopy(shapes)
    with_hole[0][-1].append(hole)
    assert usfs.state_for([37.8, -122.4], with_hole) is None
    overlap = [("NV", *shapes[0][1:])]
    assert usfs.state_for([37.8, -122.4], shapes + overlap) is None
    assert usfs.state_for([37.8, -122.4], [("PR", *shapes[0][1:])]) is None


def receipt(tmp_path, payload=None):
    now = datetime.now(UTC).isoformat()
    raw = json.dumps(
        payload
        or {
            "code": "Ok",
            "waypoints": [{"name": "origin", "distance": 1}, {"name": "Highway 1", "distance": 5}],
        }
    ).encode()
    (tmp_path / "response.json").write_bytes(raw)
    return {
        "path": "response.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": now,
        "status": 200,
        "checked_waypoint": "destination",
        "source_coordinates": [37.8, -122.4],
        "road_name": "Highway 1",
        "snap_distance_m": 5,
        "url": "https://router.project-osrm.org/route/v1/driving/-122.4,37.809999999999995;-122.4,37.8?overview=false&steps=false&alternatives=false",
    }


def test_raw_destination_and_query_must_match_native_point(tmp_path):
    entry = receipt(tmp_path)
    row = {"latitude": 37.8, "longitude": -122.4}
    assert usfs.driving(tmp_path, entry, row)[1:] == (5, "Highway 1")
    with pytest.raises(ValueError, match="native facility point"):
        usfs.driving(tmp_path, entry, {"latitude": 37.81, "longitude": -122.4})
    entry["road_name"] = "invented road"
    with pytest.raises(ValueError, match="summary disagrees"):
        usfs.driving(tmp_path, entry, row)


def test_response_checksum_destination_role_staleness_and_escape_fail(tmp_path):
    entry = receipt(tmp_path)
    changed = {**entry, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="checksum"):
        usfs.retained(tmp_path, changed)
    with pytest.raises(ValueError, match="escapes"):
        usfs.retained(tmp_path, {**entry, "path": "../response.json"})
    with pytest.raises(ValueError, match="30 days"):
        usfs.retained(
            tmp_path,
            {**entry, "retrieved_at": (datetime.now(UTC) - timedelta(days=31)).isoformat()},
        )
    with pytest.raises(ValueError, match="driving destination"):
        usfs.driving(
            tmp_path,
            {**entry, "checked_waypoint": "origin"},
            {"latitude": 37.8, "longitude": -122.4},
        )


def test_non_successful_or_distant_raw_route_cannot_be_counted(tmp_path):
    row = {"latitude": 37.8, "longitude": -122.4}
    entry = receipt(tmp_path, {"code": "NoSegment"})
    with pytest.raises(ValueError, match="successful"):
        usfs.driving(tmp_path, entry, row)
    entry = receipt(
        tmp_path, {"code": "Ok", "waypoints": [{}, {"name": "Highway 1", "distance": 76}]}
    )
    with pytest.raises(ValueError, match="too distant"):
        usfs.driving(tmp_path, entry, row)


@pytest.mark.parametrize(
    "start,end,day,rejected",
    [
        ("May 20", "Sept. 12", date(2026, 10, 15), True),
        ("Dec 1", "March 31", date(2026, 10, 15), True),
        ("Dec 1", "March 31", date(2026, 12, 1), False),
        ("Dec 1", "March 31", date(2026, 1, 15), False),
        ("Dec 1", "March 31", date(2026, 3, 31), False),
        ("May 20", "Sept. 12", date(2026, 9, 12), False),
        ("May 20", "Sept. 12", date(2026, 5, 19), True),
        ("6/1", "10/15", date(2026, 10, 15), False),
        ("April 15th", "30 November", date(2026, 10, 15), False),
    ],
)
def test_open_enums_do_not_override_public_season_dates(start, end, day, rejected):
    facility, public, shapes = sources()
    public.update(open_season_start=start, open_season_end=end)
    row, reason = usfs.qualification(facility, public, shapes, as_of=day)
    if rejected:
        assert (row, reason) == (None, "public_season_outside_dated_admission")
    else:
        assert reason is None
        assert "opening_hours" not in row


@pytest.mark.parametrize(
    "value", [None, "Summer", "October", "09/15; reduced service rest of year", "Feb 30"]
)
def test_incomplete_or_qualified_seasons_are_not_invented_as_calendar_dates(value):
    assert usfs.recurring_day(value) is None


def test_default_admission_uses_the_current_date(monkeypatch):
    class AdmissionTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 15, tzinfo=tz)

    monkeypatch.setattr(usfs, "datetime", AdmissionTime)
    facility, public, shapes = sources()
    public.update(open_season_start="May 20", open_season_end="Sept. 12")
    assert (
        usfs.qualification(facility, public, shapes)[1] == "public_season_outside_dated_admission"
    )


def test_inspected_daily_gate_hours_do_not_bypass_changed_or_other_closures():
    facility, public, shapes = sources()
    facility.update(site_cn="5339.003721", usda_portal_id="20698")
    public["recareaid"] = 20698
    facility["operational_hours"] = "Daily 08:30 a.m. - 04:30 p.m."
    public["operational_hours"] = (
        "Open Daily&nbsp;8:30 a.m.&ndash; 4:30 p.m.<br /><em>"
        "(entrance gate closed&nbsp;at 4:15 p.m.)</em>&nbsp; &nbsp;"
    )
    assert usfs.qualification(facility, public, shapes)[1] is None
    public["restrictions"] = "The access road is closed."
    assert usfs.qualification(facility, public, shapes)[1] == "contradictory_access_text"
    public["restrictions"] = None
    public["operational_hours"] += " Temporarily closed for repairs."
    assert usfs.qualification(facility, public, shapes)[1] == "contradictory_access_text"


def test_admitted_row_keeps_both_sources_access_qualifications(tmp_path, monkeypatch):
    class AdmissionTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 15, tzinfo=tz)

    monkeypatch.setattr(usfs, "datetime", AdmissionTime)
    facility, public, shapes = sources()
    facility.update(operational_hours="Seasonal hours; call the district.", restrictions=None)
    public.update(
        open_season_start="April 15",
        open_season_end="November 14",
        operational_hours="Open most weekends during summer; hours vary with volunteer availability.",
        restrictions="Vehicles (including trailers) longer than 22 feet are not recommended.",
        reservation_info="First-come, first-serve",
        accessibility="Accessible path",
    )

    def retain(name, value, url):
        raw = (json.dumps(value) + "\n").encode()
        (tmp_path / name).write_bytes(raw)
        return {
            "path": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "status": 200,
            "url": url,
        }

    origin = retain("facility.json", {"features": [{"attributes": facility}]}, usfs.FACILITY_URL)
    corroboration = retain("public.json", {"features": [{"attributes": public}]}, usfs.PUBLIC_URL)
    check = {**receipt(tmp_path), "site_cn": facility["site_cn"]}
    index = {
        "facilities": [origin],
        "public": [corroboration],
        "states": retain("states.json", {}, usfs.STATE_URL),
        "driving": retain("driving-index.json", [check], "https://router.project-osrm.org"),
        "rights": [],
    }
    inventory = retain("index.json", index, "https://www.fs.usda.gov")
    selection = [facility["site_cn"]]
    bundle = retain("bundle.json", {"index": inventory, "selection": selection}, usfs.SOURCE_URL)
    monkeypatch.setattr(usfs, "INDEX_SHA256", inventory["sha256"])
    monkeypatch.setattr(
        usfs,
        "SELECTION_SHA256",
        hashlib.sha256(json.dumps(selection, separators=(",", ":")).encode()).hexdigest(),
    )
    monkeypatch.setattr(usfs, "state_shapes", lambda _: shapes)
    manifest = {
        "source_url": usfs.SOURCE_URL,
        "release": usfs.RELEASE,
        "attribution": usfs.ATTRIBUTION,
        "sha256": bundle["sha256"],
    }
    rows, report = usfs.prepare(tmp_path / "bundle.json", manifest, max_rows=1, max_bytes=100_000)
    assert report["accepted"] == 1
    row = rows[0]
    facts = row["provenance"][0]["published_access_facts"]
    for label, source, evidence in (
        ("construction_feed", facility, origin),
        ("public_feed", public, corroboration),
    ):
        fact = facts[label]
        assert fact["source_url"] == evidence["url"]
        assert fact["snapshot_sha256"] == evidence["sha256"]
        assert fact["checked_at"] == evidence["retrieved_at"]
        assert all(value == source.get(key) for key, value in fact["fields"].items())
    assert facts["construction_feed"]["fields"]["restrictions"] is None
    assert facts["public_feed"]["fields"]["restrictions"] == public["restrictions"]
    assert facts["public_feed"]["fields"]["operational_hours"] == public["operational_hours"]
    assert facts["public_feed"]["fields"]["open_season_end"] == "November 14"
    assert row["provenance"][0]["opening_hours_imported"] is False
    assert not {"opening_hours", "opening_intervals", "price"}.intersection(row)
