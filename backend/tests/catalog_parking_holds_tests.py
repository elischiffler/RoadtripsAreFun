"""Offline source binding and exact-fact preservation for parking hold imports."""

import copy
import hashlib
import json

import pytest

from app.catalog import calendar_enrichment as enrich
from app.catalog.parking_holds import SCHEMA, build, hold_entry
from app.routing.visit_calendar import calendar_eligible


def inputs():
    receipt = {
        "source_url": "https://www.nps.gov/fixture/structured_data_fixture.json",
        "snapshot_sha256": "a" * 64,
        "evidence_path": "evidence/native.json",
        "checked_at": "2026-10-16T00:00:00Z",
    }
    row = {
        "source_id": "nps-heritage:fixture",
        "latitude": 35.0,
        "longitude": -111.0,
        "provenance": [{"record_id": "123", **copy.deepcopy(receipt)}],
    }
    previous = {
        "source_id": row["source_id"],
        "source_visit_calendar": {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "weekly_windows": [{"weekdays": list(range(7)), "opens": "09:00", "closes": "17:00"}],
            "source_receipts": [receipt],
        },
        "source_constraints": [{"literal": "Synthetic indoor hours"}],
        "transformation": {"method": "Synthetic source extraction"},
    }
    document = {
        "visitorCenters": [
            {
                "visitorCenterID": 123,
                "location": {"latitude": "35", "longitude": "-111"},
                "description": "Synthetic selected facility",
            }
        ],
        "parkingLots": [
            {
                "lotID": "native-lot",
                "latitude": "35",
                "longitude": "111",
                "schedule": {
                    "operatingScheduleID": 456,
                    "hours": [
                        {"sunriseOpen": 1, "sunsetClose": 1, "timeOpen": "", "timeClose": ""}
                    ],
                },
                "description": "Synthetic selected visitor parking; source coordinate sign remains unresolved",
            }
        ],
    }
    decision = {
        "source_id": row["source_id"],
        "source_receipt": receipt,
        "facility_pointer": "/visitorCenters/0",
        "facility_id": 123,
        "parking_lots": [
            {"native_pointer": "/parkingLots/0", "lot_id": "native-lot", "schedule_id": 456}
        ],
        "hold_reason": "Unresolved synthetic selected-arrival parking access",
    }
    return row, previous, decision, document


def test_hold_preserves_calendar_and_all_native_parking_values():
    row, previous, decision, document = inputs()
    frozen = copy.deepcopy([row, previous, decision, document])
    held = hold_entry(row, previous, decision, document)
    assert [row, previous, decision, document] == frozen
    assert (
        held["source_visit_calendar"]["weekly_windows"]
        == previous["source_visit_calendar"]["weekly_windows"]
    )
    assert held["source_constraints"][:-1] == previous["source_constraints"]
    assert (
        held["source_constraints"][-1]["selected_parking_lots"][0]["native_record"]
        == document["parkingLots"][0]
    )
    assert not calendar_eligible({"categories": ["daytime", "nature"], "source_provenance": [held]})


@pytest.mark.parametrize(
    "field",
    [
        "identity",
        "point",
        "facility",
        "lot",
        "schedule",
        "pointer",
        "reason",
        "source_url",
        "checked_at",
        "native_json_pointer",
    ],
)
def test_changed_or_unbound_source_identity_cannot_supply_a_hold(field):
    row, previous, decision, document = inputs()
    if field == "identity":
        previous["source_id"] = "different"
    if field == "point":
        row["longitude"] = 111.0
    if field == "facility":
        decision["facility_id"] = 999
    if field == "lot":
        decision["parking_lots"][0]["lot_id"] = "different"
    if field == "schedule":
        decision["parking_lots"][0]["schedule_id"] = 999
    if field == "pointer":
        decision["facility_pointer"] = "/visitorCenters/../0"
    if field == "reason":
        decision["hold_reason"] = ""
    if field == "source_url":
        decision["source_receipt"]["source_url"] = "https://www.nps.gov/invented"
    if field == "checked_at":
        decision["source_receipt"]["checked_at"] = "2026-10-16T01:00:00Z"
    if field == "native_json_pointer":
        decision["source_receipt"]["native_json_pointer"] = "/visitorCenters/9"
    with pytest.raises(ValueError):
        hold_entry(row, previous, decision, document)


def test_portable_offline_build_binds_bytes_and_parent_fingerprints(tmp_path):
    row, previous, decision, document = inputs()
    root = tmp_path / "inputs"
    (root / "evidence").mkdir(parents=True)
    source = root / "evidence/native.json"
    source.write_text(json.dumps(document))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    decision["source_receipt"]["snapshot_sha256"] = digest
    row["provenance"][0]["snapshot_sha256"] = digest
    rows, entries = [row], [previous]
    manifest = {
        "normalized_rows_sha256": enrich.rows_digest(rows),
        "calendar_enrichment_sha256": enrich.digest(entries),
        "attribution": "Synthetic fixture facts",
    }
    parent = tmp_path / "parent.json"
    parent.write_text(
        json.dumps({"generation": "a" * 64, "manifest": manifest, "rows": rows, "entries": entries})
    )
    selections = tmp_path / "decisions.json"
    selections.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA,
                "release": "synthetic-hold",
                "decisions": [decision],
                "licenses": [
                    {
                        "identifier": "Synthetic-test-only",
                        "evidence_path": "evidence/native.json",
                        "snapshot_sha256": digest,
                    }
                ],
            }
        )
    )
    output = tmp_path / "result"
    prepared = build(parent, selections, root, output)
    assert prepared["rows"] == rows and prepared["additions"] == []
    assert prepared["report"]["calendar_updates"] == 1
    assert (output / "evidence/native.json").read_bytes() == source.read_bytes()
    source.write_text("corrupted retained source")
    with pytest.raises(ValueError, match="checksum"):
        build(parent, selections, root, tmp_path / "corrupt")
