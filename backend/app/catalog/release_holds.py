"""Pinned acquisition-audit holds override historical admission approvals.

Keep source rows and provenance for deduplication and review. A new approval or
even a T3 marker cannot silently clear a hold: changing this reviewed list and
its pin requires an explicit evidence review. Missing/corrupt data fails startup.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

AUDIT_SHA256 = "0d29c5d527be6d08f018e4ee1cd9598dc8048b944e1c67aa42f2c29c190bb2ec"
_raw = Path(__file__).with_name("release_holds.json").read_bytes()
if hashlib.sha256(_raw).hexdigest() != AUDIT_SHA256:
    raise RuntimeError("catalog acquisition-audit hold list differs from its reviewed pin")
_document = json.loads(_raw)
_ids = _document["source_ids"]
if (
    _document.get("schema_version") != "roadtrips-receipt-audit-release-holds/1"
    or _document.get("count") != 133
    or not isinstance(_ids, list)
    or len(_ids) != 133
    or any(
        not isinstance(sid, str) or not re.fullmatch(r"catalog-pilot:[A-Za-z0-9_:./~-]+", sid)
        for sid in _ids
    )
    or len(set(_ids)) != 133
):
    raise RuntimeError("catalog acquisition-audit hold list is invalid")
SOURCE_IDS = frozenset(_ids)
# Validated, pinned source IDs only; this fragment has no caller-controlled SQL.
_SQL_IDS = ",".join("'" + sid + "'" for sid in sorted(SOURCE_IDS))
SQL_ALLOWED = f"""NOT EXISTS (
    SELECT 1 FROM (
        SELECT p.source_id AS sid
        UNION ALL
        SELECT fact->'catalog_admission'->>'source_id'
        FROM jsonb_array_elements(CASE WHEN jsonb_typeof(p.provenance)='array'
            THEN p.provenance ELSE '[]'::jsonb END) fact
        UNION ALL
        SELECT jsonb_array_elements_text(CASE WHEN jsonb_typeof(fact->'aliases')='array'
            THEN fact->'aliases' ELSE '[]'::jsonb END)
        FROM jsonb_array_elements(CASE WHEN jsonb_typeof(p.provenance)='array'
            THEN p.provenance ELSE '[]'::jsonb END) fact
    ) held_identity WHERE sid IN ({_SQL_IDS})
)"""


def blocked(record):
    """Recognize raw, provider and review identities without rewriting facts."""
    if isinstance(record, str):
        return record in SOURCE_IDS
    if not isinstance(record, Mapping):
        return False
    identities = [record.get(key) for key in ("source_id", "provider_id", "pilot_id")]
    for key in ("provenance", "source_provenance"):
        facts = record.get(key)
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, Mapping):
                continue
            contract = fact.get("catalog_admission")
            if isinstance(contract, Mapping):
                identities.append(contract.get("source_id"))
            aliases = fact.get("aliases")
            if isinstance(aliases, list):
                identities.extend(aliases)
    return any(isinstance(sid, str) and sid in SOURCE_IDS for sid in identities)


def reject(rows):
    """Refuse the whole stage rather than silently shrink a reviewed generation."""
    if any(blocked(row) for row in rows):
        raise ValueError(
            "catalog acquisition-audit release hold; retain identities outside active imports"
        )


def check_generation(cursor, generation):
    """Check stored facts again, including old staged and recovery generations."""
    cursor.execute(
        f"SELECT count(*) AS held_count FROM places_catalog p WHERE p.generation=%s AND NOT ({SQL_ALLOWED})",
        (generation,),
    )
    row = cursor.fetchone()
    count = row["held_count"] if isinstance(row, Mapping) else row[0]
    if count:
        raise ValueError("catalog acquisition-audit release hold; generation cannot activate")
