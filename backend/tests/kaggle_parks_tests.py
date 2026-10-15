"""Synthetic fixtures exercise source, component, season and road admission vetoes."""

import copy
import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime

import pytest

from app.catalog import kaggle_parks as parks


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(parks, "now", lambda: datetime(2026, 10, 15, 18, tzinfo=UTC))
    source = dict.fromkeys(parks.COLUMNS, "")
    source.update(
        wikidata="Q123",
        nom_en="Fixture Park",
        type="amusement_park",
        pays="US",
        latitude="33.0",
        longitude="-118.0",
    )
    clock = "2026-10-15T12:00:00+00:00"

    def save_file(name, raw, url):
        (tmp_path / name).write_bytes(raw)
        return {"path": name, "sha256": digest(raw), "retrieved_at": clock, "url": url}

    operator = save_file(
        "operator.html",
        b"<body>Fixture Park open daily. Train closed for season.</body>",
        "https://example.org/park",
    )
    operator.update(
        required_facts=["Fixture Park open daily.", "Train closed for season."],
        restrictions=["Train closed for season; public visitor destination remains open."],
    )
    road = save_file(
        "road.json",
        json.dumps(
            {
                "code": "Ok",
                "routes": [{}],
                "waypoints": [
                    {"location": [-117.998, 33.002], "distance": 0},
                    {"location": [-118, 33], "distance": 25, "name": "Visitor Road"},
                ],
            }
        ).encode(),
        "https://router.project-osrm.org/route/v1/driving/-117.998,33.002;-118.0,33.0?overview=false&steps=false",
    )
    wiki = save_file(
        "wiki.json",
        json.dumps(
            {
                "entities": {
                    "Q123": {
                        "id": "Q123",
                        "lastrevid": 12345,
                        "claims": {
                            "P625": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {
                                                "latitude": 33,
                                                "longitude": -118,
                                                "globe": "http://www.wikidata.org/entity/Q2",
                                            }
                                        }
                                    }
                                }
                            ]
                        },
                    }
                }
            }
        ).encode(),
        "https://www.wikidata.org/wiki/Special:EntityData/Q123.json",
    )
    profile = {
        "qid": "Q123",
        "source_row": copy.deepcopy(source),
        "region": "CA",
        "primary_category": "entertainment",
        "categories": ["daytime", "amusement_park"],
        "address": "Synthetic visitor address",
        "public_url": "https://example.org/park",
        "access_rule": {"kind": "daily"},
        "pages": [operator],
        "driving": road,
        "wikidata": wiki,
        "parking": "unverified",
        "arrival_type": "native point; parking entrance unverified",
    }
    profile["arrival_review"] = {
        "method": "public-parking",
        "road_way_id": 100,
        "parking_way_id": 200,
        "building_way_id": None,
        "assessment": "Fixture point is in the documented guest lot.",
        "operator_map_evidence": [],
    }
    roads = save_file(
        "arrival-roads.json",
        json.dumps(
            {
                "elements": [
                    {
                        "id": 100,
                        "type": "way",
                        "tags": {"highway": "service", "service": "parking_aisle"},
                        "geometry": [{"lat": 33, "lon": -118.001}, {"lat": 33, "lon": -117.999}],
                    }
                ]
            }
        ).encode(),
        "https://example.org/roads",
    )
    features = save_file(
        "arrival-features.json",
        json.dumps(
            {
                "elements": [
                    {
                        "id": 200,
                        "type": "way",
                        "tags": {"amenity": "parking", "access": "yes"},
                        "geometry": [
                            {"lat": 32.999, "lon": -118.001},
                            {"lat": 32.999, "lon": -117.999},
                            {"lat": 33.001, "lon": -117.999},
                            {"lat": 33.001, "lon": -118.001},
                            {"lat": 32.999, "lon": -118.001},
                        ],
                    }
                ]
            }
        ).encode(),
        "https://example.org/features",
    )
    review = {
        "schema_version": "roadtrips-rideinpark-review/1",
        "source_url": parks.SOURCE_URL,
        "reviewed_at": clock,
        "records": [profile],
        "arrival_evidence": {"roads": roads, "features": features},
        "source_dispositions": [
            {"qid": "Q123", "disposition": "selected_current_visitor_evidence"},
            {"qid": "Q456", "disposition": "current_access_unknown"},
        ],
    }
    metadata = {
        "ref": "rideinpark/theme-parks-of-the-world",
        "currentVersionNumber": 1,
        "licenseName": "Attribution 4.0 International (CC BY 4.0)",
    }

    def publish(*, repin=True):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=parks.COLUMNS)
        writer.writeheader()
        writer.writerow(source)
        csv_raw = stream.getvalue().encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr(zipfile.ZipInfo("parcs-du-monde.csv"), csv_raw)
            archive.writestr(zipfile.ZipInfo("parcs-du-monde.json"), b"[]")
        archive_raw, metadata_raw, review_raw = (
            output.getvalue(),
            json.dumps(metadata).encode(),
            json.dumps(review).encode(),
        )
        bundle = {
            "archive": save_file("archive.zip", archive_raw, parks.SOURCE_URL),
            "metadata": save_file("metadata.json", metadata_raw, parks.SOURCE_URL),
            "review": save_file("review.json", review_raw, parks.SOURCE_URL),
        }
        for value in bundle.values():
            value["path"] = str(tmp_path / value["path"])
        if repin:
            for name, value in {
                "ARCHIVE_SHA256": digest(archive_raw),
                "CSV_SHA256": digest(csv_raw),
                "METADATA_SHA256": digest(metadata_raw),
                "REVIEW_SHA256": digest(review_raw),
                "CSV_ROWS": 1,
            }.items():
                monkeypatch.setattr(parks, name, value)
        raw = json.dumps(bundle).encode()
        path = tmp_path / "bundle.json"
        path.write_bytes(raw)
        manifest = {
            "schema_version": parks.SCHEMA,
            "source_url": parks.SOURCE_URL,
            "attribution": parks.ATTRIBUTION,
            "release": "kaggle-rideinpark-v1+review-2026-10-15",
            "retrieved_at": clock,
            "sha256": digest(raw),
            "licenses": {"CC-BY-4.0": {}, "CC0-1.0": {}, "ODbL-1.0": {}},
        }
        return path, manifest

    publish()
    return tmp_path, source, profile, review, metadata, publish


def admit(sample):
    path, manifest = sample[-1]()
    return parks.prepare(path, manifest, max_rows=10, max_bytes=1_000_000)


def mutate_receipt(sample, key, mutation):
    directory, _, profile, _, _, _ = sample
    receipt = profile[key]
    path = directory / receipt["path"]
    data = json.loads(path.read_bytes())
    mutation(data)
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    receipt["sha256"] = digest(raw)


def test_native_point_closed_component_and_explicit_unknowns_survive(sample):
    rows, report = admit(sample)
    row = rows[0]
    assert (row["source_id"], row["latitude"], row["longitude"]) == ("wikidata-park:Q123", 33, -118)
    access = row["provenance"][2]
    assert access["parking"] == "unverified"
    assert access["opening_intervals"] is None and access["prices_imported"] is False
    assert "Train closed" in access["source_facts"][0]["restrictions"][0]
    assert row["source_updated_at"] is None
    assert report["rejects"] == {"current_access_unknown": 1}


@pytest.mark.parametrize("property_name", ["P576", "P3999"])
def test_current_negative_feed_vetoes_blank_source_closure(sample, property_name):
    mutate_receipt(
        sample,
        "wikidata",
        lambda data: data["entities"]["Q123"]["claims"].update({property_name: [{}]}),
    )
    with pytest.raises(ValueError, match="closure"):
        admit(sample)


def test_source_closure_vetoes_positive_operator_page(sample):
    sample[1]["annee_fermeture"] = "2025"
    sample[2]["source_row"]["annee_fermeture"] = "2025"
    with pytest.raises(ValueError, match="closure"):
        admit(sample)


@pytest.mark.parametrize(
    "field,value",
    [("latitude", "34"), ("longitude", "-119"), ("pays", "CA"), ("nom_en", "Other Park")],
)
def test_native_source_facts_cannot_be_replaced(sample, field, value):
    sample[1][field] = value
    with pytest.raises(ValueError, match="native source"):
        admit(sample)


@pytest.mark.parametrize("distance", [75.01, True, float("nan"), -1])
def test_invalid_raw_driving_distance_is_rejected(sample, distance):
    mutate_receipt(sample, "driving", lambda data: data["waypoints"][-1].update(distance=distance))
    with pytest.raises(ValueError, match="destination"):
        admit(sample)


@pytest.mark.parametrize("key,value", [("code", "NoRoute"), ("routes", []), ("waypoints", [{}])])
def test_incomplete_raw_driving_response_is_rejected(sample, key, value):
    mutate_receipt(sample, "driving", lambda data: data.update({key: value}))
    with pytest.raises(ValueError, match="destination"):
        admit(sample)


def test_query_cannot_use_replacement_arrival_point(sample):
    sample[2]["driving"]["url"] = sample[2]["driving"]["url"].replace(
        ";-118.0,33.0", ";-118.01,33.0"
    )
    with pytest.raises(ValueError, match="unchanged native"):
        admit(sample)


def test_changed_operator_original_is_not_cleared_by_a_summary(sample):
    (sample[0] / "operator.html").write_bytes(b"Fixture Park permanently closed")
    with pytest.raises(ValueError, match="checksum"):
        admit(sample)


def test_http_success_without_positive_fact_is_insufficient(sample):
    sample[2]["pages"][0]["required_facts"].append("Invented positive fact")
    with pytest.raises(ValueError, match="positive identity/access"):
        admit(sample)


def test_independent_selection_fingerprint_cannot_change(sample):
    sample[2]["parking"] = "invented parking"
    path, manifest = sample[-1](repin=False)
    with pytest.raises(ValueError, match="review fingerprint"):
        parks.prepare(path, manifest, max_rows=10, max_bytes=1_000_000)


@pytest.mark.parametrize(
    "rule",
    [
        {"kind": "snapshot-day", "date": "2026-10-14"},
        {"kind": "weekdays", "days": [0, 1, 2]},
        {"kind": "date-range", "start": "2026-05-01", "end": "2026-09-30"},
        {"kind": "belmont-calendar"},
    ],
)
def test_unknown_day_or_closed_season_fails_admission_clock(sample, rule):
    sample[2]["access_rule"] = rule
    with pytest.raises(ValueError, match="current day/season"):
        admit(sample)


@pytest.mark.parametrize(
    "timestamp", ["2026-09-14T12:00:00+00:00", "2026-10-16T12:00:00+00:00", "2026-10-15T12:00:00"]
)
def test_stale_future_and_naive_evidence_is_rejected(sample, timestamp):
    sample[2]["pages"][0]["retrieved_at"] = timestamp
    with pytest.raises(ValueError, match="within 30 days"):
        admit(sample)


def test_upstream_coordinate_mismatch_cannot_be_replaced_with_road_point(sample):
    mutate_receipt(
        sample,
        "wikidata",
        lambda data: data["entities"]["Q123"]["claims"]["P625"][0]["mainsnak"]["datavalue"][
            "value"
        ].update(latitude=33.01),
    )
    with pytest.raises(ValueError, match="structured upstream"):
        admit(sample)


def test_review_paths_cannot_escape_portable_source_root(sample):
    sample[2]["pages"][0]["path"] = "../operator.html"
    with pytest.raises(ValueError, match="portable relative"):
        admit(sample)


def test_actual_aggregate_byte_limit_is_enforced(sample):
    path, manifest = sample[-1]()
    with pytest.raises(ValueError, match="aggregate evidence"):
        parks.prepare(path, manifest, max_rows=10, max_bytes=1)


def mutate_arrival_source(sample, key, mutation):
    directory, _, _, review, _, _ = sample
    receipt = review["arrival_evidence"][key]
    path = directory / receipt["path"]
    data = json.loads(path.read_bytes())
    mutation(data["elements"][0])
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    receipt["sha256"] = digest(raw)


@pytest.mark.parametrize(
    "tags",
    [
        {"access": "private"},
        {"motor_vehicle": "no"},
        {"highway": "footway"},
        {"highway": "raceway"},
        {"layer": "-1"},
    ],
)
def test_real_car_snap_does_not_admit_private_or_internal_road(sample, tags):
    mutate_arrival_source(sample, "roads", lambda way: way["tags"].update(tags))
    with pytest.raises(ValueError, match="private, internal-only or unsuitable"):
        admit(sample)


def test_guest_parking_is_a_required_independent_source(sample):
    mutate_arrival_source(sample, "features", lambda way: way["tags"].update(access="private"))
    with pytest.raises(ValueError, match="reviewed guest parking"):
        admit(sample)


def test_native_point_must_be_inside_selected_public_parking(sample):
    def move(way):
        for point in way["geometry"]:
            point["lon"] += 0.0015

    mutate_arrival_source(sample, "features", move)
    with pytest.raises(ValueError, match="outside the reviewed public"):
        admit(sample)


def test_named_public_street_cannot_be_substituted_with_service_lane(sample):
    sample[2]["arrival_review"]["method"] = "public-street-frontage"
    with pytest.raises(ValueError, match="unnamed internal service"):
        admit(sample)


def test_arrival_geometry_must_match_actual_raw_destination_road(sample):
    def move(way):
        for point in way["geometry"]:
            point["lat"] += 0.0001

    mutate_arrival_source(sample, "roads", move)
    with pytest.raises(ValueError, match="actual snapped destination road"):
        admit(sample)


def test_successful_point_retains_practical_arrival_method(sample):
    rows, _ = admit(sample)
    proof = rows[0]["provenance"][2]["practical_arrival"]
    assert proof["method"] == "public-parking"
    assert proof["coordinate_replaced"] is False


@pytest.mark.parametrize("license_id", ["CC-BY-4.0", "CC0-1.0", "ODbL-1.0"])
def test_each_source_license_is_required(sample, license_id):
    path, manifest = sample[-1]()
    manifest["licenses"].pop(license_id)
    with pytest.raises(ValueError, match="source/rights/bounds"):
        parks.prepare(path, manifest, max_rows=10, max_bytes=1_000_000)


def test_selected_osm_identities_and_original_receipts_travel_with_provenance(sample):
    rows, _ = admit(sample)
    proof = rows[0]["provenance"][4]
    assert proof["license"] == "ODbL-1.0"
    assert proof["attribution"] == "OpenStreetMap contributors"
    assert [(e["type"], e["id"]) for e in proof["elements"]] == [("way", 100), ("way", 200)]
    assert proof["elements"][0]["source_url"] == "https://www.openstreetmap.org/way/100"
    for key in ("roads", "features"):
        original = sample[3]["arrival_evidence"][key]
        receipt = proof["source_snapshots"][key]
        assert receipt["source_url"] == original["url"]
        assert receipt["snapshot_sha256"] == original["sha256"]
        assert receipt["checked_at"] == original["retrieved_at"]
