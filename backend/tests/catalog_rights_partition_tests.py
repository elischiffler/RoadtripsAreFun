"""Discovery labels cannot authorize noncommercial use or enter the catalog."""

import json

import pytest
from scripts import catalog_rights_partition as partition

from app.catalog import admission


def artifact(tmp_path, licenses):
    ledger, candidates = tmp_path / "sources.json", tmp_path / "candidates.json"
    ledger.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": str(n),
                        "license_identifier": license_id,
                        "license_version": "4.0",
                        "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
                        "attribution": "Synthetic creator",
                        "rights_scope": "Synthetic test facts",
                        "redistribution": "requires source review",
                        "adaptation": "unreviewed",
                    }
                    for n, license_id in enumerate(licenses)
                ]
            }
        )
    )
    candidates.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "candidate_id": str(n),
                        "source_id": str(n),
                        "name": "Synthetic lead",
                        "tier": "T3",
                        "routing_eligible": True,
                        "review_status": "approved",
                    }
                    for n in range(len(licenses))
                ]
            }
        )
    )
    return ledger, candidates


def test_nc_partition_stays_quarantined_despite_claimed_approval(tmp_path):
    ledger, candidates = artifact(tmp_path, ["CC-BY-NC-4.0"])
    result = partition.build(ledger, candidates)
    row = result["partitions"]["noncommercial_only"][0]
    assert row["future_monetization_excluded"] is True
    assert row["tier"] == "T1" and row["review_status"] == "quarantined"
    assert row["profile"] is None and row["precise_question"]
    assert not admission.browse_eligible(row) and not admission.routing_eligible(row)
    assert result["main_catalog_admissions"] == result["itinerary_ready"] == 0
    assert partition.build(ledger, candidates) == result


def test_nd_and_personal_use_are_not_silently_adaptable(tmp_path):
    ledger, candidates = artifact(tmp_path, ["CC-BY-NC-ND-4.0", "Personal use only"])
    result = partition.build(ledger, candidates)
    assert "not cleared under ND" in result["partitions"]["noncommercial_only"][0]["adaptation"]
    assert result["counts"]["unclear_rights"] == 1
    assert result["partitions"]["unclear_rights"][0]["future_monetization_excluded"] is True


def test_photo_nc_does_not_relabel_separately_licensed_facts(tmp_path):
    ledger, candidates = artifact(tmp_path, ["CC-BY-4.0", "CC-BY-NC-2.0", "Unknown"])
    result = partition.build(ledger, candidates)
    assert result["counts"] == {
        "noncommercial_only": 1,
        "permissive_discovery": 1,
        "unclear_rights": 1,
    }
    assert all(not row["browse_eligible"] for rows in result["partitions"].values() for row in rows)


def test_duplicated_candidate_identity_fails_closed(tmp_path):
    ledger, candidates = artifact(tmp_path, ["CC-BY-NC-4.0", "Unknown"])
    payload = json.loads(candidates.read_bytes())
    payload["records"][1]["candidate_id"] = "0"
    candidates.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="duplicated"):
        partition.build(ledger, candidates)
