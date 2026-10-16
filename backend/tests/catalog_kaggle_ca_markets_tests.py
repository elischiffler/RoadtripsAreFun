"""Alternative-address source admission keeps unknown native fields and fails closed."""

import copy
import hashlib
import importlib
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.catalog import kaggle_ca_markets as ca
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


def originals():
    # Exact factual fragments from pinned Kaggle v4, CDFA PDF page 3 row 10,
    # and the genuine official-address Census response (no contact columns).
    native = {
        "listing_id": "cas-m-3",
        "name": "Pleasanton CFM",
        "street": "",
        "city": "Pleasanton",
        "state": "CA",
        "zip": "94566",
        "lat": "37.659288494212",
        "lng": "-121.875716470032",
        "season": "Year Round (Saturday)",
        "updated": "",
    }
    official = {
        "county": "Alameda",
        "name": "Pleasanton Farmers' Market",
        "location": "46 West Angela St.x Main St.,\nPleasanton, 94566",
        "days": "Sat",
        "hours": "9am -\n1pm",
        "months": "Year-\nRound",
        "pdf_page": 3,
        "table_index": 0,
        "row_index": 10,
    }
    query = {
        "query_id": "official-cas-m-3",
        "listing_id": "cas-m-3",
        "address_role": "official_roster",
        "street": "46 West Angela St.x Main St.",
        "city": "Pleasanton",
        "state": "CA",
        "zip": "94566",
    }
    result = {
        "query": query,
        "status": "Match",
        "match_type": "Non_Exact",
        "matched_address": "46 W ANGELA ST, PLEASANTON, CA, 94566",
        "matched_street": "46 W ANGELA ST",
        "matched_city": "PLEASANTON",
        "matched_state": "CA",
        "matched_zip": "94566",
        "coordinates": [37.659287806459, -121.875717273506],
        "tiger_line_id": "606239414",
        "tiger_line_side": "L",
    }
    receipts = {
        key: {"url": url, "sha256": digest, "retrieved_at": "2026-10-15T17:48:42.365412+00:00"}
        for key, url, digest in [
            ("archive", ca.SOURCE_URL, ca.markets.ARCHIVE_SHA256),
            (
                "canonical",
                "https://harvestlymarkets.com/data/us-farmers-markets-2026.csv",
                ca.markets.CANONICAL_SHA256,
            ),
            ("cdfa", "https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf", ca.PDF_SHA256),
        ]
    }
    return native, copy.deepcopy(native), official, receipts, result


def qualify(n=None, c=None, o=None, results=None):
    native, canonical, official, receipts, result = originals()
    return ca.qualification(
        n if n is not None else native,
        c if c is not None else canonical,
        ca.roster_index([o if o is not None else official]),
        receipts,
        results if results is not None else [result],
    )


def test_authentic_missing_native_street_has_alternative_proof_without_field_replacement():
    native, canonical, _, _, _ = originals()
    value, reason = qualify(native, canonical)
    assert reason is None
    assert value["row"]["address"] is None
    assert value["row"]["source_id"] == "usda-market:cas-m-3"
    assert (value["row"]["latitude"], value["row"]["longitude"]) == (
        float(native["lat"]),
        float(native["lng"]),
    )
    assert value["row"]["latitude"] != value["geocodes"][0]["coordinates"][0]
    assert native["street"] == canonical["street"] == ""
    assert value["facts"][0]["fields"]["location"] is None
    assert (
        "food_destination" in value["row"]["categories"]
        and "food" not in value["row"]["categories"]
    )
    assert value["row"]["source_updated_at"] is None


def test_unknown_native_zip_stays_unknown_while_genuine_official_zip_is_corroborated():
    n, c, _, _, _ = originals()
    n["zip"] = c["zip"] = ""
    value, reason = qualify(n, c)
    assert reason is None
    assert n["zip"] == c["zip"] == "" and value["row"]["address"] is None
    assert value["geocodes"][0]["submitted_address"]["zip"] == "94566"


@pytest.mark.parametrize(
    "field,value",
    [
        ("listing_id", ""),
        ("listing_id", "bad:id"),
        ("name", ""),
        ("name", "Farmers Market"),
        ("city", ""),
        ("lat", "NaN"),
    ],
)
def test_incomplete_identity_or_point_is_held(field, value):
    n, c, _, _, _ = originals()
    n[field] = c[field] = value
    assert qualify(n, c)[0] is None


def test_native_street_cannot_be_faked_or_gained_from_canonical_feed():
    n, c, _, _, _ = originals()
    c["street"] = "46 West Angela St"
    assert qualify(n, c)[1] == "native_canonical_identity_location_or_zip_conflict"
    n["street"] = c["street"]
    assert qualify(n, c)[1] == "outside_reviewed_missing_native_street_profile"


def test_actual_official_city_required_not_a_street_name_token():
    n, c, o, _, _ = originals()
    o["location"] = "46 Pleasanton Rd, Other Town, 94566"
    assert qualify(n, c, o)[1] == "no_exact_official_market_name_and_actual_city"


def test_multiple_official_visitor_locations_are_ambiguous():
    n, c, o, receipts, result = originals()
    another = {**o, "location": "99 Main St, Pleasanton, 94566"}
    value, reason = ca.qualification(n, c, ca.roster_index([o, another]), receipts, [result])
    assert value is None and reason == "ambiguous_multiple_official_visitor_locations"


def test_every_successful_form_participates_even_when_one_form_is_close():
    _, _, _, _, good = originals()
    far = copy.deepcopy(good)
    far["coordinates"][0] += 0.003
    assert qualify(results=[good, far])[1] == "one_genuine_address_form_exceeds_100m"


def test_missing_or_unmatched_independent_address_does_not_verify_native_point():
    _, _, _, _, result = originals()
    assert qualify(results=[])[1] == "independent_address_evidence_missing"
    result["status"] = "No_Match"
    assert qualify(results=[result])[1] == "no_literal_independent_point_within_100m"


@pytest.mark.parametrize(
    "field,bad",
    [
        ("matched_city", "Other Town"),
        ("matched_state", "NY"),
        ("matched_zip", "94567"),
        ("matched_street", "99 OTHER ST"),
    ],
)
def test_success_with_conflicting_components_is_not_cherry_picked(field, bad):
    _, _, _, _, result = originals()
    result[field] = bad
    assert qualify(results=[result])[0] is None


def test_alternate_query_must_be_genuinely_published_and_cannot_invent_native_address():
    _, _, _, _, result = originals()
    result["query"]["street"] = "46 Imagined Rd"
    assert qualify(results=[result])[1] == "official_query_is_not_a_literal_published_address"
    _, _, _, _, result = originals()
    result["query"]["address_role"] = "native_kaggle"
    assert qualify(results=[result])[1] == "unknown_native_address_cannot_be_queried_as_known"


@pytest.mark.parametrize("hours", ["9-1pm", "9-1", "9 am until later", "TBD"])
def test_unknown_meridiem_or_clock_stays_held(hours):
    n, c, o, _, _ = originals()
    o["hours"] = hours
    assert qualify(n, c, o)[1].startswith("unresolved_all_source_calendar:")


def test_all_native_canonical_and_official_seasons_and_days_intersect():
    n, c, o, _, _ = originals()
    n["season"] = "June to September"
    assert qualify(n, c, o)[1] == "outside_all_source_season_intersection"
    n["season"], c["season"] = "Year Round (Saturday)", "June to September"
    assert qualify(n, c, o)[1] == "outside_all_source_season_intersection"
    c["season"] = "Year Round (Sunday)"
    assert qualify(n, c, o)[1].startswith("unresolved_all_source_calendar:")


def test_actual_full_dwell_and_bounded_dates_preserve_saturday_only_window():
    value, _ = qualify()
    calendar = ca.bounded_calendar(value["calendar"], ca.REVIEW_START, ca.REVIEW_END)
    record = {
        "provider_id": value["row"]["source_id"],
        "categories": value["row"]["categories"],
        "source_provenance": [{"source_visit_calendar": calendar}],
    }
    zone = ZoneInfo("America/Los_Angeles")
    start, proof = solve_visit(
        record, datetime(2026, 10, 17, 11, tzinfo=zone), datetime(2026, 10, 17, 17, tzinfo=zone)
    )
    assert start.hour == 11 and proof["visit_end"].startswith("2026-10-17T13:00")
    for month, day, hour in [(10, 15, 10), (10, 17, 12), (11, 14, 9)]:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(
                record,
                datetime(2026, month, day, hour, tzinfo=zone),
                datetime(2026, month, day, 17, tzinfo=zone),
            )


def local_receipt(tmp_path, raw=b"authentic"):
    path = tmp_path / "body.bin"
    path.write_bytes(raw)
    return {
        "kind": "retained-local-artifact",
        "path": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "checked_at": datetime.now(UTC).isoformat(),
    }


def test_body_checksums_and_resource_ceiling_are_real_pre_read_gates(tmp_path):
    receipt = local_receipt(tmp_path)
    reader = ca.EvidenceReader(tmp_path, 4)
    with pytest.raises(ValueError, match="aggregate"):
        reader.read(receipt)
    assert reader.bytes == 0
    reader = ca.EvidenceReader(tmp_path, 100)
    (tmp_path / receipt["path"]).write_bytes(b"Authentic")
    with pytest.raises(ValueError, match="checksum"):
        reader.read(receipt)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.bin",
        "C:/unsafe.bin",
        "evidence/a:b.bin",
        "evidence/CON.bin",
        "evidence/trailing.",
        "evidence\\body.bin",
    ],
)
def test_evidence_paths_remain_portable_and_inside_bundle(path):
    assert not ca._portable(path)


def test_stale_and_future_evidence_are_rejected(tmp_path):
    receipt = local_receipt(tmp_path)
    for delta in [timedelta(days=31), timedelta(hours=-1)]:
        receipt["checked_at"] = (datetime.now(UTC) - delta).isoformat()
        with pytest.raises(ValueError):
            ca.EvidenceReader(tmp_path, 100).read(receipt)


@pytest.mark.parametrize(
    "values", [{"max_rows": 50001}, {"max_bytes": 104857601}, {"max_rows": True}, {"max_bytes": 0}]
)
def test_callers_cannot_raise_or_disable_unchanged_hard_guards(values):
    with pytest.raises(ValueError, match="hard resource"):
        ca.prepare("unused.json", {}, **values)


def test_unreviewed_config_cannot_supply_arbitrary_normalized_rows(tmp_path):
    path = tmp_path / "source.json"
    path.write_text('[{"source_id":"invented"}]')
    with pytest.raises(ValueError, match="manifest"):
        ca.prepare(path, {})


def test_ordinary_module_import_does_not_import_optional_pdf_dependencies(monkeypatch):
    # This remains valid in the ordinary backend environment with no source-only packages.
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    monkeypatch.setitem(sys.modules, "pdfminer", None)
    importlib.reload(ca)
    assert ca.SCHEMA.startswith("kaggle-usda-markets-ca-")


def test_full_parent_and_source_arrivals_are_both_screened():
    a = {"source_id": "usda-market:a", "latitude": 34.0, "longitude": -118.0}
    b = {"source_id": "usda-market:b", "latitude": 34.0001, "longitude": -118.0}
    assert set(ca.collision_holds([a, b], [])) == {a["source_id"], b["source_id"]}
    assert ca.collision_holds([a], [b]) == {a["source_id"]: [b["source_id"]]}


def test_failed_form_is_explicit_when_another_genuine_form_proves_location():
    _, _, _, _, good = originals()
    unmatched = copy.deepcopy(good)
    unmatched["status"] = "No_Match"
    value, reason = qualify(results=[unmatched, good])
    assert reason is None
    assert [fact["status"] for fact in value["geocodes"]] == ["No_Match", "Match"]


def test_official_postal_zip_conflict_is_never_used_to_fill_native_field():
    n, c, o, _, _ = originals()
    o["location"] = "46 West Angela St.x Main St., Pleasanton, 94567"
    assert qualify(n, c, o)[1] == "native_official_zip_conflict"
    assert n["zip"] == c["zip"] == "94566"
