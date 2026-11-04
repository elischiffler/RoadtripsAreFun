"""Data-level T2 routing quarantine compatible with older calendar-aware readers.

Application discovery tags are distinct from source identity/category evidence.
The inline calendar is a project qualification hold with no opening windows,
never a publisher closure or an invented schedule. It also protects direct
current-record refreshes that bypass discovery category filters.
"""

import copy
import re
from datetime import datetime
from urllib.parse import urlsplit

SCHEMA = "roadtrips-browse-routing-quarantine/1"
DATASET = "Roadtrips browse-only routing qualification hold"
ROUTING_CATEGORIES = frozenset({"daytime", "food", "culture", "nightlife"})


def receipt(row):
    """Choose an actual selected review receipt, without claiming source hours."""
    for fact in reversed(row.get("provenance", [])):
        if isinstance(fact, dict) and fact.get("current_operator_evidence_reference"):
            return fact["current_operator_evidence_reference"]
    for fact in row.get("provenance", []):
        if isinstance(fact, dict) and fact.get("public_visit_evidence"):
            return fact["public_visit_evidence"][0]
    raise ValueError("browse quarantine requires its actual reviewed source receipt")


def apply(row):
    """Restrict a reviewed T2 row; never issue or renew an admission decision."""
    facts = row.get("provenance", [])
    markers = [fact["catalog_admission"] for fact in facts if "catalog_admission" in fact]
    if len(markers) != 1 or markers[0].get("tier") != "T2":
        raise ValueError("browse quarantine only transforms an explicitly reviewed T2 row")
    if any("source_visit_calendar" in fact for fact in facts):
        existing = [fact for fact in facts if fact.get("dataset") == DATASET]
        if len(existing) != 1:
            raise ValueError("browse quarantine cannot overwrite or merge a selected calendar")
        original = copy.deepcopy(row)
        original["provenance"] = [fact for fact in facts if fact.get("dataset") != DATASET]
        original["categories"] = existing[0]["original_application_classifications"]
        if apply(original) != row:
            raise ValueError("existing browse quarantine differs from the canonical restriction")
        return copy.deepcopy(row)
    source = copy.deepcopy(receipt(row))
    stamp = datetime.fromisoformat(source["checked_at"].replace("Z", "+00:00"))
    if (
        stamp.tzinfo is None
        or urlsplit(source["source_url"]).scheme != "https"
        or urlsplit(source["source_url"]).username
        or not re.fullmatch("[0-9a-f]{64}", source["snapshot_sha256"])
    ):
        raise ValueError("browse quarantine source receipt is malformed")
    output = copy.deepcopy(row)
    original = output["categories"]
    output["categories"] = [kind for kind in original if kind not in ROUTING_CATEGORIES]
    if "catalog_browse" not in output["categories"]:
        output["categories"].append("catalog_browse")
    output["provenance"].append(
        {
            "dataset": DATASET,
            "schema_version": SCHEMA,
            "original_application_classifications": original,
            "routing_categories_removed": sorted(set(original) & ROUTING_CATEGORIES),
            "source_visit_calendar": {
                "schema_version": "roadtrips-source-visit-calendar/1",
                "weekly_windows": [],
                "date_overrides": [],
                "source_receipts": [source],
                "unknown_reasons": [
                    "Browse-only: vehicle arrival and visit timing have not been qualified."
                ],
            },
            "transformation": {
                "method": "Project eligibility restriction; not publisher hours, closure, accessibility or operating status.",
                "native_facts_unchanged": True,
                "admission_clock_renewed": False,
            },
        }
    )
    return output
