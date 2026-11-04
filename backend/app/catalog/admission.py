"""Versioned pilot admission, separate from facts, availability and legacy policy.

Admission is a replayed review decision, not proof that every fact is true. New
pilot identities fail closed without one current contract. Existing unmarked
catalog identities retain their original eligibility rules.
"""

import time
from collections.abc import Mapping

from app.catalog import release_holds
from app.catalog.identity import catalog_source_id, identity

DATASET = "Roadtrips catalog admission"
SCHEMA = "roadtrips-catalog-admission/1"
PREFIX = "catalog-pilot:"
MAX_REVIEW_SECONDS = 31 * 24 * 60 * 60
MAX_EPOCH = 253402300799
BASE_GATES = ("rights", "identity", "location", "public_access", "local_duplicate_review")
GATES = (*BASE_GATES, "arrival", "calendar")
CONTRACT_KEYS = {
    "schema_version",
    "tier",
    "source_id",
    "review_status",
    "reviewed_at_epoch",
    "expires_at_epoch",
    "gates",
}


def _facts(record):
    value = record.get("source_provenance", record.get("provenance", []))
    return value if isinstance(value, list) else []


def _markers(record):
    return [
        fact
        for fact in _facts(record)
        if isinstance(fact, dict)
        and ("catalog_admission" in fact or fact.get("dataset") == DATASET)
    ]


def _source_id(record):
    source_id, provider_id = record.get("source_id"), record.get("provider_id")
    if source_id is not None:
        if not isinstance(source_id, str):
            return None
        if provider_id is not None and identity(source_id)[0] != provider_id:
            return None
        return source_id
    return catalog_source_id(provider_id) or provider_id


def requires_admission(record):
    """New identities cannot become legacy by stripping their provenance."""
    return isinstance(record, Mapping) and (
        any(str(record.get(key, "")).startswith(PREFIX) for key in ("source_id", "provider_id"))
        or record.get("source") == "catalog-pilot"
        or bool(_markers(record))
    )


def admission_details(record, *, now_epoch=None):
    """Return the single structurally valid, current review contract or None."""
    if not isinstance(record, Mapping) or release_holds.blocked(record):
        return None
    markers = _markers(record)
    if len(markers) != 1 or markers[0].get("dataset") != DATASET:
        return None
    contract = markers[0].get("catalog_admission")
    if not isinstance(contract, dict) or set(contract) != CONTRACT_KEYS:
        return None
    source_id = _source_id(record)
    if (
        not isinstance(source_id, str)
        or not 1 <= len(source_id) <= 512
        or source_id == PREFIX
        or not isinstance(contract["source_id"], str)
        or contract["source_id"] != source_id
        or contract["schema_version"] != SCHEMA
        or not isinstance(contract["tier"], str)
        or contract["tier"] not in {"T2", "T3"}
        or contract["review_status"] != "approved"
    ):
        return None
    reviewed, expires = contract["reviewed_at_epoch"], contract["expires_at_epoch"]
    now_epoch = int(time.time()) if now_epoch is None else now_epoch
    if (
        type(reviewed) is not int
        or type(expires) is not int
        or type(now_epoch) is not int
        or not 0 <= reviewed <= now_epoch < expires <= MAX_EPOCH
        or not 0 < expires - reviewed <= MAX_REVIEW_SECONDS
    ):
        return None
    gates = contract["gates"]
    if (
        not isinstance(gates, dict)
        or set(gates) != set(GATES)
        or any(type(value) is not bool for value in gates.values())
        or not all(gates[key] for key in BASE_GATES)
        or (contract["tier"] == "T3" and not all(gates.values()))
    ):
        return None
    return {**contract, "gates": gates.copy()}


def routing_eligible(record, *, now_epoch=None):
    """Require T3 for new/marked records; calendar validation remains separate."""
    if not isinstance(record, Mapping) or release_holds.blocked(record):
        return False
    if not requires_admission(record):
        return True
    contract = admission_details(record, now_epoch=now_epoch)
    return bool(contract and contract["tier"] == "T3")


def browse_eligible(record, *, now_epoch=None):
    """Only explicitly admitted T2/T3 are browseable; no legacy relabeling."""
    return admission_details(record, now_epoch=now_epoch) is not None


# Only trusted SQL fragments, not user-supplied expressions. Guard every numeric
# cast with CASE and a twelve-digit bound: malformed metadata cannot throw or
# hide valid records behind the discovery LIMIT. SQL and Python share the same
# keys/tier/time constraints; actual source calendars are checked independently.
SQL_JOINS = """
CROSS JOIN LATERAL (
  SELECT jsonb_path_query_array(
    CASE WHEN jsonb_typeof(p.provenance)='array' THEN p.provenance ELSE '[]'::jsonb END,
    '$[*] ? (exists(@.catalog_admission) || @.dataset == "Roadtrips catalog admission")'
  ) AS marks
) admission_marks
CROSS JOIN LATERAL (
  SELECT CASE WHEN jsonb_typeof(marks->0->'catalog_admission')='object'
    THEN marks->0->'catalog_admission' ELSE '{}'::jsonb END AS contract
) admission_contract
CROSS JOIN LATERAL (
  SELECT CASE WHEN jsonb_typeof(contract->'gates')='object'
      THEN contract->'gates' ELSE '{}'::jsonb END AS gates,
    CASE WHEN jsonb_typeof(contract->'reviewed_at_epoch')='number'
        AND (contract->>'reviewed_at_epoch') ~ '^[0-9]{1,12}$'
      THEN (contract->>'reviewed_at_epoch')::bigint END AS reviewed_epoch,
    CASE WHEN jsonb_typeof(contract->'expires_at_epoch')='number'
        AND (contract->>'expires_at_epoch') ~ '^[0-9]{1,12}$'
      THEN (contract->>'expires_at_epoch')::bigint END AS expires_epoch,
    (starts_with(p.source_id,'catalog-pilot:') OR jsonb_array_length(marks)>0) AS required
) admission_review
"""


def sql_predicate(*, browse_mode=False):
    """Eligibility before SQL LIMIT; two now-epoch parameters follow categories."""
    if not isinstance(browse_mode, bool):
        raise ValueError("browse_mode must be a boolean")
    accepted_tiers = "contract->>'tier' IN ('T2','T3')" if browse_mode else "contract->>'tier'='T3'"
    contract_keys = ",".join(f"'{key}'" for key in sorted(CONTRACT_KEYS))
    gate_keys = ",".join(f"'{key}'" for key in GATES)
    base = " AND ".join(f"gates->'{key}'='true'::jsonb" for key in BASE_GATES)
    predicate = f"""
      jsonb_array_length(marks)=1
      AND marks->0->>'dataset'='Roadtrips catalog admission'
      AND contract->>'schema_version'='roadtrips-catalog-admission/1'
      AND jsonb_typeof(contract->'source_id')='string'
      AND length(p.source_id) BETWEEN 1 AND 512
      AND p.source_id<>'catalog-pilot:'
      AND contract->>'source_id'=p.source_id
      AND contract->>'review_status'='approved'
      AND contract - ARRAY[{contract_keys}]::text[]='{{}}'::jsonb
      AND {accepted_tiers}
      AND reviewed_epoch>=0 AND reviewed_epoch<=%s
      AND expires_epoch>%s AND expires_epoch<=253402300799
      AND expires_epoch>reviewed_epoch AND expires_epoch-reviewed_epoch<=2678400
      AND gates - ARRAY[{gate_keys}]::text[]='{{}}'::jsonb
      AND {base}
      AND jsonb_typeof(gates->'arrival')='boolean'
      AND jsonb_typeof(gates->'calendar')='boolean'
      AND (contract->>'tier'='T2' OR
        (gates->'arrival'='true'::jsonb AND gates->'calendar'='true'::jsonb))
    """
    eligibility = (
        f"({predicate})" if browse_mode else f"(NOT admission_review.required OR ({predicate}))"
    )
    return f"({release_holds.SQL_ALLOWED} AND {eligibility})"
