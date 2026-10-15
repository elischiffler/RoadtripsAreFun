"""Fail-closed immutable evidence loader; no capture or provider fallback."""

import hashlib
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.models.routing_models.routing_models import MapBox
from app.routing.cp_sat_selection import valid_coordinates
from app.routing.profiles import AttributeRatings
from app.routing.run_metrics import fingerprint

EVIDENCE_TYPES = {
    "synthetic_unit_only",
    "catalog_selection_with_captured_measurements",
    "catalog_recorded_pipeline",
}


class EvidenceError(ValueError):
    pass


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(strict=True, ge=1, le=1)
    fixture_id: str
    evidence_type: str
    coverage: str
    files: dict[str, str]
    attraction_count: int = Field(strict=True, ge=0, le=100)
    catalog_generation: str | None
    catalog_release: str | None
    attribution: str | None
    rights_evidence: str | None
    rating_capture: dict
    routing_capture: dict
    departure: str
    evaluation_clock: str
    endpoints: list[str]
    sampling_seed: int = 1729
    tzdata_version: str
    limitations: list[str] = []


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def route_key(coordinates):
    """Exact [lat, lon] request order, including endpoints; never round signatures."""
    return fingerprint(coordinates)


def validate_route(raw, coordinates=None):
    route = MapBox.MapBox_Route.model_validate(raw)
    if not route.geometry or len(route.geometry.coordinates) < 2:
        raise EvidenceError("route geometry missing")
    for point in route.geometry.coordinates:
        if not valid_coordinates(point[::-1]):
            raise EvidenceError("invalid route geometry coordinates")
    if coordinates is not None:
        if len(route.legs) != len(coordinates) - 1:
            raise EvidenceError("final route leg count does not match request")
        if (
            route.geometry.coordinates[0][::-1] != coordinates[0]
            or route.geometry.coordinates[-1][::-1] != coordinates[-1]
        ):
            raise EvidenceError("recorded endpoints do not match request")
    for field in ("duration", "distance"):
        values = [getattr(route, field), *(getattr(leg, field) for leg in route.legs)]
        if not route.legs or any(not finite(v) or v < 0 for v in values):
            raise EvidenceError("invalid measured driving duration/distance")
        if not math.isclose(values[0], sum(values[1:]), abs_tol=0.01):
            raise EvidenceError("route total disagrees with final legs")
    return route


class Fixture:
    def __init__(self, directory, *, allow_synthetic=False):
        root = Path(directory).resolve()
        manifest_bytes = (root / "manifest.json").read_bytes()
        self.manifest = Manifest.model_validate_json(manifest_bytes)
        m = self.manifest
        if m.evidence_type not in EVIDENCE_TYPES or m.coverage not in {
            "selection_only",
            "recorded_pipeline",
        }:
            raise EvidenceError("unknown evidence layer")
        if m.evidence_type == "synthetic_unit_only" and not allow_synthetic:
            raise EvidenceError("synthetic fixtures are allowed only by explicit unit-test mode")
        if m.evidence_type != "synthetic_unit_only" and not all(
            (m.catalog_generation, m.catalog_release, m.attribution, m.rights_evidence)
        ):
            raise EvidenceError(
                "real catalog generation, release, attribution and rights evidence required"
            )
        departure, clock = (
            datetime.fromisoformat(m.departure),
            datetime.fromisoformat(m.evaluation_clock),
        )
        if not departure.tzinfo or not clock.tzinfo or departure <= clock:
            raise EvidenceError("capture requires an aware clock before departure")
        if not m.rating_capture or not m.routing_capture or len(m.endpoints) != 2:
            raise EvidenceError("capture identities and two endpoint IDs required")
        if (
            m.coverage == "recorded_pipeline"
            and m.evidence_type == "catalog_selection_with_captured_measurements"
        ):
            raise EvidenceError("selection evidence cannot claim full pipeline coverage")
        loaded = {}
        for name, digest in m.files.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or path == root or not path.is_file():
                raise EvidenceError("fixture file escaped its immutable directory or is missing")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise EvidenceError(f"SHA-256 mismatch: {name}")
            loaded[name] = json.loads(content)
        if "data.json" not in loaded:
            raise EvidenceError("manifest must hash data.json")
        self.data = loaded["data.json"]
        self.hash = fingerprint(
            {"manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "files": m.files}
        )
        data = self.data
        self.baseline = validate_route(data["baseline_route"])
        ids, names = set(), set()
        for item in data["attractions"]:
            key = item["provider_id"]
            if not isinstance(key, str) or not key or key in ids:
                raise EvidenceError("duplicate or empty attraction ID")
            ids.add(key)
            name = " ".join(re.findall(r"\w+", item["name"].casefold()))
            if not name or name in names:
                raise EvidenceError("ambiguous captured attraction name")
            names.add(name)
            if not valid_coordinates(item["coordinates"]):
                raise EvidenceError("malformed attraction coordinates")
            AttributeRatings.model_validate(item["attribute_ratings"])
            progress, detour = item["route_progress_seconds"], item["detour_seconds"]
            if (
                not finite(progress)
                or not 0 <= progress <= self.baseline.duration
                or not finite(detour)
                or detour < 0
            ):
                raise EvidenceError("invalid baseline progress or measured solo detour")
            if m.evidence_type != "synthetic_unit_only" and (
                item.get("source_release") != m.catalog_release or not item.get("source_provenance")
            ):
                raise EvidenceError("attraction lacks generation-aligned provenance")
            if not item.get("solo_route_key") or item["solo_route_key"] not in data.get(
                "routes", {}
            ):
                raise EvidenceError("captured solo road evidence missing")
        if len(ids) != m.attraction_count:
            raise EvidenceError("manifest attraction count mismatch")
        nodes = data["nodes"]
        node_ids = [node["id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)) or not ids.issubset(node_ids):
            raise EvidenceError("routing node order duplicates or misses attractions")
        for node in nodes:
            if not valid_coordinates(node["coordinates"]):
                raise EvidenceError("invalid routing node")
            ZoneInfo(node["timezone"])
        if data["origin_id"] not in node_ids or data["destination_id"] not in node_ids:
            raise EvidenceError("missing endpoint routing nodes")
        self.nodes = {node["id"]: node for node in nodes}
        origin, end = (self.nodes[data[k]]["coordinates"] for k in ("origin_id", "destination_id"))
        if (
            self.baseline.geometry.coordinates[0][::-1] != origin
            or self.baseline.geometry.coordinates[-1][::-1] != end
        ):
            raise EvidenceError("baseline endpoint/node mismatch")
        for key, record in data.get("routes", {}).items():
            coordinates = record["request_coordinates"]
            if key != route_key(coordinates) or any(not valid_coordinates(c) for c in coordinates):
                raise EvidenceError("recorded route request signature mismatch")
            validate_route(record["response"], coordinates)
        for item in data["attractions"]:
            record = data["routes"][item["solo_route_key"]]
            if record["request_coordinates"] != [origin, item["coordinates"], end]:
                raise EvidenceError("solo-route identity mismatch")
            raw_detour = record["response"]["duration"] - self.baseline.duration
            if not math.isclose(item["detour_seconds"], max(0, raw_detour), abs_tol=0.01):
                raise EvidenceError("solo detour disagrees with captured route")
        for shortlist in data.get("production_shortlists", {}).values():
            if (
                len(shortlist) > 60
                or len(shortlist) != len(set(shortlist))
                or not set(shortlist).issubset(ids)
            ):
                raise EvidenceError("invalid frozen production shortlist")
        for field in ("travel_time_seconds", "travel_distance_meters"):
            matrix = data.get(field)
            if matrix is None:
                continue
            if len(matrix) != len(nodes) or any(len(row) != len(nodes) for row in matrix):
                raise EvidenceError("matrix/node-order dimensions mismatch")
            for i, row in enumerate(matrix):
                for j, value in enumerate(row):
                    if (i == j and value != 0) or (
                        value is not None and (not finite(value) or value < 0)
                    ):
                        raise EvidenceError(
                            "matrix must retain directed measured values or unreachable nulls"
                        )
        for lookup in data.get("timezone_lookups", []):
            if not valid_coordinates(lookup["coordinates"]):
                raise EvidenceError("invalid captured timezone query")
            ZoneInfo(lookup["timezone"])
        times, distances = data.get("travel_time_seconds"), data.get("travel_distance_meters")
        if (times is None) != (distances is None):
            raise EvidenceError("matrix durations and distances must be supplied together")
        if times is not None and any(
            (t is None) != (d is None) for tr, dr in zip(times, distances) for t, d in zip(tr, dr)
        ):
            raise EvidenceError("unreachable time/distance cells disagree")
        for hotel in data.get("hotel_offers", []):
            date.fromisoformat(hotel["check_in_date"])
            if hotel.get("price_scope") not in {
                "one_room_one_night_including_taxes_fees",
                "independent_room_quotes_not_combined_inventory",
            }:
                raise EvidenceError("hotel quotes require declared USD room-night tax/fee scope")
            if hotel.get("currency") != "USD":
                raise EvidenceError("hotel quotes must be captured in USD")
            if (
                hotel["provider_id"] not in self.nodes
                or hotel["coordinates"] != self.nodes[hotel["provider_id"]]["coordinates"]
            ):
                raise EvidenceError("hotel/node mismatch")
            if not finite(hotel["price"]) or hotel["price"] < 0:
                raise EvidenceError("invalid hotel quote")
            # Incomplete evidence is retained as a declared gate; never zero-fill.
            offers = hotel.get("room_offers", [])
            if any(not finite(o.get("price")) or o["price"] < 0 for o in offers):
                raise EvidenceError("invalid room-night quote")
            for index, offer in enumerate(offers):
                if (
                    offer.get("check_in_date") != hotel["check_in_date"]
                    or offer.get("price_scope") != "one_room_one_night_including_taxes_fees"
                ):
                    raise EvidenceError("room quote date/tax scope disagrees with requested night")
                if (
                    index >= len(hotel.get("hotel_rooms", []))
                    or offer.get("room") != hotel["hotel_rooms"][index]
                ):
                    raise EvidenceError("room quote occupancy disagrees with allocation")
            if offers and not math.isclose(
                sum(o["price"] for o in offers), hotel["price"], abs_tol=0.01
            ):
                raise EvidenceError("room quotes disagree with hotel total")
