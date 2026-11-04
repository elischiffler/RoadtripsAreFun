"""Pure effective calendar projection shared by runtime and ingestion."""

import copy


def project(provenance, entry):
    """Expose one effective calendar while retaining the superseded source facts."""
    result = copy.deepcopy(provenance)
    if entry is None:
        return result
    for item in result:
        if "source_visit_calendar" in item:
            item["superseded_source_visit_calendar"] = item.pop("source_visit_calendar")
    result.append({"dataset": "Roadtrips attributed calendar enrichment", **copy.deepcopy(entry)})
    return result
