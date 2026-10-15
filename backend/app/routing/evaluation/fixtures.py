"""Fail-closed immutable evidence loader; no capture or provider fallback."""

import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.models.routing_models.routing_models import MapBox
from app.models.trip_limits import MAPBOX_MAX_COORDINATES
from app.routing.cp_sat_selection import valid_coordinates
from app.routing.evaluation.evidence import (
    EvidenceReference,
    RatingCapture,
    ReviewLedger,
    RightsEvidence,
    RoutingCapture,
)
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
    schema_version: int = Field(strict=True, ge=1, le=2)
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
    access_review_file: str | None = None
    hotel_rating_capture: dict | None = None


class RealManifest(Manifest):
    schema_version: Literal[2]
    evidence_type: Literal[
        "catalog_selection_with_captured_measurements", "catalog_recorded_pipeline"
    ]
    catalog_generation: str = Field(min_length=1)
    catalog_release: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    rights_evidence: str = Field(min_length=1)
    access_review_file: str = Field(min_length=1)
    rating_capture: RatingCapture
    routing_capture: RoutingCapture
    hotel_rating_capture: RatingCapture | None = None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def strict_json(content):
    def reject(value):
        raise EvidenceError(f"non-finite JSON number: {value}")

    def number(value):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else reject(value)

    return json.loads(content, parse_constant=reject, parse_float=number)


def route_key(coordinates):
    """Exact [lat, lon] request order, including endpoints; never round signatures."""
    return fingerprint(coordinates)


def validate_route(raw, coordinates=None):
    for point in (raw.get("geometry") or {}).get("coordinates", []):
        if not isinstance(point, list) or not valid_coordinates(point[::-1]):
            raise EvidenceError("invalid raw route coordinates")
    for segment in [
        raw,
        *raw.get("legs", []),
        *(step for leg in raw.get("legs", []) for step in leg.get("steps", [])),
    ]:
        if any(
            not finite(segment.get(field)) or segment[field] < 0
            for field in ("duration", "distance")
        ):
            raise EvidenceError("invalid raw route duration/distance")
    route = MapBox.MapBox_Route.model_validate(raw)
    if not route.geometry or len(route.geometry.coordinates) < 2:
        raise EvidenceError("route geometry missing")
    for point in route.geometry.coordinates:
        if not valid_coordinates(point[::-1]):
            raise EvidenceError("invalid route geometry coordinates")
    if coordinates is not None:
        if len(coordinates) > MAPBOX_MAX_COORDINATES:
            raise EvidenceError("captured route exceeds single-request transport capacity")
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
        manifest_raw = strict_json(manifest_bytes)
        self.manifest = Manifest.model_validate(manifest_raw)
        m = self.manifest
        if m.evidence_type != "synthetic_unit_only":
            validated = RealManifest.model_validate(manifest_raw)
            self.manifest = Manifest.model_validate(validated.model_dump(mode="json"))
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
        if m.evidence_type != "synthetic_unit_only" and (
            (m.evidence_type == "catalog_recorded_pipeline") != (m.coverage == "recorded_pipeline")
        ):
            raise EvidenceError("real evidence type and coverage must agree")
        loaded = {}
        for name, digest in m.files.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or path == root or not path.is_file():
                raise EvidenceError("fixture file escaped its immutable directory or is missing")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise EvidenceError(f"SHA-256 mismatch: {name}")
            loaded[name] = strict_json(content)
        if "data.json" not in loaded:
            raise EvidenceError("manifest must hash data.json")
        self.data = loaded["data.json"]
        self.loaded_files = loaded
        self.hash = fingerprint(
            {"manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "files": m.files}
        )
        data = self.data
        self.baseline = validate_route(data["baseline_route"])
        real = m.evidence_type != "synthetic_unit_only"
        reviews = {}
        if real:
            if m.schema_version != 2:
                raise EvidenceError("real fixtures require reviewed v2 evidence")
            rating = RatingCapture.model_validate(m.rating_capture)
            routing = RoutingCapture.model_validate(m.routing_capture)
            if (
                rating.captured_at > clock
                or routing.captured_at > clock
                or routing.departure_context != departure
            ):
                raise EvidenceError(
                    "capture date/context disagrees with evaluation clock/departure"
                )
            if m.access_review_file not in loaded or m.rights_evidence not in loaded:
                raise EvidenceError("hashed review ledger and rights evidence required")
            ledger = ReviewLedger.model_validate(loaded[m.access_review_file])
            reviews = ledger.approved(m.catalog_generation, m.catalog_release, clock, departure)
            rights = RightsEvidence.model_validate(loaded[m.rights_evidence])
            if (rights.catalog_generation, rights.catalog_release, rights.attribution) != (
                m.catalog_generation,
                m.catalog_release,
                m.attribution,
            ):
                raise EvidenceError("rights evidence generation/release/attribution mismatch")
            if not rights.reviewed_at.tzinfo or rights.reviewed_at > clock:
                raise EvidenceError("rights review must predate evaluation clock")
            baseline_key = route_key(
                [
                    data["baseline_route"]["geometry"]["coordinates"][0][::-1],
                    data["baseline_route"]["geometry"]["coordinates"][-1][::-1],
                ]
            )
            baseline_record = data.get("routes", {}).get(baseline_key)
            if not baseline_record or fingerprint(baseline_record["response"]) != fingerprint(
                data["baseline_route"]
            ):
                raise EvidenceError("baseline requires its exact recorded request/response")
        self.reviews = reviews
        ids = set()
        for item in data["attractions"]:
            key = item["provider_id"]
            if not isinstance(key, str) or not key or key in ids:
                raise EvidenceError("duplicate or empty attraction ID")
            ids.add(key)
            if not isinstance(item["name"], str) or not item["name"].strip():
                raise EvidenceError("empty original attraction name")
            if real:
                review = reviews.get(key)
                if review is None or (
                    reason := review.rejection(item["coordinates"], clock, departure)
                ):
                    raise EvidenceError(
                        f"attraction access review failed: {key}: {reason if review else 'missing_review'}"
                    )
                if (
                    item.get("source_generation") != m.catalog_generation
                    or item.get("source_attribution") != m.attribution
                ):
                    raise EvidenceError("attraction generation/attribution mismatch")
                if item.get("rating_capture_id") != rating.capture_id:
                    raise EvidenceError("attraction rating capture mismatch")
                for reference in item.get("evidence_references", []):
                    EvidenceReference.model_validate(reference)
                if not item.get("evidence_references"):
                    raise EvidenceError("attraction evidence references missing")
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
            if real and record.get("capture_id") != routing.capture_id:
                raise EvidenceError("recorded road capture identity mismatch")
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
        hotel_capture = (
            RatingCapture.model_validate(m.hotel_rating_capture)
            if real and data.get("hotel_offers")
            else None
        )
        if hotel_capture and hotel_capture.captured_at > clock:
            raise EvidenceError("hotel ratings captured after evaluation clock")
        for hotel in data.get("hotel_offers", []):
            AttributeRatings.model_validate(hotel.get("attribute_ratings", {}))
            if real and hotel.get("rating_capture_id") != hotel_capture.capture_id:
                raise EvidenceError("hotel rating capture mismatch")
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

    def require_access_until(self, through_date):
        for item in self.data["attractions"]:
            review = self.reviews.get(item["provider_id"])
            if review is not None and review.valid_through < through_date:
                raise EvidenceError("access review expires before the evaluated trip horizon")
