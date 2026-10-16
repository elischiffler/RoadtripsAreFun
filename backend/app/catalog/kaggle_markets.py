"""Offline admission of a frozen Kaggle/USDA market batch and real arrivals.

Registry membership corroborates a dated visitor destination, never all-day
opening or parking. All source seasons participate; native points stay intact.
The source producer independently verifies the pinned PDF table extraction.
"""

import calendar
import csv
import hashlib
import io
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from itertools import product
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html

from app.catalog import market_visit_calendar, roadside

SCHEMA = "kaggle-usda-markets-reviewed-arrivals/1"
SOURCE_URL = (
    "https://www.kaggle.com/datasets/harvestlymarkets/us-farmers-markets-by-state-2026/versions/4"
)
RELEASE = "kaggle-usda-markets-v4+review-2026-10-15"
ATTRIBUTION = (
    "Harvestly Markets (CC BY 4.0), derived from USDA AMS Local Food Portal; "
    "California and Connecticut Departments of Agriculture, Delaware Department "
    "of Agriculture, Burlington Farmers Market visitor facts; "
    "U.S. Census Bureau Public_AR_ACS2026 address-range corroboration; "
    "driving evidence: OSRM, © OpenStreetMap contributors (ODbL). No endorsement."
)
INDEX_SHA256 = "e97d56b9daac8a560c26b5f904cfafd2a73b2e9bc91439ce42d645496aa5d06c"
ARCHIVE_SHA256 = "dea363d2a400f008fa28c933dc6816af2bb7166bea5e5795adc9ec79989d30b1"
CSV_SHA256 = "42a4ec12c0900d1b7a513c084cec5d0fc5045194cfbe8ad72062b78da3c76648"
CANONICAL_SHA256 = "76b5e9887643a7cb82d91c89682d52c5c531c88d74fc9e2bed3ef79146039514"
MEMBER = "us-farmers-markets-2026.csv"
CSV_ROWS, CANONICAL_ROWS = 8863, 7947
FIELDS = (
    "listing_id,name,street,city,state,state_name,zip,lat,lng,phone,website,facebook,"
    "instagram,twitter,youtube,pinterest,season,products,description,updated,"
    "accepts_snap,accepts_ebt,organic_certified,organic_practices,csa_vendor_present,"
    "indoor_market,online_order_available,delivery_available,payment_cash,"
    "payment_credit_debit,live_enriched"
).split(",")
DAYS = {
    form: short
    for short, forms in {
        "mon": "mon monday mondays",
        "tue": "tue tues tuesday tuesdays",
        "wed": "wed wednesday wednesdays",
        "thu": "thu thur thurs thursday thursdays",
        "fri": "fri friday fridays",
        "sat": "sat saturday saturdays",
        "sun": "sun sunday sundays",
    }.items()
    for form in forms.split()
}
MONTHS = {
    name.lower(): month
    for month in range(1, 13)
    for name in (calendar.month_name[month], calendar.month_abbr[month])
} | {"sept": 9}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))


def plain(value):
    return " ".join(unicodedata.normalize("NFKD", value or "").replace("’", "'").split())


def words(value):
    value = plain(value).lower().replace("'", "").replace("cfm", " certified farmers market ")
    return re.findall(r"[a-z0-9]+", value)


def core(value):
    stops = {"certified", "farmer", "farmers", "market", "markets", "on", "at", "the", "of", "and"}
    return tuple(sorted(word for word in words(value) if word not in stops and word not in DAYS))


def weekdays(value):
    return {DAYS[word] for word in words(value) if word in DAYS}


def address_words(value):
    aliases = {
        "st": "street",
        "rd": "road",
        "ave": "avenue",
        "blvd": "boulevard",
        "hwy": "highway",
        "dr": "drive",
        "pkwy": "parkway",
        "ln": "lane",
        "n": "north",
        "s": "south",
        "w": "west",
        "e": "east",
    }
    return {aliases.get(word, word) for word in words(value)}


def location_matches(row, official):
    """Literal city and road agreement, without geocoding or fuzzy name guesses."""
    native, published = address_words(row["street"]), address_words(official["location"])
    city = address_words(row["city"])
    if not city or not city <= published:
        return False
    street_types = {
        "street",
        "road",
        "avenue",
        "boulevard",
        "highway",
        "drive",
        "parkway",
        "lane",
        "way",
        "court",
        "place",
    }
    if native <= published and native & street_types and any(word.isdigit() for word in native):
        return True
    native, published = native - city, published - city
    generic = {
        "street",
        "road",
        "avenue",
        "boulevard",
        "highway",
        "drive",
        "parkway",
        "lane",
        "north",
        "south",
        "west",
        "east",
        "and",
        "at",
        "between",
        "corner",
        "ca",
        "california",
        "in",
        "block",
        "on",
        "the",
        "of",
        "lot",
        "parking",
        "to",
    }
    distinct = {word for word in native & published if word not in generic and not word.isdigit()}
    a = {word for word in native if word.isdigit()}
    b = {word for word in published if word.isdigit()}
    if a and b and not a & b:
        return (
            bool({"and", "at", "between", "corner"} & (native | published)) and len(distinct) >= 2
        )
    return bool(a & b and distinct) or len(distinct) >= 2


def season(value, as_of=None):
    """Three-valued admission: positive, negative, or explicitly unknown.

    Unqualified month-only bounds include the entire named month. Precise dates
    remain precise. Complex/approximate statements are withheld for review.
    """
    as_of = as_of or datetime.now(UTC).date()
    text = plain(value).lower().replace("–", "-").replace("—", "-")
    if not text:
        return "unknown_blank"
    if re.search(r"20\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", text):
        return "review_explicit_year"
    if re.search(r"\byear\s*-?\s*round\b", text):
        if any(word in text for word in ("except", "closed", "/")):
            return "review_qualified_year_round"
        if re.search(r"\b(" + MONTH_PATTERN + r")\b", text):
            return "review_qualified_year_round"
        qualifiers = re.findall(r"\(([^)]*)\)", text)
        if any(any(word not in DAYS and word != "and" for word in words(q)) for q in qualifiers):
            return "review_qualified_year_round"
        return "in_year_round"
    matches = list(re.finditer(r"\b(" + MONTH_PATTERN + r")\b(?:\s+(\d{1,2})(?!\d))?", text))
    if not matches:
        if re.search(r"\b(?:summer|winter|spring|autumn|fall|closed|closure)\b", text):
            return "review_descriptive_season"
        return "unknown_no_months"
    if len(matches) != 2:
        return "review_complex_or_single_month"
    start, end = matches
    if not re.fullmatch(r"\s*(?:-|to|through)\s*", text[start.end() : end.start()]):
        return "review_complex_separator"
    if any(word in text for word in ("mid", "early", "late")):
        return "review_approximate_boundary"
    try:
        a = date(2000, MONTHS[start[1]], int(start[2] or 1))
        b = date(2000, MONTHS[end[1]], int(end[2] or calendar.monthrange(2000, MONTHS[end[1]])[1]))
        today = date(2000, as_of.month, as_of.day)
    except ValueError:
        return "review_invalid_date"
    inside = a <= today <= b if a <= b else today >= a or today <= b
    return "in_interval" if inside else "out_interval"


def retained(root, evidence, *, ceiling=15 * 1024 * 1024):
    name = evidence.get("path", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", name):
        raise ValueError("invalid market receipt path")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("market receipt escapes or is missing")
    if not 0 < path.stat().st_size <= ceiling:
        raise ValueError("market receipt byte ceiling exceeded")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence.get("sha256"):
        raise ValueError("market receipt checksum mismatch")
    roadside.checked_time(evidence["retrieved_at"])
    if evidence.get("status") != 200 or evidence.get("bytes", len(raw)) != len(raw):
        raise ValueError("market acquisition status/bytes mismatch")
    return raw


def csv_rows(raw, expected):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != FIELDS:
        raise ValueError("market CSV schema differs from pinned source")
    result = {}
    for row in reader:
        ident = row.get("listing_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ident) or ident in result or None in row:
            raise ValueError("market CSV identity is missing, duplicate, or malformed")
        result[ident] = row
        if len(result) > expected:
            raise ValueError("market source row ceiling exceeded")
    if len(result) != expected:
        raise ValueError("market source row count mismatch")
    return result


def load_sources(root, index):
    data, size = {}, 0
    for key in (
        "archive",
        "canonical",
        "kaggle_metadata",
        "cdfa",
        "cdfa_rows",
        "ct",
        "ct_rows",
        "de",
        "vt",
    ):
        data[key] = retained(root, index[key])
        size += len(data[key])
    if hashlib.sha256(data["archive"]).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("market archive is not pinned Kaggle v4")
    if hashlib.sha256(data["canonical"]).hexdigest() != CANONICAL_SHA256:
        raise ValueError("market canonical snapshot differs from reviewed correction")
    with zipfile.ZipFile(io.BytesIO(data["archive"])) as archive:
        info = archive.getinfo(MEMBER)
        if not 0 < info.file_size <= 5 * 1024 * 1024:
            raise ValueError("market CSV member byte ceiling exceeded")
        raw = archive.read(info)
    if hashlib.sha256(raw).hexdigest() != CSV_SHA256:
        raise ValueError("market CSV differs from pinned Kaggle member")
    metadata = json.loads(data["kaggle_metadata"])
    if metadata.get("currentVersionNumber") != 4 or "CC BY 4.0" not in metadata.get(
        "description", ""
    ):
        raise ValueError("market Kaggle version/license evidence differs")
    for evidence in index["rights"]:
        size += len(retained(root, evidence, ceiling=2 * 1024 * 1024))
    native, canonical = csv_rows(raw, CSV_ROWS), csv_rows(data["canonical"], CANONICAL_ROWS)
    rosters = []
    for region, key, pdf_key in (("CA", "cdfa_rows", "cdfa"), ("CT", "ct_rows", "ct")):
        table = json.loads(data[key])
        if table.get("sha256") != index[pdf_key]["sha256"] or table.get("anomalies"):
            raise ValueError("market PDF extraction is not bound to retained original")
        for row in table["rows"]:
            rosters.append({**row, "region": region, "receipt_key": pdf_key})
    return native, canonical, rosters, data, size + len(raw)


def targeted_records(data):
    """Two exact, separately inspected profiles for otherwise empty states."""

    def text(raw):
        document = html.fromstring(raw)
        for node in document.xpath("//script|//style"):
            node.drop_tree()
        return " ".join(" ".join(document.itertext()).split())

    de, vt = text(data["de"]), text(data["vt"])
    fall = (
        "Lewes School Parking Lot (fall market location) , 820 Savannah Road Lewes, DE 19958 "
        "Saturdays, 9 a.m. to Noon, Oct. 3-Dec. 5, 2026"
    )
    summer = (
        "George H. P. Smith Park (spring/summer market location) , DuPont & Johnson Avenues "
        "Lewes, DE 19958 Saturdays, 8 a.m. to Noon, May 2-Sept. 26, 2026"
    )
    burlington = (
        "Summer 2026 9:00 am - 2:00pm | 345 Pine St | Burlington, Vermont "
        "Every Saturday May 9 - October 31, 2026 Rain or shine."
    )
    if fall not in de or summer not in de or burlington not in vt:
        raise ValueError("market targeted official profile requires renewed review")
    return {
        "301530": {
            "name": "Historic Lewes Farmers Market",
            "region": "DE",
            "receipt_key": "de",
            "location": "820 Savannah Road, Lewes, DE 19958",
            "days": "Saturdays",
            "hours": "9 a.m. to Noon",
            "start": "2026-10-03",
            "end": "2026-12-05",
            "other_location_facts": [
                {
                    "location": "George H. P. Smith Park, DuPont & Johnson Avenues, Lewes, DE 19958",
                    "season": "May 2-Sept. 26, 2026",
                    "days": "Saturdays",
                    "hours": "8 a.m. to Noon",
                    "applies_to_selected_native_point": False,
                }
            ],
        },
        "301158": {
            "name": "Burlington Farmers Market",
            "region": "VT",
            "receipt_key": "vt",
            "location": "345 Pine St, Burlington, Vermont",
            "days": "Every Saturday",
            "hours": "9:00 am - 2:00pm",
            "start": "2026-05-09",
            "end": "2026-10-31",
            "weather_qualification": "Rain or shine.",
        },
    }


def qualification(native, current, officials, *, as_of=None):
    as_of = as_of or datetime.now(UTC).date()
    if current is None:
        return None, "not_in_current_canonical_membership"
    if any(
        native.get(key) != current.get(key)
        for key in ("name", "street", "city", "state", "lat", "lng")
    ):
        return None, "canonical_identity_or_location_changed"
    if native.get("state") not in {"CA", "CT", "DE", "VT"}:
        return None, "outside_reviewed_regional_rosters"
    try:
        lat, lon = float(native["lat"]), float(native["lng"])
        if (
            not all(map(math.isfinite, (lat, lon)))
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError
    except (TypeError, ValueError, KeyError):
        return None, "native_coordinates"
    found = []
    for official in officials:
        if official["region"] != native["state"] or core(official["name"]) != core(native["name"]):
            continue
        place = {**official, "location": official["location"] + ", " + official.get("city", "")}
        if not location_matches(native, place):
            continue
        nd, od = weekdays(current["season"]), weekdays(official["days"])
        if nd and od and not nd & od:
            continue
        found.append(official)
    if not found:
        return None, "no_exact_name_city_road_weekday_match"
    if len({plain(row["location"]) for row in found}) != 1:
        return None, "multiple_official_locations"
    for official in found:
        if official["region"] == "CA":
            assessment = season(official["months"], as_of)
            if not assessment.startswith("in_"):
                return None, "official_season_" + assessment
        else:
            try:
                if "start" in official:
                    start, end = (
                        date.fromisoformat(official["start"]),
                        date.fromisoformat(official["end"]),
                    )
                else:
                    start = datetime.strptime(official["start_date"] + "-2026", "%d-%b-%Y").date()
                    end = datetime.strptime(official["end_date"] + "-2026", "%d-%b-%Y").date()
                if not start <= as_of <= end:
                    return None, "official_season_outside_current_date"
            except ValueError:
                return None, "official_season_unresolved"
    for label, row in (("kaggle", native), ("canonical", current)):
        assessment = season(row["season"], as_of)
        if assessment.startswith(("out_", "review_")):
            return None, label + "_season_" + assessment
    return {
        "source_id": "usda-market:" + native["listing_id"],
        "name": native["name"].strip(),
        "latitude": lat,
        "longitude": lon,
        "region": native["state"],
        "address": native["street"],
        "categories": ["farmers_market", "food_destination", "daytime", "public_destination"],
        "source_updated_at": None,
        "official_rows": found,
    }, None


def driving(root, entry, row):
    raw = retained(root, entry, ceiling=1024 * 1024)
    data = json.loads(raw)
    lat, lon = row["latitude"], row["longitude"]
    expected = f"/route/v1/driving/{lon},{lat + 0.01};{lon},{lat}"
    url = urlsplit(entry.get("url", ""))
    if (url.scheme, url.netloc, url.path) != (
        "https",
        "router.project-osrm.org",
        expected,
    ) or entry.get("source_coordinates") != [lat, lon]:
        raise ValueError("market driving query changed the native point")
    waypoints = data.get("waypoints", [])
    if (
        entry.get("checked_waypoint") != "destination"
        or data.get("code") != "Ok"
        or len(waypoints) != 2
    ):
        raise ValueError("market driving requires a successful two-waypoint destination")
    distance = waypoints[-1].get("distance")
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or not 0 <= distance <= 75
    ):
        raise ValueError("market driving destination exceeds 75 metres")
    if entry.get("snap_distance_m") != distance or entry.get("road_name") != waypoints[-1].get(
        "name"
    ):
        raise ValueError("market driving summary disagrees with raw destination")
    return len(raw), distance


CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
CENSUS_BENCHMARK = "8"
CENSUS_BENCHMARK_NAME = "Public_AR_ACS2026"
MAX_GEOCODE_DISTANCE_M = 100
COLLISION_DISTANCE_M = 250
REVIEW_HOLDS = {
    "301303": "independent Census address positions disagree with native East Palo Alto point",
    "301314": "independent Census intersection is approximately 4.9 km from native California Avenue point",
    "308615": "unresolved shared arrival with 308803; distinct calendars do not prove distinct destinations",
    "308803": "unresolved shared arrival with 308615; distinct calendars do not prove distinct destinations",
}


def point_distance(a, b):
    lat_a, lat_b = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    return (
        6371000
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin((lat_b - lat_a) / 2) ** 2
                    + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlon / 2) ** 2
                ),
            )
        )
    )


def parse_census(request_raw, response_raw, query_document):
    """Bind every batch result to the exact submitted public venue address."""
    if (query_document.get("benchmark"), query_document.get("benchmark_name")) != (
        CENSUS_BENCHMARK,
        CENSUS_BENCHMARK_NAME,
    ):
        raise ValueError("Census benchmark differs from the frozen address-range snapshot")
    queries = query_document.get("queries", [])
    if not 1 <= len(queries) <= 1000:
        raise ValueError("Census query count exceeds the reviewed batch bound")
    submitted = list(csv.reader(io.StringIO(request_raw.decode("utf-8"), newline="")))
    expected = [
        [query[key] for key in ("query_id", "street", "city", "state", "zip")] for query in queries
    ]
    if submitted != expected:
        raise ValueError("Census request CSV differs from retained query fields")
    by_query = {query["query_id"]: query for query in queries}
    if len(by_query) != len(queries):
        raise ValueError("duplicate Census submitted identity")
    results = {}
    for fields in csv.reader(io.StringIO(response_raw.decode("utf-8"), newline="")):
        if len(fields) not in {3, 8} or fields[0] not in by_query or fields[0] in results:
            raise ValueError("Census response identity/row schema is missing or ambiguous")
        query = by_query[fields[0]]
        if (
            query["query_id"]
            != ("native-" if query["address_role"] == "native_kaggle" else "official-")
            + query["listing_id"]
        ):
            raise ValueError("Census query identity/role disagreement")
        if query["address_role"] not in {"native_kaggle", "official_roster"}:
            raise ValueError("unreviewed Census address role")
        if fields[1] != ", ".join(query[key] for key in ("street", "city", "state", "zip")):
            raise ValueError("Census returned input differs from submitted address")
        result = {"query": query, "status": fields[2]}
        if fields[2] == "Match":
            if len(fields) != 8 or fields[3] not in {"Exact", "Non_Exact"}:
                raise ValueError("Census match schema/precision is unresolved")
            parts = [part.strip() for part in fields[4].split(",")]
            if len(parts) != 4:
                raise ValueError("Census matched address components are unresolved")
            try:
                lon, lat = map(float, fields[5].split(","))
                if (
                    not math.isfinite(lat)
                    or not math.isfinite(lon)
                    or not -90 <= lat <= 90
                    or not -180 <= lon <= 180
                ):
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError("Census coordinate schema is invalid") from None
            result.update(
                {
                    "match_type": fields[3],
                    "matched_address": fields[4],
                    "matched_street": parts[0],
                    "matched_city": parts[1],
                    "matched_state": parts[2],
                    "matched_zip": parts[3],
                    "coordinates": [lat, lon],
                    "tiger_line_id": fields[6] or None,
                    "tiger_line_side": fields[7] or None,
                }
            )
        elif fields[2] not in {"No_Match", "Tie"} or len(fields) != 3:
            raise ValueError("Census result is not a reviewed match status")
        results[fields[0]] = result
    if set(results) != set(by_query):
        raise ValueError("Census batch response omitted submitted identities")
    return results


def load_census(root, index):
    inventory = index["census"]
    data = {
        key: retained(root, inventory[key], ceiling=2 * 1024 * 1024)
        for key in ("request", "response", "queries", "benchmarks")
    }
    response = inventory["response"]
    if (
        response.get("url"),
        response.get("method"),
        response.get("benchmark"),
        response.get("benchmark_name"),
    ) != (CENSUS_URL, "POST", CENSUS_BENCHMARK, CENSUS_BENCHMARK_NAME):
        raise ValueError("Census receipt differs from the actual pinned batch request")
    if response.get("request_sha256") != hashlib.sha256(data["request"]).hexdigest():
        raise ValueError("Census response request checksum mismatch")
    benchmarks = json.loads(data["benchmarks"])
    if not any(
        item.get("id") == CENSUS_BENCHMARK and item.get("benchmarkName") == CENSUS_BENCHMARK_NAME
        for item in benchmarks.get("benchmarks", [])
    ):
        raise ValueError("Census benchmark is not present in retained official metadata")
    return parse_census(data["request"], data["response"], json.loads(data["queries"])), sum(
        map(len, data.values())
    )


def census_qualification(native, officials, results):
    """Census is independent range interpolation, never a replacement point.

    Every successful form participates. Unknown forms need another genuine
    published form with full components and a point within the same bound.
    """
    ident = native["listing_id"]
    if ident in REVIEW_HOLDS:
        return None, "review_hold: " + REVIEW_HOLDS[ident]
    native_zip = native.get("zip", "").strip()
    if not re.fullmatch(r"\d{5}(?:-\d{4})?", native_zip):
        return None, "census_native_zip_unknown"
    native_zip = native_zip[:5]
    for official in officials:
        published_zip = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", plain(official["location"]))
        if published_zip and published_zip[1] != native_zip:
            return None, "official_native_zip_conflict"
    entries = [entry for entry in results.values() if entry["query"]["listing_id"] == ident]
    if not entries:
        return None, "census_evidence_not_acquired"
    evidence, corroborated = [], False
    for entry in entries:
        query = entry["query"]
        if (query["city"], query["state"]) != (native["city"], native["state"]):
            return None, "census_query_city_state_disagreement"
        if query["address_role"] == "native_kaggle":
            if any(query[key] != native[key] for key in ("street", "city", "state", "zip")):
                return None, "census_query_changed_native_address"
        else:
            published = [
                official
                for official in officials
                if address_words(query["street"]) <= address_words(official["location"])
                and query["street"].strip()
            ]
            if not published:
                return None, "census_query_not_published_official_address"
        fact = {
            key: entry.get(key)
            for key in (
                "status",
                "match_type",
                "matched_address",
                "coordinates",
                "tiger_line_id",
                "tiger_line_side",
            )
        }
        fact["submitted_address"] = {key: query[key] for key in ("street", "city", "state", "zip")}
        fact["address_role"] = query["address_role"]
        fact["query_id"] = query["query_id"]
        if entry["status"] == "Match":
            if (
                plain(entry["matched_city"]).casefold(),
                entry["matched_state"],
                entry["matched_zip"],
            ) != (plain(native["city"]).casefold(), native["state"], native_zip):
                return None, "census_matched_city_state_zip_disagreement"
            distance = point_distance(
                [float(native["lat"]), float(native["lng"])], entry["coordinates"]
            )
            fact["native_point_distance_m"] = distance
            if distance > MAX_GEOCODE_DISTANCE_M:
                return None, "census_native_point_more_than_100m_away"
            literal = address_words(entry["matched_street"]) <= address_words(query["street"])
            fact["literal_street_agreement"] = literal
            corroborated = corroborated or literal
        evidence.append(fact)
    if not corroborated:
        return None, "census_no_unambiguous_literal_address_match"
    return evidence, None


def reject_collisions(rows):
    """Bounded unit-Cartesian grid, including poles and the antimeridian.

    A pair closer than the arc bound also has chord distance below that bound,
    hence its three coordinates occupy the same or adjacent grid cells.
    """
    cell_size = COLLISION_DISTANCE_M / 6_371_000
    buckets = {}
    for row in rows:
        latitude, longitude = math.radians(row["latitude"]), math.radians(row["longitude"])
        position = (
            math.cos(latitude) * math.cos(longitude),
            math.cos(latitude) * math.sin(longitude),
            math.sin(latitude),
        )
        cell = tuple(math.floor(coordinate / cell_size) for coordinate in position)
        for offset in product((-1, 0, 1), repeat=3):
            neighbor = tuple(value + delta for value, delta in zip(cell, offset))
            for other in buckets.get(neighbor, ()):
                if (
                    point_distance(
                        [row["latitude"], row["longitude"]], [other["latitude"], other["longitude"]]
                    )
                    < COLLISION_DISTANCE_M
                ):
                    raise ValueError("unresolved market arrival collision within 250 metres")
        buckets.setdefault(cell, []).append(row)


def prepare(path, manifest, *, max_rows, max_bytes):
    if (manifest.get("source_url"), manifest.get("release"), manifest.get("attribution")) != (
        SOURCE_URL,
        RELEASE,
        ATTRIBUTION,
    ):
        raise ValueError("market manifest differs from the reviewed source/release")
    if set(manifest.get("licenses", {})) != {"CC-BY-4.0", "LicenseRef-US-Census-Geocoder"}:
        raise ValueError("markets require retained CC-BY-4.0 and Census Geocoder license evidence")
    path = Path(path)
    if not 0 < path.stat().st_size <= 32_768:
        raise ValueError("market bundle byte ceiling exceeded")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("market bundle checksum mismatch")
    bundle, root = json.loads(raw), path.parent
    inventory_raw = retained(root, bundle["index"], ceiling=1024 * 1024)
    if hashlib.sha256(inventory_raw).hexdigest() != INDEX_SHA256:
        raise ValueError("market acquisition inventory is not the frozen review")
    index = json.loads(inventory_raw)
    selection = bundle.get("selection")
    if (
        selection != index.get("selection")
        or not selection
        or len(selection) > max_rows
        or len(set(selection)) != len(selection)
    ):
        raise ValueError("market selection differs from frozen bounded review")
    native, current, rosters, data, size = load_sources(root, index)
    targeted = targeted_records(data)
    census, census_bytes = load_census(root, index)
    size += census_bytes
    checks = {entry["listing_id"]: entry for entry in index["driving"]}
    if len(checks) != len(index["driving"]):
        raise ValueError("duplicate market driving identity")
    rows, rejects, regions = [], Counter(), Counter()
    for ident in selection:
        source, canonical = native.get(ident), current.get(ident)
        if source is None:
            raise ValueError("selected market is missing its Kaggle source identity")
        officials = [targeted[ident]] if ident in targeted else rosters
        row, reason = qualification(source, canonical, officials)
        if reason:
            raise ValueError("selected market no longer qualifies: " + reason)
        geo_facts, geo_reason = census_qualification(source, row["official_rows"], census)
        if geo_reason:
            raise ValueError("selected market coordinate corroboration failed: " + geo_reason)
        check = checks[ident]
        nbytes, distance = driving(root, check, row)
        size += nbytes
        if size + len(raw) + len(inventory_raw) > max_bytes:
            raise ValueError("market aggregate evidence byte ceiling exceeded")
        officials = row.pop("official_rows")
        fact_groups = []
        for label, record, receipt in (
            ("kaggle_feed", source, index["archive"]),
            ("canonical_feed", canonical, index["canonical"]),
        ):
            fact_groups.append(
                {
                    "feed": label,
                    "record_id": ident,
                    "source_url": receipt["url"],
                    "snapshot_sha256": receipt["sha256"],
                    "checked_at": receipt["retrieved_at"],
                    "fields": {
                        "season": record["season"] or None,
                        "source_updated_at_raw": record["updated"] or None,
                        "location": record["street"] or None,
                        "city": record["city"] or None,
                    },
                }
            )
        for official in officials:
            receipt = index[official["receipt_key"]]
            fields = {
                key: official.get(key)
                for key in (
                    "name",
                    "location",
                    "days",
                    "hours",
                    "months",
                    "start_date",
                    "end_date",
                    "start_time",
                    "end_time",
                    "start",
                    "end",
                    "weather_qualification",
                    "other_location_facts",
                )
            }
            fact_groups.append(
                {
                    "feed": "official_visitor_facts",
                    "source_url": receipt["url"],
                    "snapshot_sha256": receipt["sha256"],
                    "checked_at": receipt["retrieved_at"],
                    "pdf_page": official.get("pdf_page"),
                    "table_index": official.get("table_index"),
                    "row_index": official.get("row_index"),
                    "fields": fields,
                }
            )
        url = canonical["website"]
        row["url"] = (
            url
            if urlsplit(url).scheme in {"http", "https"} and urlsplit(url).netloc
            else index[officials[0]["receipt_key"]]["url"]
        )
        row["provenance"] = [
            {
                "dataset": "kaggle-usda-markets",
                "record_id": ident,
                "source_url": SOURCE_URL,
                "license": "CC-BY-4.0",
                "snapshot_sha256": ARCHIVE_SHA256,
                "checked_at": index["archive"]["retrieved_at"],
                "coordinate_source": "unchanged Kaggle v4 latitude/longitude; publisher identifies USDA native coordinates; canonical snapshot agrees exactly",
                "point_role": "published recurring public market destination",
                "arrival_type": "native market point with independently corroborated street/city and nearby driving destination; parking unknown",
                "primary_category": "food",
                "coordinate_corroboration": {
                    "dataset": "U.S. Census Bureau Geocoder",
                    "license": "LicenseRef-US-Census-Geocoder",
                    "source_url": CENSUS_URL,
                    "snapshot_sha256": index["census"]["response"]["sha256"],
                    "request_sha256": index["census"]["response"]["request_sha256"],
                    "checked_at": index["census"]["response"]["retrieved_at"],
                    "benchmark": CENSUS_BENCHMARK_NAME,
                    "max_native_point_distance_m": MAX_GEOCODE_DISTANCE_M,
                    "native_coordinates_replaced": False,
                    "point_role": "interpolated address-range corroboration; not an entrance or parking coordinate",
                    "results": geo_facts,
                },
                "published_access_facts": fact_groups,
                "source_visit_calendar": market_visit_calendar.build(fact_groups),
                "parking": None,
                "opening_hours_imported": False,
                "driving_evidence_sha256": check["sha256"],
                "driving_checked_at": check["retrieved_at"],
                "driving_snap_distance_m": distance,
                "driving_road": check["road_name"],
                "limitations": "Dated market registry and season evidence. Markets operate only on published market days/times; scheduler hours, prices, parking, current market-day vehicle entry, future operation and availability remain unknown. Road proximity does not establish a parking entrance.",
            }
        ]
        rows.append(row)
        regions[row["region"]] += 1
    reject_collisions(rows)
    return rows, {
        "scanned": len(native),
        "accepted": len(rows),
        "bytes": size + len(raw) + len(inventory_raw),
        "duplicates": 0,
        "rejects": dict(rejects),
        "regions": dict(regions),
        "categories": {"food_destination": len(rows), "daytime": len(rows)},
        "unselected_source_records": len(native) - len(rows),
        "visit_calendars": {
            "supported": sum(
                not row["provenance"][0]["source_visit_calendar"]["unknown_reasons"] for row in rows
            ),
            "unknown": sum(
                bool(row["provenance"][0]["source_visit_calendar"]["unknown_reasons"])
                for row in rows
            ),
            "records": [
                {
                    "source_id": row["source_id"],
                    "unknown_reasons": row["provenance"][0]["source_visit_calendar"][
                        "unknown_reasons"
                    ],
                    "weekly_windows": len(
                        row["provenance"][0]["source_visit_calendar"]["weekly_windows"]
                    ),
                }
                for row in rows
            ],
        },
    }
