"""Follow-up queue and immutable-evidence controls; no source/AI requests."""

import hashlib
import json

import pytest
from scripts import catalog_pilot_audit as audit
from scripts import catalog_pilot_followup as followup


def setup(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    native = {
        "results": {
            "bindings": [
                {
                    "item": {"value": "https://www.wikidata.org/entity/Q1"},
                    "itemLabel": {"value": "Synthetic museum"},
                    "coord": {"value": "Point(-72 43)"},
                }
            ]
        }
    }
    followup.write(base / "native.json", native)
    receipt = {
        "id": "native",
        "path": "native.json",
        "sha256": followup.digest(base / "native.json"),
        "url": "https://query.wikidata.org/sparql",
        "status": 200,
    }
    records = [
        {"pilot_id": f"culture:wd:Q{n}", "cohort": "museum_science", "hold_reason": "unreviewed"}
        for n in range(1, 51)
    ]
    followup.write(base / "states.json", {})
    payload = {
        "records": records,
        "evidence": [receipt],
        "states": {"path": "states.json", "sha256": followup.digest(base / "states.json")},
        "local_baseline": {"path": "states.json", "sha256": followup.digest(base / "states.json")},
    }
    followup.write(base / "reviewed.json", payload)
    followup.write(
        base / "reviewed.manifest.json", {"sha256": followup.digest(base / "reviewed.json")}
    )
    queue = tmp_path / "queue.json"
    followup.write(queue, {"unreviewed_operator_review": [r["pilot_id"] for r in records]})
    updates = tmp_path / "updates.json"
    return base, queue, updates


def test_followup_preserves_base_and_original_review_stamp(tmp_path, monkeypatch):
    base, queue, updates = setup(tmp_path)
    original = (base / "reviewed.json").read_bytes()
    row = json.loads(original)["records"][0] | {"hold_reason": "bounded review incomplete"}
    followup.write(updates, {"records": [row], "evidence": []})
    monkeypatch.setattr(followup, "replay", lambda *args: {"accepted": 0})
    output = tmp_path / "out"
    followup.merge(base, [updates], queue, output)
    assert (base / "reviewed.json").read_bytes() == original
    assert json.loads((output / "reviewed.json").read_bytes())["records"][0] == row
    assert json.loads((output / "merge-receipt.json").read_bytes())["reviewed_queue_count"] == 1
    with pytest.raises(ValueError, match="immutable"):
        followup.merge(base, [updates], queue, output)


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"pilot_id": "culture:wd:Q9999"}, "outsidequeue"),
        ({"cohort": "other"}, "identity/cohort"),
        ({"review": {"decision": "T3"}}, "itinerary"),
    ],
)
def test_review_cannot_escape_queue_or_grant_t3(tmp_path, mutation, message):
    base, queue, updates = setup(tmp_path)
    row = json.loads((base / "reviewed.json").read_bytes())["records"][0] | mutation
    followup.write(updates, {"records": [row], "evidence": []})
    with pytest.raises(ValueError, match=message):
        followup.merge(base, [updates], queue, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("decision", ["T1", "T2"])
def test_followup_cannot_bind_a_different_native_entity(tmp_path, decision):
    base, queue, updates = setup(tmp_path)

    def binding(leaf):
        return {"evidence_id": "native", "pointer": "/results/bindings/0/" + leaf}

    row = {
        "pilot_id": "culture:wd:Q2",
        "cohort": "museum_science",
        "source_family": "wikidata",
        "review": {"decision": decision},
        "bindings": {
            "native_id": binding("item/value") | {"transform": "url_tail"},
            "name": binding("itemLabel/value"),
            "coordinates": {"encoding": "wkt", "value": binding("coord/value")},
        },
    }
    followup.write(updates, {"records": [row], "evidence": []})
    with pytest.raises(ValueError, match="queued Wikidata"):
        followup.merge(base, [updates], queue, tmp_path / "out")


def test_changed_original_or_new_receipt_fails_without_output(tmp_path):
    base, queue, updates = setup(tmp_path)
    body = b"original evidence"
    (tmp_path / "operator.bin").write_bytes(body + b"changed")
    followup.write(
        updates,
        {
            "records": [],
            "evidence": [
                {
                    "id": "operator",
                    "path": "operator.bin",
                    "status": 200,
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="changed"):
        followup.merge(base, [updates], queue, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_bounded_diverse_queue_rejects_changed_discovery_snapshot(tmp_path):
    base, queue, updates = setup(tmp_path)
    payload = json.loads((base / "reviewed.json").read_bytes())
    payload["records"][0]["pilot_id"] = "diversity:wd:Q1"
    followup.write(base / "reviewed.json", payload)
    followup.write(
        base / "reviewed.manifest.json", {"sha256": followup.digest(base / "reviewed.json")}
    )
    followup.write(
        queue,
        {
            "unreviewed_operator_review": ["diversity:wd:Q1"],
            "frozen_native_sha256": {"diversity:wd:Q1": "0" * 64},
        },
    )

    def binding(leaf):
        return {"evidence_id": "native", "pointer": "/results/bindings/0/" + leaf}

    row = payload["records"][0] | {
        "source_family": "wikidata",
        "review": {"decision": "T2"},
        "bindings": {
            "native_id": binding("item/value") | {"transform": "url_tail"},
            "name": binding("itemLabel/value"),
            "coordinates": {"encoding": "wkt", "value": binding("coord/value")},
        },
    }
    followup.write(updates, {"records": [row], "evidence": []})
    with pytest.raises(ValueError, match="queued hash"):
        followup.merge(base, [updates], queue, tmp_path / "out")


@pytest.mark.parametrize(
    "queue_ids", [[], ["culture:wd:Q1"] * 2, ["unknown:Q1"], ["culture:wd:Q1"] * 101]
)
def test_queue_is_unique_bounded_and_explicit(tmp_path, queue_ids):
    base, queue, updates = setup(tmp_path)
    followup.write(queue, {"unreviewed_operator_review": queue_ids})
    followup.write(updates, {"records": [], "evidence": []})
    with pytest.raises(ValueError, match="prepared operator queue"):
        followup.merge(base, [updates], queue, tmp_path / "out")


def audit_fixture(tmp_path):
    source, proof = tmp_path / "source", tmp_path / "proof"
    (source / "replay").mkdir(parents=True)
    (proof / "portable-import").mkdir(parents=True)
    row = {"source_id": "catalog-pilot:wikidata:Q1", "region": "CT", "categories": ["museum"]}

    def rows_sha(rows):
        return hashlib.sha256(
            "".join(json.dumps(r, sort_keys=True, allow_nan=False) + "\n" for r in rows).encode()
        ).hexdigest()

    followup.write(
        source / "reviewed.json",
        {"evidence": [], "records": [{"pilot_id": "p", "cohort": "museum"}]},
    )
    sha = followup.digest(source / "reviewed.json")
    followup.write(source / "reviewed.manifest.json", {"sha256": sha})
    followup.write(source / "local-baseline.json", [row] * 696)
    followup.write(source / "replay/additions.preview.json", [row])
    followup.write(source / "replay/personas.json", [])
    followup.write(
        source / "replay/decisions.json", [{"pilot_id": "p", "tier": "T1", "reason": "hold"}] * 600
    )
    followup.write(
        source / "replay/report.json",
        {"accepted": 1, "prospects": 600, "normalized_rows_sha256": rows_sha([row])},
    )
    followup.write(
        proof / "portable-import/catalog.preview.json", [{"source_id": "synthetic-parent"}, row]
    )
    followup.write(
        proof / "proof.json",
        {
            "source_manifest_sha256": sha,
            "source_additions_sha256": rows_sha([row]),
            "source_admitted_browse": 1,
            "actual_repository_queries": 1,
            "generation": "candidate",
            "assembled": {
                "additions": 1,
                "normalized_rows_sha256": rows_sha([{"source_id": "synthetic-parent"}, row]),
            },
        },
    )
    followup.write(
        proof / "recovery-receipt.json", {"candidate": {"generation": "candidate", "row_count": 2}}
    )
    return source, proof


def test_audit_requires_matching_source_proof_and_preserves_coverage(tmp_path):
    source, proof = audit_fixture(tmp_path)
    audit.export(source, proof, tmp_path / "audit")
    coverage = json.loads((tmp_path / "audit/coverage.json").read_bytes())
    assert coverage["before"]["records"] == 696
    assert coverage["after"]["records"] == 697
    assert coverage["live_net_new"] is None


@pytest.mark.parametrize(
    "target, field",
    [
        ("proof", "source_manifest_sha256"),
        ("proof", "source_additions_sha256"),
        ("report", "normalized_rows_sha256"),
        ("manifest", "sha256"),
    ],
)
def test_audit_rejects_unrelated_proof_or_changed_replay(tmp_path, target, field):
    source, proof = audit_fixture(tmp_path)
    path = {
        "proof": proof / "proof.json",
        "report": source / "replay/report.json",
        "manifest": source / "reviewed.manifest.json",
    }[target]
    value = json.loads(path.read_bytes())
    value[field] = "0" * 64
    followup.write(path, value)
    with pytest.raises(ValueError, match="does not match"):
        audit.export(source, proof, tmp_path / "audit")
    assert not (tmp_path / "audit").exists()
