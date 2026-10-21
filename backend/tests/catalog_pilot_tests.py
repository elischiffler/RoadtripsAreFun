"""Synthetic source replay controls, not real attraction verification."""

import copy
import hashlib
import json
import time

import pytest

from app.catalog import admission, pilot, pilot_personas


@pytest.fixture(autouse=True)
def synthetic_rights_notice(monkeypatch):
    # Synthetic notices can clear only synthetic tests; production pins stay
    # unchanged and fixture changes are restored after each test.
    monkeypatch.setitem(
        pilot.RIGHTS_PINS,
        "wikidata",
        {hashlib.sha256(b"Structured facts are available under CC0.").hexdigest()},
    )


def artifact(tmp_path):
    """Synthetic JSON/HTML and 56 synthetic shapes; no network or real facts."""
    evidence = []

    def retain(ident, value, url):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        path = tmp_path / (ident + ".bin")
        path.write_bytes(body)
        receipt = {
            "id": ident,
            "path": path.name,
            "sha256": hashlib.sha256(body).hexdigest(),
            "url": url,
            "status": 200,
            "checked_at": "2099-01-01T00:00:00Z",  # Replaced below, never future evidence.
        }
        from datetime import UTC, datetime

        receipt["checked_at"] = datetime.now(UTC).isoformat()
        evidence.append(receipt)
        return receipt

    retain(
        "native",
        {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "https://www.wikidata.org/entity/Q999999999"},
                        "itemLabel": {"value": "Synthetic test museum"},
                        "coord": {"value": "Point(-72 43)"},
                    }
                ]
            }
        },
        "https://query.wikidata.org/sparql?query=synthetic-fixture",
    )
    retain(
        "operator",
        b"Synthetic test museum in Mock Town. Public museum visitors are welcome.",
        "https://operator.example/visit",
    )
    retain(
        "rights",
        b"Structured facts are available under CC0.",
        "https://www.wikidata.org/wiki/Wikidata:Copyright",
    )
    states = retain(
        "states",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {"STUSAB": "NH" if n == 0 else "ZZ"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-73, 42], [-71, 42], [-71, 44], [-73, 44], [-73, 42]]]
                        if n == 0
                        else [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    },
                }
                for n in range(56)
            ],
        },
        pilot.usfs.STATE_URL,
    )
    baseline = retain(
        "baseline",
        [
            {
                "source_id": "fixture-parent",
                "name": "Synthetic prior",
                "region": "CA",
                "latitude": 0,
                "longitude": 0,
                "provenance": [],
            }
        ],
        "https://operator.example/synthetic-parent",
    )

    def binding(pointer):
        return {"evidence_id": "native", "pointer": pointer}

    row = {
        "pilot_id": "synthetic:1",
        "source_family": "wikidata",
        "cohort": "museum_science",
        "state": "NH",
        "category": "museum",
        "operator_url": "https://operator.example/visit",
        "bindings": {
            "native_id": binding("/results/bindings/0/item/value") | {"transform": "url_tail"},
            "name": binding("/results/bindings/0/itemLabel/value"),
            "coordinates": {"encoding": "wkt", "value": binding("/results/bindings/0/coord/value")},
        },
        "access_proofs": [
            {"evidence_id": "operator", "literal": "Public museum visitors are welcome."}
        ],
        "operator_identity_location_proofs": [
            {"evidence_id": "operator", "literal": "Synthetic test museum in Mock Town."}
        ],
        "rights_proofs": [{"evidence_id": "rights", "literal": "available under CC0"}],
        "review": {
            "decision": "T2",
            "license": "CC0-1.0",
            "reviewer": "Synthetic test reviewer",
            "reason": "Controlled test assertion only",
            "operator_is_primary": True,
            "public_visit_affirmed": True,
            "closure_conflicts_reviewed": True,
            "reviewed_at_epoch": int(time.time()) - 1,
        },
        "source_constraints": ["Synthetic appointment constraint; never a real visit."],
    }
    payload = {
        "records": [row],
        "evidence": evidence[:3],
        "states": states,
        "local_baseline": baseline,
    }
    return payload


def replay(tmp_path, payload):
    path = tmp_path / "reviewed.json"
    path.write_text(json.dumps(payload, allow_nan=False))
    manifest = {
        "schema_version": pilot.SCHEMA,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return pilot.prepare(path, manifest)


def test_replay_is_deterministic_browse_only_with_unknowns_and_fourteen_attributes(tmp_path):
    payload = artifact(tmp_path)
    rows, report = replay(tmp_path, payload)
    assert replay(tmp_path, payload) == (rows, report)
    assert report["prospects"] == 1 and report["scanned"] == 59
    assert report["native_source_rows"] == 1
    assert report["accepted"] == 1 and report["itinerary_ready"] == 0
    row = rows[0]
    assert admission.browse_eligible(row) and not admission.routing_eligible(row)
    assert "catalog_browse" in row["categories"] and "daytime" not in row["categories"]
    assert row["address"] is None and row["source_updated_at"] is None
    profile = report["profiles"][0]
    assert len(profile["attribute_ratings"]) == 14
    assert profile["attribute_ratings"]["culture_arts"] == 0.8
    assert profile["attribute_ratings"]["family_friendliness"] == 0.5
    assert profile["activities"] == []
    assert profile["practical_context"]["hours"] is None
    assert (
        profile["practical_context"]["source_constraints"]
        == payload["records"][0]["source_constraints"]
    )
    assert "location_profile" not in pilot_personas.stored(profile)
    assert report["live_net_new"] is None


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda r: r.update(state="CT"), "Census state"),
        (lambda r: r["review"].update(public_visit_affirmed=False), "review is incomplete"),
        (lambda r: r["review"].update(license="Unknown"), "license differs"),
        (
            lambda r: r["access_proofs"][0].update(literal="There is free parking here"),
            "evidence fragment differs",
        ),
        (
            lambda r: r["bindings"]["name"].update(pointer="/results/bindings/0/missing"),
            "reviewed source field",
        ),
        (
            lambda r: r.update(operator_url="https://unrelated.example/"),
            "differs from reviewed operator",
        ),
        (lambda r: r.update(category="invented_type"), "no reviewed persona rule"),
        (
            lambda r: r["review"].update(reviewed_at_epoch=int(time.time()) + 1000),
            "stale or in the future",
        ),
        (lambda r: r.pop("operator_identity_location_proofs"), "operator_identity_location_proofs"),
    ],
)
def test_unresolved_facts_are_held_with_reasons(tmp_path, mutation, reason):
    payload = artifact(tmp_path)
    mutation(payload["records"][0])
    rows, report = replay(tmp_path, payload)
    assert not rows and report["accepted"] == 0
    assert reason in report["decisions"][0]["reason"]


def test_t1_never_promoted_and_duplicate_alias_cannot_inflate_counts(tmp_path):
    payload = artifact(tmp_path)
    second = copy.deepcopy(payload["records"][0])
    second["pilot_id"] = "synthetic:2"
    payload["records"].extend(
        [second, {"pilot_id": "synthetic:3", "hold_reason": "operator review pending"}]
    )
    rows, report = replay(tmp_path, payload)
    assert len(rows) == 1 and report["prospects"] == 3
    assert "duplicate" in report["decisions"][1]["reason"]
    assert report["decisions"][2] == {
        "pilot_id": "synthetic:3",
        "tier": "T1",
        "reason": "operator review pending",
    }


def test_changed_evidence_and_aggregate_budget_fail_before_admission(tmp_path):
    payload = artifact(tmp_path)
    (tmp_path / "native.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        replay(tmp_path, payload)
    payload = artifact(tmp_path)
    path = tmp_path / "reviewed.json"
    path.write_text(json.dumps(payload))
    manifest = {
        "schema_version": pilot.SCHEMA,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    with pytest.raises(ValueError, match="ceiling"):
        pilot.prepare(path, manifest, max_bytes=len(path.read_bytes()) + 10)


def test_native_pointer_identity_transforms_are_explicit_and_deterministic():
    evidence = {
        "record": (
            {"url": "https://data.ny.gov/resource/example.json"},
            b'{"id":"{12345678-1234-1234-1234-123456789012}","name":"Synthetic"}',
        )
    }
    assert (
        pilot._value({"evidence_id": "record", "pointer": "/id", "transform": "uuid"}, evidence)
        == "12345678-1234-1234-1234-123456789012"
    )
    derived = {
        "transform": "sha256_fields",
        "fields": [
            {"evidence_id": "record", "pointer": "/id"},
            {"evidence_id": "record", "pointer": "/name"},
        ],
    }
    assert pilot._value(derived, evidence).startswith("derived-")
    assert pilot._value(derived, evidence) == pilot._value(derived, evidence)
    with pytest.raises(ValueError, match="two to six"):
        pilot._value({"transform": "sha256_fields", "fields": []}, evidence)


def test_native_fields_from_different_entities_are_never_combined(tmp_path):
    payload = artifact(tmp_path)
    payload["records"][0]["bindings"]["coordinates"]["value"]["pointer"] = (
        "/results/bindings/1/point"
    )
    rows, report = replay(tmp_path, payload)
    assert rows == []
    assert "different source entities" in report["decisions"][0]["reason"]


def test_documented_later_identifiers_and_stored_aliases_remain_exclusions(tmp_path):
    payload = artifact(tmp_path)
    payload["documented_later_exclusion_ids"] = ["wikidata-park:Q999999999"]
    rows, report = replay(tmp_path, payload)
    assert rows == [] and "duplicate" in report["decisions"][0]["reason"]
    assert "nris:123" in pilot._native_aliases(
        {
            "source_id": "catalog-pilot:nps-nhl:123",
            "provenance": [{"aliases": ["nris:123"]}],
        }
    )


def test_typed_browse_import_needs_no_fabricated_calendar(tmp_path):
    from app.catalog import calendar_enrichment as enrich
    from tests.catalog_calendar_enrichment_tests import artifact as parent_artifact

    source = tmp_path / "source"
    source.mkdir()
    payload = artifact(source)
    replay(source, payload)
    manifest = {
        "schema_version": pilot.SCHEMA,
        "sha256": hashlib.sha256((source / "reviewed.json").read_bytes()).hexdigest(),
    }
    baseline = [
        {
            "source_id": "synthetic-parent",
            "name": "Synthetic preservation fixture",
            "latitude": 0.0,
            "longitude": 0.0,
            "region": "CA",
            "categories": ["daytime"],
            "address": None,
            "url": None,
            "source_updated_at": None,
            "provenance": [],
        }
    ]
    path, package = parent_artifact(tmp_path, baseline=baseline)
    package["entries"] = []
    package["addition_inputs"] = [
        {
            "adapter": "reviewed-browse-pilot",
            "path": "source/reviewed.json",
            "sha256": manifest["sha256"],
            "manifest": manifest,
        }
    ]
    path.write_text(json.dumps(package))
    prepared = enrich.prepare(path)
    assert prepared["baseline"] == baseline
    assert len(prepared["additions"]) == 1 and prepared["entries"] == []
    assert not admission.routing_eligible(prepared["additions"][0])
    assert enrich.prepare(path)["generation"] == prepared["generation"]
    # An ordinary empty-calendar enrichment retains its existing rejection.
    package["addition_inputs"] = []
    path.write_text(json.dumps(package))
    with pytest.raises(ValueError, match="calendar entry count"):
        enrich.prepare(path)


@pytest.mark.parametrize("kind", ["redirect", "rights_authority", "null_native_id"])
def test_untrusted_authority_redirects_and_missing_ids_cannot_admit(tmp_path, kind):
    payload = artifact(tmp_path)
    if kind == "redirect":
        payload["evidence"][0]["final_url"] = "https://unrelated.example/sparql"
    elif kind == "rights_authority":
        payload["evidence"][2]["url"] = "https://unrelated.example/CC0"
    else:
        source = json.loads((tmp_path / "native.bin").read_bytes())
        source["results"]["bindings"][0]["item"]["value"] = None
        (tmp_path / "native.bin").write_text(json.dumps(source))
        payload["evidence"][0]["sha256"] = hashlib.sha256(
            (tmp_path / "native.bin").read_bytes()
        ).hexdigest()
    rows, report = replay(tmp_path, payload)
    assert rows == [] and report["decisions"][0]["tier"] == "T1"
