"""Inspected Kaggle LOC metadata with independently reviewed roadside arrivals.

The first explicit site profile is Corn Palace. Original photographs and website
prose are not imported. A licensed Overture venue point must match the current
published visitor address and a retained driving-frontage check. No coordinates
or categories are inferred from an old photograph alone. No network/database I/O.
"""

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lxml import html

SCHEMA = "kaggle-loc-roadside-arrivals/1"
SOURCE_URL = (
    "https://www.kaggle.com/datasets/headsortails/us-roadside-attractions-photographs/versions/4"
)
CSV_SHA256 = "f0f3452e84c40d8cf05d35a7750ca1ac308f91f3dc9fe5e59e95abda14bd887a"
CSV_ROWS = 11_710
RELEASE = "2026-09-23.1"
POINT_SOURCE = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/"
RIGHTS_URL = "https://guides.loc.gov/ld.php?content_id=76336558"
VISIT_URL = "https://www.cornpalace.com/31/Visiting"
PARKING_URL = "https://www.cornpalace.com/173/Parking"
ATTRIBUTION = "Kaggle roadside metadata v4 by Heads or Tails (CC0); Library of Congress, Prints & Photographs Division, John Margolies archive; licensed Overture arrival facts. No photographs imported."
CLOSURE = re.compile(
    r"\b(temporarily closed|permanently closed|closed until further notice|closed indefinitely)\b",
    re.I,
)


def compact(value):
    text = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in text if c.isalnum())


def checked_time(value):
    checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if checked.tzinfo is None or not datetime.now(UTC) - timedelta(
        days=30
    ) <= checked <= datetime.now(UTC):
        raise ValueError("roadside evidence must be dated within 30 days")
    return checked.isoformat()


def retained(evidence, *, url=None, ceiling=2 * 1024 * 1024):
    if url and evidence.get("url") != url:
        raise ValueError("roadside evidence URL differs from the reviewed publisher")
    checked_time(evidence["retrieved_at"])
    path = Path(evidence["path"])
    if not path.is_file() or not 0 < path.stat().st_size <= ceiling:
        raise ValueError("roadside evidence missing or oversized")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
        raise ValueError("roadside evidence checksum mismatch")
    return raw


def text(raw):
    document = html.fromstring(raw)
    for element in document.xpath("//script|//style"):
        element.drop_tree()
    return " ".join(document.text_content().split())


def rights(raw):
    # One unrelated publisher row has an invalid UTF-8 byte. Preserve it rather
    # than substituting/deleting bytes; require strict UTF-8 in the selected row.
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="surrogateescape")))
    selected = []
    for count, row in enumerate(reader, 1):
        if count > 2000:
            raise ValueError("LOC rights table row ceiling exceeded")
        if row.get("id") == "723_marg.html":
            selected.append(row)
    if len(selected) != 1:
        raise ValueError("LOC archive rights statement missing or ambiguous")
    row = selected[0]
    for value in row.values():
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
    publication = text(row.get("publication", ""))
    if (
        row.get("title") != "John Margolies Roadside America Photograph Archive"
        or "Library of Congress purchased the intellectual property rights" not in publication
        or "no known copyright restrictions" not in publication
        or "sculpture or other works of art" not in publication
    ):
        raise ValueError("LOC archive rights statement requires renewed review")


def prepare(path, manifest, *, max_rows, max_bytes):
    from app.catalog.ingest import provenance_licenses

    if (
        manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(r"kaggle-loc-v4\+review-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
    ):
        raise ValueError("roadside manifest requires the inspected v4 intake and dated review")
    path = Path(path)
    raw = path.read_bytes() if 0 < path.stat().st_size <= 32_768 else b""
    if not raw or hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise ValueError("roadside bundle checksum/size mismatch")
    bundle = json.loads(raw)
    # Expanding this explicit site profile requires actual archive/access review.
    if bundle.get("profile") != "corn-palace/1" or max_rows < 1:
        raise ValueError("unreviewed roadside site profile")
    archive = bundle["archive"]
    if archive.get("sha256") != CSV_SHA256:
        raise ValueError("roadside CSV differs from the inspected Kaggle v4 member")
    csv_raw = retained(archive)
    reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig")))
    if set(reader.fieldnames or []) != {"index", "title", "year", "image", "image_link"}:
        raise ValueError("unexpected roadside metadata schema")
    matches, count = [], 0
    for count, photo in enumerate(reader, 1):
        if count > CSV_ROWS:
            raise ValueError("roadside metadata row ceiling exceeded")
        title = photo["title"].casefold()
        if (
            title.startswith("corn palace,") or title.startswith("mitchell corn palace,")
        ) and title.endswith("mitchell, south dakota"):
            matches.append(photo)
    if count != CSV_ROWS or not matches or min(int(p["index"]) for p in matches) != 279:
        raise ValueError("roadside archive identity/count mismatch")
    rights_raw = retained(bundle["rights"], url=RIGHTS_URL)
    rights(rights_raw)
    point_raw = retained(bundle["points"], url=POINT_SOURCE)
    features = [json.loads(line) for line in point_raw.splitlines()]
    if len(features) > 10:
        raise ValueError("roadside point-review ceiling exceeded")
    chosen = [f for f in features if f.get("properties", {}).get("id") == bundle.get("point_id")]
    if len(chosen) != 1:
        raise ValueError("roadside venue point missing or ambiguous")
    feature = chosen[0]
    p = feature["properties"]
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    if (
        geometry.get("type") != "Point"
        or not isinstance(coords, list)
        or len(coords) != 2
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in coords
        )
    ):
        raise ValueError("roadside requires an actual finite licensed point")
    lon, lat = coords
    if not (43.70 <= lat <= 43.73 and -98.04 <= lon <= -98.01):
        raise ValueError("roadside point is outside the reviewed Mitchell venue area")
    address = next(
        (a for a in p.get("addresses", []) if a.get("country") == "US" and a.get("region") == "SD"),
        {},
    )
    if (
        p.get("names", {}).get("primary") != "The World's Only Corn Palace"
        or compact(address.get("freeform", "")) != "604nmainst"
        or address.get("locality") != "Mitchell"
        or address.get("postcode") != "57301"
        or p.get("operating_status") != "open"
        or isinstance(p.get("confidence"), bool)
        or not isinstance(p.get("confidence"), (int, float))
        or not math.isfinite(p["confidence"])
        or p["confidence"] < 0.9
    ):
        raise ValueError("roadside point does not match the actual public visitor venue")
    provenance = [
        {
            k: s[k]
            for k in (
                "dataset",
                "record_id",
                "update_time",
                "property",
                "license",
                "provider",
                "resource",
                "version",
            )
            if s.get(k) is not None
        }
        for s in p.get("sources", [])
    ]
    required = provenance_licenses({"provenance": provenance})
    if not required or required - manifest["licenses"].keys():
        raise ValueError("roadside point provenance/license is not admitted")
    visit_raw = retained(bundle["visit"], url=VISIT_URL)
    parking_raw = retained(bundle["parking"], url=PARKING_URL)
    visit, parking = text(visit_raw), text(parking_raw)
    if CLOSURE.search(visit + " " + parking):
        raise ValueError("roadside publisher reports a current closure")
    if (
        "The Corn Palace is open year-round and is free to visit" not in visit
        or "604 North Main Street" not in visit
        or "Mitchell, SD 57301" not in visit
        or "FREE RV/Trailer parking located on 7th and Lawler" not in parking
    ):
        raise ValueError("roadside current visitor address/parking evidence missing")
    driving_raw = retained(bundle["driving"])
    checks = [x for x in json.loads(driving_raw) if x.get("source_id") == p["id"]]
    if len(checks) != 1:
        raise ValueError("roadside driving check missing or ambiguous")
    check = checks[0]
    checked_time(check["checked_at"])
    distance = check.get("snap_distance_m")
    if (
        check.get("http_status") != 200
        or check.get("code") != "Ok"
        or check.get("source_coordinates") != [lat, lon]
        or isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or not 0 <= distance <= 35
        or check.get("road_name") != "North Main Street"
    ):
        raise ValueError("roadside point lacks the reviewed driving frontage")
    size = len(raw) + sum(
        map(len, (csv_raw, rights_raw, point_raw, visit_raw, parking_raw, driving_raw))
    )
    if size > max_bytes:
        raise ValueError("roadside aggregate evidence byte ceiling exceeded")
    provenance += [
        {
            "dataset": "Overture reviewed arrival point",
            "record_id": p["id"],
            "release": RELEASE,
            "source_url": POINT_SOURCE,
            "sha256": bundle["points"]["sha256"],
            "original_category": p.get("basic_category"),
        },
        {
            "dataset": "Kaggle LOC roadside metadata",
            "record_id": "279",
            "alternate_photo_indices": [int(x["index"]) for x in matches if x["index"] != "279"],
            "release": "4",
            "sha256": CSV_SHA256,
            "source_url": SOURCE_URL,
            "license": "CC0-1.0",
            "photo_coordinates_used": False,
        },
        {
            "dataset": "LOC Margolies archive rights statement",
            "record_id": "723_marg.html",
            "source_url": RIGHTS_URL,
            "sha256": bundle["rights"]["sha256"],
            "license": "LicenseRef-LOC-Margolies-Notice",
            "photographs_imported": False,
        },
        {
            "dataset": "Corn Palace official visitor and parking evidence",
            "source_url": VISIT_URL,
            "parking_url": PARKING_URL,
            "snapshot_sha256": [bundle["visit"]["sha256"], bundle["parking"]["sha256"]],
            "checked_at": bundle["visit"]["retrieved_at"],
            "arrival_type": "venue frontage at published visitor address",
            "coordinate_source": "licensed Overture venue point; unchanged",
            "driving_snap_distance_m": distance,
            "driving_road": "North Main Street",
            "primary_category": "roadside",
            "limitations": "Parking may require a short walk. Check dated closures, event restrictions and holiday hours; future opening/parking availability is unknown.",
        },
    ]
    return [
        {
            "source_id": "kaggle-loc:279",
            "name": p["names"]["primary"],
            "latitude": lat,
            "longitude": lon,
            "region": "SD",
            "categories": ["culture", "daytime", "roadside_attraction"],
            "address": "604 N Main St, Mitchell, SD 57301",
            "url": VISIT_URL,
            "source_updated_at": None,
            "provenance": provenance,
        }
    ], {
        "scanned": count,
        "accepted": 1,
        "bytes": size,
        "rejects": {"not_selected_for_current_arrival_review": count - len(matches)},
        "duplicate_photograph_records": len(matches) - 1,
        "primary_categories": {"roadside": 1},
        "regions": {"SD": 1},
    }
