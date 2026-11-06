"""Exact native identity bindings for adding hours without replacing place facts."""

import copy


def native_key(row):
    """Only explicit publisher-native identities, never fuzzy name or nearest matches."""
    sid = row["source_id"]
    keys = set()
    for fact in row.get("provenance", []):
        if not isinstance(fact, dict):
            continue
        if sid.startswith(("nps:", "nps-heritage:", "nps-public:")):
            if (
                fact.get("park_code")
                and fact.get("record_id")
                and "visitor facility" in fact.get("dataset", "").lower()
            ):
                keys.add(("nps-facility", fact["park_code"], str(fact["record_id"])))
        if sid.startswith("usfs:"):
            native = (
                fact.get("published_access_facts", {}).get("construction_feed", {}).get("record_id")
            )
            if native:
                keys.add(("usfs-facility", str(native)))
    return next(iter(keys)) if len(keys) == 1 else None


def bind_calendar(candidate, parent, entry):
    if (
        native_key(candidate) is None
        or native_key(candidate) != native_key(parent)
        or (candidate["latitude"], candidate["longitude"])
        != (parent["latitude"], parent["longitude"])
        or any("source_visit_calendar" in item for item in parent.get("provenance", []))
    ):
        raise ValueError(
            "calendar binding requires an identical native facility and arrival without an existing calendar"
        )
    if entry["source_id"] != candidate["source_id"]:
        raise ValueError("calendar binding differs from source replay")
    result = copy.deepcopy(entry)
    result["source_id"] = parent["source_id"]
    # Supplementary hours never replace the parent's original source release.
    result.pop("source_release", None)
    result["transformation"]["parent_identity_binding"] = {
        "source_facility_id": candidate["source_id"],
        "preserved_parent_id": parent["source_id"],
        "native_identity": list(native_key(parent)),
        "coordinates_unchanged": True,
    }
    return result
