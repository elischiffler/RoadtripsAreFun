"""Source-attributed scheduling holds without removing places or inventing clocks.

Reviewed selections identify the relevant native facilities and parking lots.
This offline builder verifies their retained bytes and identities, retains the
existing calendar verbatim, and adds an explicit unresolved-access reason.
The ordinary discovery and scheduling contracts enforce that reason.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from app.catalog import calendar_enrichment as enrich
from app.catalog import ingest
from app.routing.visit_calendar import calendar_eligible, source_calendar

SCHEMA = "roadtrips-source-parking-holds/1"


def _read_json(path, max_bytes):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("parking hold input exceeds unchanged byte ceiling")
    with path.open("rb") as stream:
        body = stream.read(max_bytes + 1)
    if not 0 < len(body) <= max_bytes:
        raise ValueError("parking hold input exceeds unchanged byte ceiling")
    return json.loads(body.decode("utf-8-sig")), len(body)


def _native(document, pointer, collection):
    parts = pointer.split("/") if isinstance(pointer, str) else []
    if len(parts) != 3 or parts[:2] != ["", collection] or not parts[2].isdigit():
        raise ValueError("parking hold requires an exact native collection pointer")
    try:
        return document[collection][int(parts[2])]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("selected native parking/facility record is missing") from exc


def hold_entry(row, previous, decision, document):
    """Bind a reviewed hold to unchanged native identity and source constraints."""
    sid = decision["source_id"]
    if sid != row["source_id"] or previous["source_id"] != sid:
        raise ValueError("parking hold identity differs from preserved place")
    facility = _native(document, decision["facility_pointer"], "visitorCenters")
    receipt = decision["source_receipt"]
    if (
        facility.get("visitorCenterID") != decision["facility_id"]
        or float(facility["location"]["latitude"]) != row["latitude"]
        or float(facility["location"]["longitude"]) != row["longitude"]
        or not any(
            fact.get("record_id") == str(decision["facility_id"])
            and all(
                fact.get(key) == receipt.get(key)
                for key in ["snapshot_sha256", "source_url", "checked_at"]
            )
            for fact in row["provenance"]
        )
        or receipt.get("native_facility_id", decision["facility_id"]) != decision["facility_id"]
        or receipt.get("native_json_pointer", decision["facility_pointer"])
        != decision["facility_pointer"]
    ):
        raise ValueError("parking hold changed native facility identity or coordinates")
    selected = decision["parking_lots"]
    if not isinstance(selected, list) or not 1 <= len(selected) <= 100:
        raise ValueError("parking hold requires bounded reviewed parking selections")
    lots = []
    for selection in selected:
        lot = _native(document, selection["native_pointer"], "parkingLots")
        if (
            lot.get("lotID") != selection["lot_id"]
            or lot.get("schedule", {}).get("operatingScheduleID") != selection["schedule_id"]
        ):
            raise ValueError("parking hold lot or schedule identity differs from native source")
        lots.append({"native_pointer": selection["native_pointer"], "native_record": lot})
    reason = decision.get("hold_reason")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 4096:
        raise ValueError("parking hold requires an explicit bounded unresolved-access reason")
    entry = copy.deepcopy(previous)
    if source_calendar({"source_provenance": [entry]}) is None:
        raise ValueError("parking hold requires the valid prior attributed calendar")
    entry["source_visit_calendar"].setdefault("unknown_reasons", []).append(reason)
    entry["source_constraints"].append(
        {
            "dataset": "National Park Service selected-arrival parking access",
            "source_receipt": copy.deepcopy(decision["source_receipt"]),
            "native_facility_pointer": decision["facility_pointer"],
            "native_facility_id": decision["facility_id"],
            "native_facility": copy.deepcopy(facility),
            "selected_parking_lots": copy.deepcopy(lots),
            "unresolved_access_reason": reason,
            "scope": "Selected visitor-facility arrival; no inferred solar time, AM/PM repair, overnight offset, coordinate repair or substitute entrance",
        }
    )
    entry["transformation"] = {
        "method": "Preserve the prior calendar and add a source-attributed unresolved selected-arrival parking hold",
        "prior_transformation": entry["transformation"],
        "prior_calendar_sha256": enrich.digest(previous["source_visit_calendar"]),
    }
    if calendar_eligible({"source_provenance": [entry]}):
        raise ValueError("explicit parking hold unexpectedly passed automatic eligibility")
    return entry


def build(parent_path, decisions_path, evidence_root, output):
    """Build a portable enrichment artifact from a frozen parent export, offline."""
    parent, parent_bytes = _read_json(parent_path, ingest.MAX_BYTES)
    selections, selection_bytes = _read_json(decisions_path, ingest.MAX_BYTES - parent_bytes)
    decisions = selections.get("decisions")
    if (
        selections.get("schema_version") != SCHEMA
        or not isinstance(decisions, list)
        or not 1 <= len(decisions) <= ingest.MAX_ROWS
        or len({d["source_id"] for d in decisions}) != len(decisions)
    ):
        raise ValueError("parking hold decisions require unique bounded reviewed identities")
    rows, previous = parent["rows"], parent["entries"]
    if (
        not 1 <= len(rows) <= ingest.MAX_ROWS
        or len({r["source_id"] for r in rows}) != len(rows)
        or len({e["source_id"] for e in previous}) != len(previous)
        or parent["manifest"]["normalized_rows_sha256"] != enrich.rows_digest(rows)
        or parent["manifest"]["calendar_enrichment_sha256"] != enrich.digest(previous)
    ):
        raise ValueError("parking hold parent export differs from immutable fingerprints")
    by_id, by_entry = ({r["source_id"]: r for r in rows}, {e["source_id"]: e for e in previous})
    output = Path(output)
    if output.exists():
        raise ValueError("parking hold output must be a new directory")
    output.mkdir(parents=True)
    reader = enrich.Reader(evidence_root, ingest.MAX_BYTES - parent_bytes - selection_bytes)

    def retain(receipt):
        body = reader.read(receipt["evidence_path"], receipt["snapshot_sha256"])
        target = output / receipt["evidence_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return body

    entries = []
    for decision in decisions:
        sid = decision["source_id"]
        if sid not in by_id or sid not in by_entry:
            raise ValueError("parking hold references a place/calendar outside its parent")
        body = retain(decision["source_receipt"])
        document = json.loads(body.decode("utf-8-sig"))
        entry = hold_entry(by_id[sid], by_entry[sid], decision, document)
        for receipt in entry["source_visit_calendar"]["source_receipts"]:
            retain(receipt)
        entries.append(entry)
    for license in selections["licenses"]:
        retain(license)
    snapshot = output / "baseline.json"
    snapshot.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n")
    payload = {
        "schema_version": enrich.SCHEMA,
        "release": selections["release"],
        "attribution": parent["manifest"]["attribution"],
        "parent": {
            "generation": parent["generation"],
            "manifest_sha256": enrich.digest(parent["manifest"]),
            "normalized_rows_sha256": enrich.rows_digest(rows),
            "calendar_enrichment_sha256": enrich.digest(previous),
            "row_count": len(rows),
            "snapshot_path": snapshot.name,
            "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        },
        "source_scanned_rows": len(decisions),
        "source_inputs": [d["source_receipt"] for d in decisions],
        "entries": entries,
        "licenses": selections["licenses"],
    }
    path = output / "catalog.enrichment.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return enrich.prepare(path)
