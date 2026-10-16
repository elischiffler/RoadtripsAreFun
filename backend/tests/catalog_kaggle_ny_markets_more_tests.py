"""Alternative-address NY source admission preserves native unknowns and all conflicts."""

import copy
import csv
import hashlib
import importlib
import io
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.catalog import kaggle_ca_markets as ca
from app.catalog import kaggle_ny_markets_more as more
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit


def originals():
    # Exact factual fields: Kaggle v4 nys-m-27; OPEN-NY row; regional NYC PDF
    # page 1 column 1; genuine October 15 Census results (no contact fields).
    native = {
        "listing_id": "nys-m-27",
        "name": "La Familia Verde Southern Blvd Farmers' Market",
        "street": "",
        "city": "Bronx",
        "state": "NY",
        "zip": "10459",
        "lat": "40.82668",
        "lng": "-73.89169",
        "season": "July 9-November 12",
        "updated": "",
    }
    official = {
        "market_name": native["name"],
        "market_location": "Field of Dreams Park, 960 E 167th St",
        "address_line_1": "960 East 167th Street",
        "city": "Bronx",
        "state": "NY",
        "zip": "10459",
        "operation_hours": "Thu 10am-1pm",
        "operation_season": "July 9-November 12",
        "latitude": "40.82668",
        "longitude": "-73.89169",
        "georeference_1": {"type": "Point", "coordinates": [-73.89169, 40.82668]},
    }
    column = {
        "source_key": "agency-nyc-pdf",
        "snapshot_sha256": more.PDF_PINS["agency-nyc-pdf"],
        "pdf_page": 1,
        "column_index": 1,
        "bbox": [263.45784615384616, 90.11883714285705, 508.8723076923077, 584.16],
        "literal_text": "Farmers' Market\nLa Familia Verde Southern Blvd Farmers' Market\n"
        " July 9-November 12\nField of Dreams Park Thu 10am-1pm\n960 E 167th St",
    }
    receipts = {
        key: {"url": url, "sha256": digest, "retrieved_at": "2026-10-15T22:32:39.336052+00:00"}
        for key, url, digest in [
            ("archive", more.SOURCE_URL, more.markets.ARCHIVE_SHA256),
            (
                "canonical",
                "https://harvestlymarkets.com/data/us-farmers-markets-2026.csv",
                more.markets.CANONICAL_SHA256,
            ),
            ("ny", more.ny.NY_URL, more.ny.NY_SHA256),
            (
                "agency-nyc-pdf",
                "https://agriculture.ny.gov/system/files/documents/2026/09/fmnpmarketschedulescountiesnyc_0.pdf",
                more.PDF_PINS["agency-nyc-pdf"],
            ),
        ]
    }
    block, reason = more.regional_block(official, [official], [column])
    assert reason is None
    census = {}
    for query in more.address_queries(native["listing_id"], official, block):
        census[query["query_id"]] = {
            "query": query,
            "status": "Match",
            "match_type": "Non_Exact"
            if query["address_role"] in {"official_api_visitor", "official_pdf_visitor"}
            else "Exact",
            "matched_address": "960 E 167TH ST, BRONX, NY, 10459",
            "matched_street": "960 E 167TH ST",
            "matched_city": "BRONX",
            "matched_state": "NY",
            "matched_zip": "10459",
            "coordinates": [40.82673389078, -73.891442536389],
            "tiger_line_id": "80302343",
            "tiger_line_side": "R",
        }
    return native, copy.deepcopy(native), official, [column], receipts, census


def qualify(n=None, c=None, o=None, cols=None, results=None):
    native, canonical, official, columns, receipts, census = originals()
    official = o if o is not None else official
    return more.qualification(
        n if n is not None else native,
        c if c is not None else canonical,
        more.ny.roster_index([official]),
        [official],
        cols if cols is not None else columns,
        receipts,
        results if results is not None else census,
    )


def test_authentic_all_form_proof_retains_native_point_unknown_street_and_raw_seasons():
    native, canonical, _, _, _, _ = originals()
    result, reason = qualify()
    assert reason is None and result["row"]["source_id"] == "usda-market:nys-m-27"
    assert result["row"]["address"] is None and native["street"] == canonical["street"] == ""
    assert (result["row"]["latitude"], result["row"]["longitude"]) == (40.82668, -73.89169)
    assert result["row"]["latitude"] != result["geocodes"][0]["coordinates"][0]
    assert result["row"]["source_updated_at"] is None
    assert len(result["geocodes"]) == 6
    assert len(result["facts"]) == 4
    assert all(f["fields"]["season"] == "July 9-November 12" for f in result["facts"])
    assert result["regional"]["published_market_type"] == "Farmers' Market"
    assert (
        "food_destination" in result["row"]["categories"]
        and "food" not in result["row"]["categories"]
    )


def test_unknown_native_zip_is_never_filled_from_agency_or_census():
    n, c, _, _, _, _ = originals()
    n["zip"] = c["zip"] = ""
    result, reason = qualify(n, c)
    assert reason is None and result["row"]["address"] is None
    assert n["zip"] == c["zip"] == ""


@pytest.mark.parametrize(
    "key,value",
    [
        ("listing_id", ""),
        ("listing_id", "bad:id"),
        ("name", "Farmers Market"),
        ("city", ""),
        ("lat", "NaN"),
        ("lng", "181"),
    ],
)
def test_incomplete_or_invalid_identity_is_held(key, value):
    n, c, _, _, _, _ = originals()
    n[key] = c[key] = value
    assert qualify(n, c)[0] is None


def test_canonical_cannot_fill_missing_native_address():
    _, c, _, _, _, _ = originals()
    c["street"] = "960 East 167th Street"
    assert qualify(c=c)[1] == "native_canonical_identity_point_or_zip_conflict"
    n = copy.deepcopy(c)
    assert qualify(n, c)[1] == "outside_reviewed_unknown_native_street_profile"


def test_official_city_must_match_literal_native_city():
    _, _, o, _, _, _ = originals()
    o["city"] = "Manhattan"
    assert qualify(o=o)[1] == "no_unique_exact_all_source_name_city_membership"


def test_official_duplicate_identity_is_ambiguous():
    n, c, o, cols, receipts, results = originals()
    assert (
        more.qualification(n, c, more.ny.roster_index([o, o]), [o, o], cols, receipts, results)[1]
        == "no_unique_exact_all_source_name_city_membership"
    )


def test_agency_coordinate_fields_must_agree_and_native_point_must_be_nearby():
    _, _, o, _, _, _ = originals()
    o["georeference_1"]["coordinates"][0] += 0.1
    assert qualify(o=o)[0] is None
    o["longitude"] = str(float(o["longitude"]) + 0.1)
    assert qualify(o=o)[1] == "native_agency_point_exceeds_100m"


def test_missing_any_full_or_fragment_address_result_is_a_hold():
    *_, results = originals()
    results.pop(next(iter(results)))
    assert qualify(results=results)[1] == "not_every_genuine_published_address_form_was_queried"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("matched_zip", "10458", "one_successful_census_city_state_or_zip_conflicts"),
        ("matched_city", "Brooklyn", "one_successful_census_city_state_or_zip_conflicts"),
        ("matched_street", "960 E 167TH BLVD", "one_successful_census_street_is_not_literal"),
        ("coordinates", [40.82673, -73.8], "one_genuine_successful_address_form_exceeds_100m"),
    ],
)
def test_one_successful_alternative_address_conflict_overrides_other_good_forms(
    field, value, reason
):
    *_, results = originals()
    results[next(iter(results))][field] = value
    assert qualify(results=results)[1] == reason


def test_no_match_and_tie_remain_explicit_without_excusing_successful_conflicts():
    *_, results = originals()
    keys = list(results)
    results[keys[0]]["status"] = "No_Match"
    results[keys[1]]["status"] = "Tie"
    result, reason = qualify(results=results)
    assert reason is None and [x["status"] for x in result["geocodes"]][:2] == ["No_Match", "Tie"]
    for x in results.values():
        x["status"] = "No_Match"
    assert qualify(results=results)[1] == "no_positive_literal_independent_address_point"


def test_source_zip_conflict_is_held_without_native_replacement():
    n, c, o, _, _, _ = originals()
    o["zip"] = "10458"
    assert qualify(n, c, o)[1] == "native_official_zip_conflict"
    assert n["zip"] == c["zip"] == "10459"


def test_all_source_seasons_and_weekdays_participate():
    n, c, _, _, _, _ = originals()
    c["season"] = "July 9-August 1"
    assert qualify(n, c)[1] == "outside_all_source_season_intersection"
    n["season"] = c["season"] = "Year Round (Sunday)"
    assert qualify(n, c)[0] is None


@pytest.mark.parametrize("hours", ["Thu 10-1pm", "Thu 10am-1", "Thu 10am-11am"])
def test_ambiguous_meridiem_and_short_mobile_stop_windows_cannot_be_admitted(hours):
    _, _, o, _, _, _ = originals()
    o["operation_hours"] = hours
    assert qualify(o=o)[0] is None


@pytest.mark.parametrize(
    "replacement",
    [
        "private residents-only",
        "Members-only",
        "closed October 22",
        "winter hours unknown",
        "last entry 12pm",
    ],
)
def test_published_access_and_extra_calendar_restrictions_fail_closed(replacement):
    _, _, _, cols, _, _ = originals()
    cols[0]["literal_text"] += "\n" + replacement
    assert qualify(cols=cols)[0] is None


def test_published_market_type_and_every_regional_clock_are_required():
    _, _, _, cols, _, _ = originals()
    cols[0]["literal_text"] = cols[0]["literal_text"].replace(
        "Farmers' Market\n", "Mobile Market\n", 1
    )
    assert qualify(cols=cols)[1] == "not_a_published_fixed_consumer_farmers_market"
    _, _, _, cols, _, _ = originals()
    cols[0]["literal_text"] = cols[0]["literal_text"].replace("Thu 10am-1pm", "Fri 10am-1pm")
    assert qualify(cols=cols)[1] == "regional_and_open_ny_calendar_conflict_or_incomplete_clock"


def test_regional_address_change_or_duplicate_identity_is_a_hold():
    _, _, _, cols, _, _ = originals()
    assert (
        qualify(cols=cols + copy.deepcopy(cols))[1]
        == "regional_publication_identity_missing_or_ambiguous"
    )
    cols[0]["literal_text"] = cols[0]["literal_text"].replace("960 E 167th St", "950 E 167th St")
    assert qualify(cols=cols)[1] == "regional_and_open_ny_visitor_location_conflict"


def census_csv():
    n, _, o, cols, _, results = originals()
    block, _ = more.regional_block(o, [o], cols)
    queries = more.address_queries(n["listing_id"], o, block)
    request, response = io.StringIO(newline=""), io.StringIO(newline="")
    for q in queries:
        csv.writer(request).writerow([q[k] for k in ("query_id", "street", "city", "state", "zip")])
        r = results[q["query_id"]]
        csv.writer(response).writerow(
            [
                q["query_id"],
                ", ".join(q[k] for k in ("street", "city", "state", "zip")),
                "Match",
                r["match_type"],
                r["matched_address"],
                "-73.891442536389,40.82673389078",
                "80302343",
                "R",
            ]
        )
    return (
        request.getvalue().encode(),
        response.getvalue().encode(),
        {
            "benchmark": more.markets.CENSUS_BENCHMARK,
            "benchmark_name": more.markets.CENSUS_BENCHMARK_NAME,
            "queries": queries,
        },
    )


def test_exact_original_census_request_and_out_of_order_results_replay():
    request, response, doc = census_csv()
    assert len(more.parse_census(request, response, doc)) == 6
    assert (
        len(
            more.parse_census(
                request, b"\r\n".join(reversed(response.split(b"\r\n")[:-1])) + b"\r\n", doc
            )
        )
        == 6
    )
    with pytest.raises(ValueError):
        more.parse_census(request.replace(b"Bronx", b"Brooklyn", 1), response, doc)
    with pytest.raises(ValueError):
        more.parse_census(request, response + response.splitlines()[0] + b"\r\n", doc)
    with pytest.raises(ValueError):
        more.parse_census(request, response.split(b"\r\n", 1)[1], doc)


def test_census_incomplete_match_status_and_benchmark_are_rejected():
    request, response, doc = census_csv()
    rows = list(csv.reader(io.StringIO(response.decode())))
    rows[0] = rows[0][:3]
    altered = io.StringIO(newline="")
    csv.writer(altered).writerows(rows)
    with pytest.raises(ValueError):
        more.parse_census(request, altered.getvalue().encode(), doc)
    doc["benchmark"] = "0"
    with pytest.raises(ValueError):
        more.parse_census(request, response, doc)


def test_actual_cpsat_full_dwell_respects_thursday_clocks_closed_days_and_review_horizon():
    item, reason = qualify()
    assert reason is None
    cal = more.ny.bounded_calendar(item["calendar"], more.REVIEW_START, more.REVIEW_END)
    row = {
        "provider_id": item["row"]["source_id"],
        "categories": item["row"]["categories"],
        "source_provenance": [{"source_visit_calendar": cal}],
    }
    zone = ZoneInfo("America/New_York")
    start, proof = solve_visit(
        row, datetime(2026, 10, 15, 10, tzinfo=zone), datetime(2026, 10, 15, 13, tzinfo=zone)
    )
    assert start.hour == 10 and datetime.fromisoformat(proof["visit_end"]).hour == 12
    for day, hour in [(17, 10), (15, 12)]:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(
                row,
                datetime(2026, 10, day, hour, tzinfo=zone),
                datetime(2026, 10, day, 18, tzinfo=zone),
            )
    with pytest.raises(VisitCalendarConflict):
        solve_visit(
            row, datetime(2026, 11, 19, 10, tzinfo=zone), datetime(2026, 11, 19, 18, tzinfo=zone)
        )


def test_evidence_checksum_pre_read_bytes_and_freshness_fail_closed(tmp_path):
    body = tmp_path / "body.bin"
    body.write_bytes(b"Authentic")
    receipt = {
        "kind": "retained-local-artifact",
        "path": body.name,
        "sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
        "bytes": 9,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    reader = more.EvidenceReader(tmp_path, 8)
    with pytest.raises(ValueError):
        reader.read(receipt)
    assert reader.bytes == 0
    body.write_bytes(b"Corrupted")
    with pytest.raises(ValueError):
        more.EvidenceReader(tmp_path, 20).read(receipt)
    body.write_bytes(b"Authentic")
    for age in [timedelta(days=31), timedelta(hours=-1)]:
        receipt["checked_at"] = (datetime.now(UTC) - age).isoformat()
        with pytest.raises(ValueError):
            more.EvidenceReader(tmp_path, 20).read(receipt)


@pytest.mark.parametrize("verify", [more.verify_original_pdfs, ca.verify_original_pdf])
def test_optional_pdf_replay_rejects_oversized_control_before_read(tmp_path, monkeypatch, verify):
    control = tmp_path / "control.json"
    control.write_bytes(b" " * 32769)

    def forbidden_read(path):
        pytest.fail("oversized control must be rejected before reading bytes")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    with pytest.raises(ValueError, match="configuration missing or oversized"):
        verify(control)


@pytest.mark.parametrize(
    "module,verify", [(more, more.verify_original_pdfs), (ca, ca.verify_original_pdf)]
)
def test_optional_pdf_replay_charges_control_against_aggregate_before_index_read(
    tmp_path, monkeypatch, module, verify
):
    index = tmp_path / "index.json"
    body = b" " * 128
    index.write_bytes(body)
    control = tmp_path / "control.json"
    control.write_text(
        json.dumps({"index": {"path": index.name, "sha256": hashlib.sha256(body).hexdigest()}})
    )
    monkeypatch.setattr(module, "MAX_BYTES", control.stat().st_size + len(body) - 1)
    original_read = Path.read_bytes

    def guarded_read(path):
        if path == index:
            pytest.fail("aggregate overflow must be rejected before reading index bytes")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError, match="aggregate evidence byte ceiling"):
        verify(control)


@pytest.mark.parametrize(
    "kwargs", [{"max_rows": 50001}, {"max_rows": True}, {"max_bytes": 104857601}, {"max_bytes": 0}]
)
def test_unchanged_hard_resource_guards_cannot_be_disabled_or_raised(kwargs):
    with pytest.raises(ValueError, match="hard resource"):
        more.prepare("unused.json", {}, **kwargs)


def test_arbitrary_normalized_rows_are_not_admission_authority(tmp_path):
    path = tmp_path / "source.json"
    path.write_text('[{"source_id":"invented"}]')
    with pytest.raises(ValueError, match="manifest"):
        more.prepare(path, {})


def test_normal_backend_import_does_not_require_optional_pdf_packages(monkeypatch):
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    monkeypatch.setitem(sys.modules, "pdfminer", None)
    importlib.reload(more)
    assert more.SCHEMA.startswith("kaggle-usda-markets-ny-alternative-")


def test_source_and_complete_parent_collisions_both_hold():
    a = {"source_id": "usda-market:a", "latitude": 40.0, "longitude": -74.0}
    b = {"source_id": "usda-market:b", "latitude": 40.0001, "longitude": -74.0}
    assert set(more.ny.collision_holds([a, b], [])) == {a["source_id"], b["source_id"]}
    assert more.ny.collision_holds([a], [b]) == {a["source_id"]: [b["source_id"]]}
