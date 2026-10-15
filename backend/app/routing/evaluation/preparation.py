"""Read-only local export, deterministic sampling and frozen production shortlists."""

import asyncio
import copy
import hashlib
import json
import math
import os
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.routing.discovery import balanced_pool, make_discovery_plan
from app.routing.evaluation.evidence import (
    CatalogExport,
    ReviewLedger,
    RightsEvidence,
    source_metadata,
)
from app.routing.evaluation.fixtures import EvidenceError, Fixture, strict_json, validate_route
from app.routing.evaluation.network import no_network
from app.routing.evaluation.offline import FrozenProviders
from app.routing.evaluation.scenarios import Scenario
from app.routing.geometry import RouteMeasure
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.run_metrics import fingerprint
from app.routing.sources.persona_candidates import VerifiedPlace


def read_json(path):
    content = Path(path).read_bytes()
    return strict_json(content), hashlib.sha256(content).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)  # atomic install that refuses an existing output
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_reviewed(catalog, reviews, rights, output, clock, departure, *, unit_only=False):
    """Consume the owner's local exchange; never read/mutate a live catalog."""
    source, source_hash = read_json(catalog)
    ledger_raw, ledger_hash = read_json(reviews)
    rights_raw, rights_hash = read_json(rights)
    CatalogExport.model_validate(source)
    ledger = ReviewLedger.model_validate(ledger_raw)
    approved_rights = RightsEvidence.model_validate(rights_raw)
    clock, departure = datetime.fromisoformat(clock), datetime.fromisoformat(departure)
    if not clock.tzinfo or not departure.tzinfo or clock >= departure:
        raise EvidenceError("aware frozen clock must precede departure")
    generation, release = source["catalog_generation"], source["catalog_release"]
    if source.get("evidence_type") == "synthetic_unit_only" and not unit_only:
        raise EvidenceError("synthetic exchange requires unit-only mode")
    if (
        approved_rights.catalog_generation,
        approved_rights.catalog_release,
        approved_rights.attribution,
    ) != (generation, release, source["attribution"]):
        raise EvidenceError("rights evidence does not match the export generation")
    if not approved_rights.reviewed_at.tzinfo or approved_rights.reviewed_at > clock:
        raise EvidenceError("rights review must predate evaluation clock")
    by_id = ledger.approved(generation, release, clock, departure)
    records, exclusions, seen = [], [], set()
    for item in source["records"]:
        place = VerifiedPlace.model_validate(item)
        key = place.provider_id
        if key in seen:
            raise EvidenceError("duplicate export identity")
        seen.add(key)
        review = by_id.get(key)
        reason = (
            review.rejection(place.coordinates, clock, departure) if review else "missing_review"
        )
        if reason:
            exclusions.append({"provider_id": key, "reason": reason})
            continue
        leaf_release, leaf_attribution = source_metadata(
            place.source, release, source["attribution"], source.get("source_catalogs", {})
        )
        if (
            place.source_release != leaf_release
            or place.source_attribution != leaf_attribution
            or not place.source_provenance
        ):
            raise EvidenceError("approved source record lacks matching provenance")
        records.append({**item, **place.model_dump(), "source_generation": generation})
    result = {
        "schema_version": 1,
        "evidence_type": source.get("evidence_type", "catalog_reviewed_export"),
        "catalog_generation": generation,
        "catalog_release": release,
        "attribution": source["attribution"],
        "source_catalogs": source.get("source_catalogs", {}),
        "evaluation_clock": clock.isoformat(),
        "departure": departure.isoformat(),
        "source_sha256": source_hash,
        "review_ledger_sha256": ledger_hash,
        "access_reviews": ledger_raw,
        "rights_evidence": rights_raw,
        "rights_sha256": rights_hash,
        "records": sorted(records, key=lambda item: item["provider_id"]),
        "exclusions": exclusions,
        "counts": {
            "source": len(source["records"]),
            "approved": len(records),
            "excluded": len(exclusions),
        },
    }
    write_new(output, result)
    return result["counts"]


def sample_corridor(export, baseline, output, *, count=100, seed=1729, unit_only=False):
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
        raise EvidenceError("sample count must be 1..100")
    source, source_hash = read_json(export)
    raw_route, route_hash = read_json(baseline)
    if source.get("evidence_type") == "synthetic_unit_only" and not unit_only:
        raise EvidenceError("synthetic exchange requires unit-only mode")
    ledger = ReviewLedger.model_validate(source["access_reviews"])
    checked = ledger.approved(
        source["catalog_generation"],
        source["catalog_release"],
        datetime.fromisoformat(source["evaluation_clock"]),
        datetime.fromisoformat(source["departure"]),
    )
    for item in source["records"]:
        review = checked.get(item["provider_id"])
        if review is None or review.rejection(
            item["coordinates"],
            datetime.fromisoformat(source["evaluation_clock"]),
            datetime.fromisoformat(source["departure"]),
        ):
            raise EvidenceError("reviewed export contains unapproved records")
    route = validate_route(raw_route)
    measure = RouteMeasure(route)
    section_count = min(12, max(1, math.ceil(route.duration / 7200)))
    buckets = defaultdict(lambda: defaultdict(list))
    outside = []
    for item in source["records"]:
        projection = measure.project(item["coordinates"])
        if projection["distance_meters"] > 5 * 1609.344:
            outside.append(item["provider_id"])
            continue
        section = (
            min(
                section_count - 1,
                int(projection["route_progress_seconds"] * section_count / route.duration),
            )
            if route.duration
            else 0
        )
        category = (item.get("categories") or ["uncategorized"])[0]
        buckets[section][category].append({**item, **projection, "section_id": section})
    ranked = []
    for section, categories in sorted(buckets.items()):
        for values in categories.values():
            values.sort(
                key=lambda item: (fingerprint([seed, item["provider_id"]]), item["provider_id"])
            )
        variety = []
        while any(categories.values()):
            for category in sorted(categories):
                if categories[category]:
                    variety.append(categories[category].pop(0))
        ranked.extend({**item, "variety_order": i} for i, item in enumerate(variety))
    selected = balanced_pool(
        ranked, count, section_count, lambda item: (item["variety_order"], item["provider_id"])
    )
    result = {
        "schema_version": 1,
        "status": "ready" if len(selected) == count else "insufficient_real_fixture_coverage",
        "evidence_type": source["evidence_type"],
        "catalog_generation": source["catalog_generation"],
        "catalog_release": source["catalog_release"],
        "source_catalogs": source.get("source_catalogs", {}),
        "source_export_sha256": source_hash,
        "baseline_sha256": route_hash,
        "baseline_model_hash": fingerprint(raw_route),
        "seed": seed,
        "requested_count": count,
        "available_corridor_count": len(ranked),
        "selected_count": len(selected),
        "selected_ids": [item["provider_id"] for item in selected],
        "selected_records": selected,
        "section_counts": dict(Counter(item["section_id"] for item in selected)),
        "outside_corridor_ids": outside,
    }
    write_new(output, result)
    return {key: result[key] for key in ("status", "selected_count", "available_corridor_count")}


def install_bundle(output, manifest, files, *, unit_only=False):
    """Validate the entire new directory before making it visible; never overwrite."""
    output = Path(output)
    if output.exists():
        raise EvidenceError("immutable fixture output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fixture-prepare-", dir=output.parent) as temp:
        staged = Path(temp) / "bundle"
        staged.mkdir()
        manifest = copy.deepcopy(manifest)
        manifest["files"] = {}
        for name, value in files.items():
            target = staged / name
            if not target.resolve().is_relative_to(staged.resolve()):
                raise EvidenceError("unsafe evidence file path")
            write_new(target, value)
            manifest["files"][name] = hashlib.sha256(target.read_bytes()).hexdigest()
        write_new(staged / "manifest.json", manifest)
        validated = Fixture(staged, allow_synthetic=unit_only)
        result = {"fixture_hash": validated.hash, "count": validated.manifest.attraction_count}
        staged.rename(output)
    return result


def assemble(capture_directory, sample, output, *, unit_only=False):
    """Select existing capture bytes; no rating, road or approval is generated."""
    root = Path(capture_directory).resolve()
    manifest, _ = read_json(root / "manifest.json")
    selection, _ = read_json(sample)
    if (
        selection["status"] != "ready"
        or len(selection["selected_ids"]) != selection["requested_count"]
    ):
        raise EvidenceError("cannot assemble an insufficient-coverage sample")
    if (manifest["catalog_generation"], manifest["catalog_release"]) != (
        selection["catalog_generation"],
        selection["catalog_release"],
    ):
        raise EvidenceError("sample and capture generation mismatch")
    files = {}
    for name, digest in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise EvidenceError("unsafe capture path")
        value, actual = read_json(path)
        if actual != digest:
            raise EvidenceError("capture file hash mismatch")
        files[name] = value
    data = files["data.json"]
    if fingerprint(data["baseline_route"]) != selection["baseline_model_hash"]:
        raise EvidenceError("sample baseline mismatch")
    if fingerprint(manifest.get("source_catalogs", {})) != fingerprint(
        selection.get("source_catalogs", {})
    ):
        raise EvidenceError("sample and capture source_catalogs mismatch")
    by_id = {item["provider_id"]: item for item in data["attractions"]}
    wanted = set(selection["selected_ids"])
    for selected in selection["selected_records"]:
        item = by_id.get(selected["provider_id"])
        if item is None or (item["name"], item["coordinates"]) != (
            selected["name"],
            selected["coordinates"],
        ):
            raise EvidenceError("captured identity/arrival coordinates disagree with sample")
    data["attractions"] = [by_id[key] for key in selection["selected_ids"]]
    data["sampling"] = {key: value for key, value in selection.items() if key != "selected_records"}
    keep = {
        data["origin_id"],
        data["destination_id"],
        *(item["provider_id"] for item in data.get("hotel_offers", [])),
        *wanted,
    }
    indices = [i for i, node in enumerate(data["nodes"]) if node["id"] in keep]
    data["nodes"] = [data["nodes"][i] for i in indices]
    for name in ("travel_time_seconds", "travel_distance_meters"):
        if data.get(name) is not None:
            data[name] = [[data[name][i][j] for j in indices] for i in indices]
    data["production_shortlists"] = {}
    if selection["evidence_type"] == "synthetic_unit_only":
        manifest["evidence_type"] = "synthetic_unit_only"
    manifest["attraction_count"] = len(wanted)
    manifest["sampling_seed"] = selection["seed"]
    manifest.pop("baseline_sha256", None)
    return install_bundle(output, manifest, files, unit_only=unit_only)


def freeze_shortlists(directory, scenarios, output, *, unit_only=False):
    fixture = Fixture(directory, allow_synthetic=unit_only)
    files = copy.deepcopy(fixture.loaded_files)
    saved = {}

    async def freeze():
        provider = FrozenProviders(fixture)
        for raw in scenarios:
            scenario = Scenario.model_validate(raw)
            if scenario.fixture != fixture.manifest.fixture_id:
                continue
            if (
                fixture.manifest.endpoints
                != [scenario.inputs.start_id, scenario.inputs.destination_id]
                or fixture.manifest.departure != scenario.departure().isoformat()
                or fixture.manifest.evaluation_clock != scenario.evaluation_clock.isoformat()
            ):
                raise EvidenceError("shortlist scenario does not match captured endpoints/date")
            fixture.require_access_until(
                scenario.departure().date() + timedelta(days=scenario.target_days - 1)
            )
            plan = make_discovery_plan(fixture.baseline, scenario.inputs.num_stops)
            discovered = await provider.candidates(
                fixture.baseline, plan, scenario.inputs.persona_weights
            )
            checked = await CPSatPlanner._verify_detours(
                fixture.baseline, discovered.candidates, provider.services()
            )
            saved[scenario.id] = [item["provider_id"] for item in checked]

    with no_network():
        asyncio.run(freeze())
    if not saved:
        raise EvidenceError("no matching scenarios to freeze")
    files["data.json"]["production_shortlists"] = saved
    return install_bundle(output, fixture.manifest.model_dump(), files, unit_only=unit_only)
