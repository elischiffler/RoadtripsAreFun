"""NY source admission: authentic factual cases, coordinate/season/arrival negatives."""

import copy
import hashlib
import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.catalog import kaggle_ny_markets as ny
from app.catalog import market_visit_calendar
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


def originals():
    # Factual fields from the genuine Kaggle v4 and NY official row 144 snapshots.
    native = {
        "listing_id": "300016",
        "name": "Clarence Hollow Farmers' Market",
        "street": "10717 Main St.",
        "city": "Clarence",
        "state": "NY",
        "zip": "14031",
        "lat": "42.98032",
        "lng": "-78.58945",
        "season": "June to October",
        "updated": "Aug 3rd, 2020",
    }
    official = {
        "market_name": "Clarence Hollow Farmers' Market",
        "address_line_1": "10717 Main St",
        "market_location": "Town lot btwn Ransom & Salt Rds, 10717 Main St",
        "city": "Clarence",
        "state": "NY",
        "zip": "14031",
        "operation_hours": "Sat 8am-1pm",
        "operation_season": "June 6-October 31",
        "latitude": "42.9808",
        "longitude": "-78.58904",
        "georeference_1": {"type": "Point", "coordinates": [-78.58904, 42.9808]},
    }
    receipts = {
        key: {"url": url, "sha256": digest, "retrieved_at": "2026-10-15T19:51:52.340529+00:00"}
        for key, url, digest in [
            ("archive", ny.SOURCE_URL, ny.markets.ARCHIVE_SHA256),
            (
                "canonical",
                "https://harvestlymarkets.com/data/us-farmers-markets-2026.csv",
                ny.markets.CANONICAL_SHA256,
            ),
            ("ny", ny.NY_URL, ny.NY_SHA256),
        ]
    }
    return native, copy.deepcopy(native), official, receipts


def qualify(native=None, canonical=None, official=None):
    n, c, o, receipts = originals()
    return ny.qualification(
        native or n,
        canonical or c,
        ny.roster_index([official or o]),
        receipts,
        as_of=date(2026, 10, 15),
    )


def test_authentic_clarence_native_point_and_all_source_calendar_remain_intact():
    n, _, o, _ = originals()
    row, reason = qualify()
    assert reason is None
    assert (row["latitude"], row["longitude"]) == (float(n["lat"]), float(n["lng"]))
    assert (row["latitude"], row["longitude"]) != (float(o["latitude"]), float(o["longitude"]))
    assert 60 < row["agency_native_point_distance_m"] < 65
    assert row["source_id"] == "usda-market:300016"
    assert "food_destination" in row["categories"] and "food" not in row["categories"]
    assert row["source_updated_at"] is None
    assert row["fact_groups"][0]["fields"]["source_updated_at_raw"] == "Aug 3rd, 2020"
    assert row["unbounded_calendar_research"]["weekly_windows"] == [
        {"weekdays": [5], "opens": "08:00", "closes": "13:00", "end_day_offset": 0}
    ]


def test_point_agreement_does_not_override_zip_conflict():
    n, c, o, _ = originals()
    o["zip"] = "14032"
    assert qualify(n, c, o)[1] == "native_canonical_official_zip_conflict"


def test_exact_same_address_does_not_excuse_distant_independent_point():
    n, c, o, _ = originals()
    o["latitude"] = "42.99"
    o["georeference_1"]["coordinates"][1] = 42.99
    assert qualify(n, c, o)[1] == "native_point_more_than_100m_from_independent_agency_point"


def test_every_native_and_canonical_season_participates():
    n, c, o, _ = originals()
    n["season"] = "June to September"
    assert qualify(n, c, o)[1] == "outside_all_source_season_intersection"
    n["season"], c["season"] = "June to October", "June to September"
    assert qualify(n, c, o)[1] == "outside_all_source_season_intersection"


def test_changed_native_coordinate_or_ambiguous_official_identity_stays_held():
    n, c, o, r = originals()
    c["lat"] = "42.98033"
    assert qualify(n, c, o)[1] == "canonical_identity_or_native_coordinates_changed"
    row, reason = ny.qualification(n, n, ny.roster_index([o, o]), r, as_of=date(2026, 10, 15))
    assert row is None and reason == "no_unique_exact_normalized_market_name_and_city"


@pytest.mark.parametrize("bad", ["10718 Main St", "10717 East Main St", "Main St", "10717 Main"])
def test_complete_numbered_street_preserves_every_qualifier(bad):
    assert not ny.exact_numbered_street("10717 Main St.", bad)


def test_agency_lat_lon_and_geometry_must_agree():
    n, c, o, _ = originals()
    o["georeference_1"]["coordinates"] = [-78, 42]
    assert qualify(n, c, o)[1] == "invalid_or_conflicting_independent_agency_coordinates"


def test_unpublished_or_ambiguous_hours_cannot_create_positive_calendar():
    n, c, o, _ = originals()
    o["operation_hours"] = "Sat 8-1"
    assert qualify(n, c, o)[1].startswith("unresolved_all_source_calendar:")


def test_dated_expansion_retains_weekday_season_and_full_dwell():
    row, _ = qualify()
    cal = ny.bounded_calendar(
        row["unbounded_calendar_research"], date(2026, 10, 15), date(2026, 11, 13)
    )
    assert [x["date"] for x in cal["date_overrides"]] == ["2026-10-17", "2026-10-24", "2026-10-31"]
    assert cal["weekly_windows"] == cal["seasons"] == []
    rec = {
        "provider_id": row["source_id"],
        "categories": row["categories"],
        "source_provenance": [{"source_visit_calendar": cal}],
    }
    zone = ZoneInfo("America/New_York")
    start, proof = solve_visit(
        rec, datetime(2026, 10, 17, 11, tzinfo=zone), datetime(2026, 10, 17, 16, tzinfo=zone)
    )
    assert start.hour == 11 and proof["visit_end"].startswith("2026-10-17T13:00")
    for day, hour in [(17, 12), (18, 8)]:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(
                rec,
                datetime(2026, 10, day, hour, tzinfo=zone),
                datetime(2026, 10, day, 16, tzinfo=zone),
            )


def test_unknown_source_season_or_scope_longer_than_thirty_days_rejected():
    empty = market_visit_calendar.build([])
    with pytest.raises(ValueError, match="unresolved"):
        ny.bounded_calendar(empty, date(2026, 10, 15), date(2026, 11, 13))
    row, _ = qualify()
    with pytest.raises(ValueError, match="thirty"):
        ny.bounded_calendar(
            row["unbounded_calendar_research"], date(2026, 10, 15), date(2026, 11, 14)
        )


def test_destination_snap_is_checked_even_when_origin_is_close(tmp_path):
    row, _ = qualify()
    lat, lon = row["latitude"], row["longitude"]
    raw = json.dumps(
        {
            "code": "Ok",
            "waypoints": [
                {"distance": 1, "name": "Origin"},
                {"distance": 76, "name": "Destination"},
            ],
        }
    ).encode()
    (tmp_path / "road.json").write_bytes(raw)
    receipt = {
        "url": f"https://router.project-osrm.org/route/v1/driving/{lon},{lat + 0.01};{lon},{lat}?overview=false&steps=false",
        "path": "road.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "status": 200,
        "bytes": len(raw),
        "checked_waypoint": "destination",
        "source_coordinates": [lat, lon],
        "snap_distance_m": 76,
        "road_name": "Destination",
    }
    with pytest.raises(ValueError, match="75 metres"):
        ny.markets.driving(tmp_path, receipt, row)


def test_full_parent_and_source_collisions_are_both_held_across_antimeridian():
    a = {"source_id": "usda-market:a", "latitude": 70, "longitude": 179.999}
    b = {"source_id": "usda-market:b", "latitude": 70, "longitude": -179.999}
    held = ny.collision_holds([a, b], [])
    assert set(held) == {a["source_id"], b["source_id"]}
    held = ny.collision_holds([a], [b])
    assert held == {a["source_id"]: [b["source_id"]]}


def test_unreviewed_normalized_json_cannot_bypass_typed_source_replay(tmp_path):
    path = tmp_path / "places.json"
    path.write_text('[{"name":"Unverified"}]')
    with pytest.raises(ValueError, match="exact reviewed"):
        ny.prepare(path, {})


def test_local_parent_receipt_has_no_invented_http_response_and_rejects_mutation(tmp_path):
    raw = b"{}"
    (tmp_path / "parent.bin").write_bytes(raw)
    receipt = {
        "kind": "retained-local-artifact",
        "path": "parent.bin",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "checked_at": datetime.now(UTC).isoformat(),
    }
    assert ny._retained(tmp_path, receipt) == raw
    (tmp_path / "parent.bin").write_bytes(b"[]")
    with pytest.raises(ValueError, match="checksum"):
        ny._retained(tmp_path, receipt)


def test_official_visitor_location_cannot_be_ignored_for_convenient_address_field():
    n, c, o, _ = originals()
    o["market_location"] = "Sanford Ave & Union St, Bowne Playground"
    assert qualify(n, c, o)[1] == "official_visitor_location_conflicts_with_native_street"
