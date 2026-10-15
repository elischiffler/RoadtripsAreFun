"""Source admission boundaries, native-point fidelity and raw-receipt checks."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta

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
