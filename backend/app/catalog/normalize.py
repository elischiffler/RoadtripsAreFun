"""Normalize Overture GeoJSON features without retaining raw source payloads."""

import math
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

US_REGIONS = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
# Deliberately conservative: generic businesses are not road-trip destinations.
FOOD = {"restaurant", "cafe", "coffee_shop", "bakery", "ice_cream_shop", "food_truck"}
CULTURE = {
    "museum",
    "art_museum",
    "history_museum",
    "art_gallery",
    "performing_arts",
    "theater",
    "theatre",
    "historic_site",
    "historical_landmark",
    "monument",
    "public_art",
    "sculpture",
}
NIGHTLIFE = {
    "bar",
    "pub",
    "nightclub",
    "night_club",
    "wine_bar",
    "cocktail_bar",
    "brewery",
    "comedy_club",
}
DAYTIME = {
    "movie_theater",
    "arcade",
    "bowling_alley",
    "escape_room",
    "miniature_golf",
    "park",
    "national_park",
    "state_park",
    "beach",
    "botanical_garden",
    "zoo",
    "aquarium",
    "amusement_park",
    "theme_park",
    "tourist_attraction",
    "landmark",
    "viewpoint",
    "scenic_lookout",
    "nature_reserve",
    "nature_preserve",
    "hiking_trail",
    "trailhead",
    "waterfall",
    "cave",
    "visitor_center",
}
# A point geometry for an area/natural feature can be its centroid, not an
# entrance. No guessed access coordinates or undocumented overrides in v1.
ACCESS_POINT_REQUIRED = {
    "park",
    "national_park",
    "state_park",
    "nature_reserve",
    "nature_preserve",
    "landmark",
    "beach",
    "waterfall",
    "cave",
    "mountain",
    "hiking_trail",
}
POINT_DESTINATIONS = {"visitor_center", "trailhead", "viewpoint", "scenic_lookout"}


def groups_for(labels):
    """Use taxonomy ancestors; never infer eligibility from a place's name."""
    labels = set(labels)
    groups = set()
    if labels & FOOD or any(x.endswith("_restaurant") for x in labels):
        groups.add("food")
    if labels & CULTURE:
        groups.update(("culture", "daytime"))
    if labels & NIGHTLIFE:
        groups.add("nightlife")
    if labels & DAYTIME:
        groups.add("daytime")
    return sorted(groups)


def normalize(feature):
    """Return (compact row, None) or (None, rejection reason)."""
    if not isinstance(feature, dict):
        return None, "shape"
    p = feature.get("properties", feature)
    if not isinstance(p, dict):
        return None, "shape"
    geometry = feature.get("geometry", {})
    if not isinstance(geometry, dict):
        return None, "geometry"
    coords = geometry.get("coordinates", [])
    if not isinstance(coords, list):
        return None, "geometry"
    if geometry.get("type") != "Point" or len(coords) != 2:
        return None, "geometry"
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in coords
    ):
        return None, "coordinates"
    lon, lat = coords
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None, "coordinates"
    addresses = p.get("addresses") or []
    if not isinstance(addresses, list) or any(not isinstance(a, dict) for a in addresses):
        return None, "country_region"
    address = next(
        (
            a
            for a in addresses
            if a.get("country") == "US"
            and isinstance(a.get("region"), str)
            and a.get("region") in US_REGIONS
        ),
        None,
    )
    if address is None:
        return None, "country_region"
    status = p.get("operating_status")
    if status not in (None, "open"):
        return None, "closed_or_uncertain"
    source_id = p.get("id") or feature.get("id")
    names = p.get("names") or {}
    if not isinstance(names, dict):
        return None, "identity"
    name = names.get("primary")
    if (
        not isinstance(source_id, str)
        or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", source_id)
        or not isinstance(name, str)
        or not name.strip()
        or len(name) > 300
    ):
        return None, "identity"
    taxonomy = p.get("taxonomy") or {}
    if not isinstance(taxonomy, dict) or not isinstance(taxonomy.get("hierarchy") or [], list):
        return None, "category"
    labels = [p.get("basic_category"), taxonomy.get("primary")]
    for hierarchy in taxonomy.get("hierarchy") or []:
        labels.extend(hierarchy if isinstance(hierarchy, list) else [hierarchy])
    labels = sorted({x for x in labels if isinstance(x, str) and len(x) <= 100})
    groups = groups_for(labels)
    if not groups:
        return None, "category"
    specific = {
        label
        for label in (p.get("basic_category"), taxonomy.get("primary"))
        if isinstance(label, str)
    }
    if specific & ACCESS_POINT_REQUIRED and not specific & POINT_DESTINATIONS:
        return None, "access_point_required"
    sources = p.get("sources") or []
    if not isinstance(sources, list) or not sources or len(sources) > 20:
        return None, "provenance"
    provenance = []
    for source in sources:
        if not isinstance(source, dict):
            return None, "provenance"
        dataset = source.get("dataset")
        if not isinstance(dataset, str) or not dataset.strip() or len(dataset) > 200:
            return None, "provenance"
        provenance.append(
            {
                key: str(source[key])[:300]
                for key in (
                    "dataset",
                    "record_id",
                    "update_time",
                    "property",
                    "license",
                    "provider",
                    "resource",
                    "version",
                )
                if source.get(key) is not None
            }
        )
    websites = p.get("websites") or []
    if not isinstance(websites, list):
        return None, "website"
    url = next(
        (
            u
            for u in websites
            if isinstance(u, str)
            and len(u) <= 2000
            and urlparse(u).scheme in ("http", "https")
            and urlparse(u).netloc
        ),
        None,
    )
    updates = []
    for source in provenance:
        if "update_time" in source:
            try:
                date = datetime.fromisoformat(source["update_time"].replace("Z", "+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                updates.append(date.astimezone(UTC).isoformat())
            except ValueError:
                return None, "evidence_date"
    return {
        "source_id": source_id,
        "name": name.strip(),
        "latitude": lat,
        "longitude": lon,
        "region": address["region"],
        "categories": sorted(set(labels + groups)),
        "address": ", ".join(
            str(address[k])
            for k in ("freeform", "locality", "region", "postcode")
            if address.get(k)
        )[:1000]
        or None,
        "url": url,
        "source_updated_at": max(updates) if updates else None,
        "provenance": provenance,
    }, None
