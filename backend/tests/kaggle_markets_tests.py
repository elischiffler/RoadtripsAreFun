"""Market admission regressions: season conflicts, native points, and raw proof."""

import copy
import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from app.catalog import kaggle_markets as markets


def source_rows():
    native = {key: "" for key in markets.FIELDS}
    native.update(
        listing_id="123",
        name="Example Certified Farmers' Market",
        street="123 Main St",
        city="Example",
        state="CA",
        lat="34.123",
        lng="-118.123",
        season="Year Round (Sunday)",
        updated="Mar 20th, 2023",
        zip="90000",
    )
    official = {
        "name": "Example Farmers' Market",
        "location": "123 Main Street, Example, CA 90000",
        "days": "Sun",
        "hours": "9am - 1pm",
        "months": "Year\nRound",
        "region": "CA",
        "receipt_key": "cdfa",
    }
    return native, copy.deepcopy(native), [official]


def test_native_point_and_daytime_market_contract():
    row, reason = markets.qualification(*source_rows(), as_of=date(2026, 10, 15))
    assert reason is None
    assert row["source_id"] == "usda-market:123"
    assert (row["latitude"], row["longitude"]) == (34.123, -118.123)
    assert {"farmers_market", "food_destination", "daytime"} <= set(row["categories"])
    assert not {"food", "nightlife"} & set(row["categories"])
    assert row["source_updated_at"] is None
    assert not {"price", "rating", "opening_hours", "opening_intervals"} & row.keys()


@pytest.mark.parametrize("label", ["kaggle", "canonical", "official"])
def test_every_feed_participates_in_season_conflicts(label):
    native, current, officials = source_rows()
    if label == "kaggle":
        native["season"] = "May to September"
    elif label == "canonical":
        current["season"] = "May to September"
    else:
        officials[0]["months"] = "Apr 1 - Oct 7"
    row, reason = markets.qualification(native, current, officials, as_of=date(2026, 10, 15))
    assert row is None and reason.startswith(label + "_season")


@pytest.mark.parametrize(
    "value,day,expected",
    [
        ("May to October", date(2026, 10, 31), "in_interval"),
        ("May to October", date(2026, 11, 1), "out_interval"),
        ("Apr 1 - Oct 7", date(2026, 10, 7), "in_interval"),
        ("Apr 1 - Oct 7", date(2026, 10, 8), "out_interval"),
        ("December 1 through March 31", date(2026, 1, 1), "in_interval"),
        ("December 1 through March 31", date(2026, 10, 15), "out_interval"),
        ("Feb 30 - Oct 31", date(2026, 10, 15), "review_invalid_date"),
        ("June 2021 to October 2021", date(2026, 10, 15), "review_explicit_year"),
        ("May to mid October", date(2026, 10, 15), "review_complex_separator"),
        ("Year round; June to September", date(2026, 10, 15), "review_qualified_year_round"),
        ("Year Round (Sunday)", date(2026, 10, 15), "in_year_round"),
        ("Year-round except Christmas", date(2026, 10, 15), "review_qualified_year_round"),
        ("winter only", date(2026, 10, 15), "review_descriptive_season"),
        ("", date(2026, 10, 15), "unknown_blank"),
        ("Sundays 9am-1pm", date(2026, 10, 15), "unknown_no_months"),
    ],
)
def test_conservative_seasons_boundaries_and_unknowns(value, day, expected):
    assert markets.season(value, day) == expected


def test_unknown_source_season_requires_positive_official_roster():
    native, current, officials = source_rows()
    native["season"] = current["season"] = ""
    assert markets.qualification(native, current, officials, as_of=date(2026, 10, 15))[1] is None
    officials[0]["months"] = ""
    assert markets.qualification(native, current, officials, as_of=date(2026, 10, 15))[0] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("lat", "nan"),
        ("lng", "inf"),
        ("lat", "91"),
        ("street", "456 Main St"),
        ("city", "Different"),
        ("name", "Different market"),
    ],
)
def test_unresolved_native_points_identity_and_moved_locations_are_held(field, value):
    native, current, officials = source_rows()
    current[field] = value
    assert markets.qualification(native, current, officials)[0] is None
    native[field] = value
    assert markets.qualification(native, current, officials)[0] is None


@pytest.mark.parametrize(
    "street,city,published",
    [
        ("514 N Hwy 3", "Etna", "514 N Hwy 3, Etna CA 96027"),
        ("765 Portola Rd", "Portola Valley", "765 Portola Road, Portola Valley, 94028"),
        ("8920 East Rd", "Redwood Valley", "8920 East Road, Redwood Valley, CA 95470"),
        ("12345 Main St", "Example", "12345 Main Street, Example, CA 90000"),
    ],
)
def test_exact_street_subset_before_city_removal(street, city, published):
    assert markets.location_matches({"street": street, "city": city}, {"location": published})


@pytest.mark.parametrize(
    "native,published",
    [
        ("123 Main St", "456 Main St, Example, CA"),
        ("123 Main St", "123 Other St, Example, CA"),
        ("123 Main St", "123 Main St, Elsewhere, CA"),
        ("Main St", "123 Main St, Example, CA"),
    ],
)
def test_changed_numbers_or_missing_literal_city_and_street_evidence_fail(native, published):
    assert not markets.location_matches(
        {"street": native, "city": "Example"}, {"location": published}
    )


def test_disjoint_weekday_and_distinct_current_locations_are_not_merged():
    native, current, officials = source_rows()
    officials[0]["days"] = "Sat"
    assert markets.qualification(native, current, officials)[0] is None
    officials[0]["days"] = "Sun"
    other = {**officials[0], "location": "123 Main St, Example, CA"}
    assert (
        markets.qualification(native, current, officials + [other])[1]
        == "multiple_official_locations"
    )


def test_current_year_precise_official_dates_cannot_be_reused_in_a_later_year():
    native, current, officials = source_rows()
    native["state"] = current["state"] = officials[0]["region"] = "CT"
    officials[0].update(start_date="12-May", end_date="17-Nov")
    assert markets.qualification(native, current, officials, as_of=date(2026, 10, 15))[1] is None
    assert markets.qualification(native, current, officials, as_of=date(2027, 10, 15))[0] is None


def receipt(tmp_path, *, distance=5, code="Ok"):
    raw = json.dumps(
        {
            "code": code,
            "waypoints": [
                {"distance": 0, "name": "origin"},
                {"distance": distance, "name": "Main Street"},
            ],
        }
    ).encode()
    (tmp_path / "route.json").write_bytes(raw)
    return {
        "path": "route.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "status": 200,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "checked_waypoint": "destination",
        "source_coordinates": [34.123, -118.123],
        "road_name": "Main Street",
        "snap_distance_m": distance,
        "url": f"https://router.project-osrm.org/route/v1/driving/-118.123,{34.123 + 0.01};-118.123,34.123?overview=false&steps=false&alternatives=false",
    }


def test_actual_destination_receipt_and_native_query_are_required(tmp_path):
    entry = receipt(tmp_path)
    row = {"latitude": 34.123, "longitude": -118.123}
    assert markets.driving(tmp_path, entry, row)[1] == 5
    for changed in [
        {**entry, "checked_waypoint": "origin"},
        {**entry, "source_coordinates": [34.124, -118.123]},
        {**entry, "road_name": "invented road"},
        {**entry, "url": entry["url"].replace(str(34.123 + 0.01), "34.134")},
    ]:
        with pytest.raises(ValueError):
            markets.driving(tmp_path, changed, row)
    with pytest.raises(ValueError, match="75 metres"):
        markets.driving(tmp_path, receipt(tmp_path, distance=76), row)
    with pytest.raises(ValueError, match="successful"):
        markets.driving(tmp_path, receipt(tmp_path, code="NoSegment"), row)


def test_receipt_staleness_checksum_escape_and_status_fail(tmp_path):
    entry = receipt(tmp_path)
    for changed in [
        {**entry, "path": "../route.json"},
        {**entry, "sha256": "0" * 64},
        {**entry, "status": 403},
        {**entry, "retrieved_at": (datetime.now(UTC) - timedelta(days=31)).isoformat()},
    ]:
        with pytest.raises(ValueError):
            markets.retained(tmp_path, changed)


def test_preparation_keeps_separate_attribution_and_unknowns_without_private_fields(
    tmp_path, monkeypatch
):
    native, current, officials = source_rows()
    native.update(phone="private manager phone", description="creative description")
    current.update(updated="Jul 20th, 2020", season="Year Round (Sunday)")
    check = {**receipt(tmp_path), "listing_id": "123"}
    source_receipt = {
        "url": markets.SOURCE_URL,
        "sha256": "a" * 64,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }
    canonical_receipt = {
        **source_receipt,
        "url": "https://harvestlymarkets.com/data/us-farmers-markets-2026.csv",
        "sha256": "b" * 64,
    }
    official_receipt = {
        **source_receipt,
        "url": "https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf",
        "sha256": "c" * 64,
    }
    index = {
        "census": {
            "response": {
                "sha256": "d" * 64,
                "request_sha256": "e" * 64,
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
        },
        "selection": ["123"],
        "driving": [check],
        "archive": source_receipt,
        "canonical": canonical_receipt,
        "cdfa": official_receipt,
    }
    inventory = json.dumps(index).encode()
    (tmp_path / "index.json").write_bytes(inventory)
    inventory_hash = hashlib.sha256(inventory).hexdigest()
    monkeypatch.setattr(markets, "INDEX_SHA256", inventory_hash)
    monkeypatch.setattr(
        markets, "load_sources", lambda *_: ({"123": native}, {"123": current}, officials, {}, 1)
    )
    monkeypatch.setattr(markets, "targeted_records", lambda _: {})
    monkeypatch.setattr(markets, "load_census", lambda *_: (census_example(native), 0))
    bundle = {
        "selection": ["123"],
        "index": {
            "path": "index.json",
            "sha256": inventory_hash,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "status": 200,
        },
    }
    raw = json.dumps(bundle).encode()
    path = tmp_path / "bundle.json"
    path.write_bytes(raw)
    manifest = {
        "source_url": markets.SOURCE_URL,
        "release": markets.RELEASE,
        "attribution": markets.ATTRIBUTION,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "licenses": {"CC-BY-4.0": {}, "LicenseRef-US-Census-Geocoder": {}},
    }
    rows, report = markets.prepare(path, manifest, max_rows=1, max_bytes=100000)
    assert report["accepted"] == 1
    row = rows[0]
    provenance = row["provenance"][0]
    facts = provenance["published_access_facts"]
    assert facts[0]["fields"]["source_updated_at_raw"] == "Mar 20th, 2023"
    assert facts[1]["fields"]["source_updated_at_raw"] == "Jul 20th, 2020"
    assert facts[2]["fields"]["hours"] == "9am - 1pm"
    assert [fact["snapshot_sha256"] for fact in facts] == ["a" * 64, "b" * 64, "c" * 64]
    assert provenance["parking"] is None and provenance["opening_hours_imported"] is False
    assert row["source_updated_at"] is None
    assert "private manager phone" not in json.dumps(row)
    assert "creative description" not in json.dumps(row)
    assert not {"opening_intervals", "opening_hours", "price", "rating"} & row.keys()
    assert row["url"] == official_receipt["url"]
    with pytest.raises(ValueError, match="byte ceiling"):
        markets.prepare(path, manifest, max_rows=1, max_bytes=1)
    with pytest.raises(ValueError, match="selection"):
        markets.prepare(path, manifest, max_rows=0, max_bytes=100000)
    with pytest.raises(ValueError, match="license"):
        markets.prepare(path, {**manifest, "licenses": {}}, max_rows=1, max_bytes=100000)


def census_example(native=None, *, role="native_kaggle", distance_lat=0, status="Match"):
    native = native or source_rows()[0]
    query = {
        "query_id": ("native-" if role == "native_kaggle" else "official-") + native["listing_id"],
        "listing_id": native["listing_id"],
        "address_role": role,
        **{key: native[key] for key in ("street", "city", "state", "zip")},
    }
    result = {"query": query, "status": status}
    if status == "Match":
        result.update(
            match_type="Exact",
            matched_address="123 MAIN ST, EXAMPLE, CA, 90000",
            matched_street="123 MAIN ST",
            matched_city=native["city"].upper(),
            matched_state=native["state"],
            matched_zip=native["zip"][:5],
            coordinates=[float(native["lat"]) + distance_lat, float(native["lng"])],
            tiger_line_id="123456",
            tiger_line_side="L",
        )
    return {query["query_id"]: result}


def test_census_corroborates_without_changing_native_point_or_unknowns():
    native, _, official = source_rows()
    results = census_example(native, distance_lat=0.0001)
    facts, reason = markets.census_qualification(native, official, results)
    assert reason is None
    assert 10 < facts[0]["native_point_distance_m"] < 12
    assert facts[0]["coordinates"] != [float(native["lat"]), float(native["lng"])]
    assert native["lat"] == "34.123" and native["lng"] == "-118.123"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("matched_city", "OTHER", "census_matched_city_state_zip_disagreement"),
        ("matched_state", "NV", "census_matched_city_state_zip_disagreement"),
        ("matched_zip", "90001", "census_matched_city_state_zip_disagreement"),
        ("matched_street", "456 OTHER ST", "census_no_unambiguous_literal_address_match"),
        ("coordinates", [34.125, -118.123], "census_native_point_more_than_100m_away"),
    ],
)
def test_census_disagreement_is_not_overridden_by_roster_or_road_snap(field, value, reason):
    native, _, official = source_rows()
    results = census_example(native)
    next(iter(results.values()))[field] = value
    assert markets.census_qualification(native, official, results) == (None, reason)


@pytest.mark.parametrize("status", ["No_Match", "Tie"])
def test_unknown_census_form_needs_an_independent_published_positive_form(status):
    native, _, official = source_rows()
    results = census_example(native, status=status)
    assert markets.census_qualification(native, official, results)[0] is None
    results.update(census_example(native, role="official_roster"))
    facts, reason = markets.census_qualification(native, official, results)
    assert reason is None
    assert {fact["status"] for fact in facts} == {"Match", status}


def test_all_successful_census_forms_participate_without_cherry_picking():
    native, _, official = source_rows()
    results = census_example(native)
    results.update(census_example(native, role="official_roster", distance_lat=0.002))
    assert (
        markets.census_qualification(native, official, results)[1]
        == "census_native_point_more_than_100m_away"
    )


def test_native_and_published_zip_conflict_remains_a_hold():
    native, _, official = source_rows()
    official[0]["location"] = "123 Main St, Example, CA 90001"
    assert (
        markets.census_qualification(native, official, census_example(native))[1]
        == "official_native_zip_conflict"
    )
    native["zip"] = ""
    assert (
        markets.census_qualification(native, official, census_example(native))[1]
        == "census_native_zip_unknown"
    )


@pytest.mark.parametrize("ident", ["301303", "301314", "308615", "308803"])
def test_independently_identified_wrong_points_and_shared_arrivals_stay_held(ident):
    native, _, official = source_rows()
    native["listing_id"] = ident
    assert markets.census_qualification(native, official, census_example(native))[1].startswith(
        "review_hold:"
    )


def test_same_and_nearby_unreviewed_market_points_cannot_inflate_destinations():
    row = {"source_id": "usda-market:1", "latitude": 34, "longitude": -118}
    for offset in [0, 0.001]:
        with pytest.raises(ValueError, match="collision"):
            markets.reject_collisions(
                [row, {**row, "source_id": "usda-market:2", "latitude": 34 + offset}]
            )
    markets.reject_collisions([row, {**row, "source_id": "usda-market:2", "latitude": 34.01}])


def census_batch():
    import csv
    import io

    result = next(iter(census_example().values()))
    query = result["query"]
    request = io.StringIO(newline="")
    csv.writer(request, lineterminator="\r\n").writerow(
        [query[key] for key in ("query_id", "street", "city", "state", "zip")]
    )
    response = io.StringIO(newline="")
    csv.writer(response).writerow(
        [
            query["query_id"],
            ", ".join(query[key] for key in ("street", "city", "state", "zip")),
            "Match",
            "Exact",
            "123 MAIN ST, EXAMPLE, CA, 90000",
            "-118.123,34.123",
            "123456",
            "L",
        ]
    )
    document = {"benchmark": "8", "benchmark_name": "Public_AR_ACS2026", "queries": [query]}
    return request.getvalue().encode(), response.getvalue().encode(), document


def test_batch_geocoder_binds_actual_response_to_exact_request_and_benchmark():
    request, response, document = census_batch()
    actual = markets.parse_census(request, response, document)
    assert actual["native-123"]["coordinates"] == [34.123, -118.123]
    for changed in [
        response.replace(b"native-123", b"native-999"),
        response + response,
        b"",
        response.replace(b"-118.123,34.123", b"nan,34.123"),
        response.replace(b"123 Main St", b"456 Other St"),
    ]:
        with pytest.raises(ValueError):
            markets.parse_census(request, changed, document)
    with pytest.raises(ValueError, match="benchmark"):
        markets.parse_census(request, response, {**document, "benchmark": "4"})
    with pytest.raises(ValueError, match="request CSV"):
        markets.parse_census(request.replace(b"123 Main St", b"456 Other St"), response, document)


@pytest.mark.parametrize(
    "points",
    [
        [(0, 179.9995), (0, -179.9995)],
        [(89.9995, 0), (89.9995, 180)],
        [(-89.9995, -90), (-89.9995, 90)],
    ],
)
def test_market_collision_grid_preserves_polar_and_antimeridian_neighbors(points):
    rows = [
        {"source_id": f"usda-market:{number}", "latitude": point[0], "longitude": point[1]}
        for number, point in enumerate(points)
    ]
    with pytest.raises(ValueError, match="collision"):
        markets.reject_collisions(rows)


def test_market_collision_grid_avoids_unbounded_all_pairs(monkeypatch):
    rows = [
        {"source_id": f"usda-market:{number}", "latitude": -60 + number * 0.01, "longitude": 0}
        for number in range(10000)
    ]
    calls = 0
    original = markets.point_distance

    def measured(a, b):
        nonlocal calls
        calls += 1
        return original(a, b)

    monkeypatch.setattr(markets, "point_distance", measured)
    markets.reject_collisions(rows)
    assert calls < 10000
