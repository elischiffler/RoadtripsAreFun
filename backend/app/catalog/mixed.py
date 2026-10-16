"""Complete mixed generations assembled only from separately admitted inputs.

The bundle describes retained original artifacts/manifests, not arbitrary
normalized place payloads. Child adapters revalidate every source before stage.
Activation still replaces the whole generation. No downloads/database calls.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

from app.catalog.identity import identity

SCHEMA = "roadtrips-mixed-catalog/1"
SOURCE_URL = "https://github.com/elischiffler/RoadtripsAreFun/issues/36"
SOURCE_SCHEMAS = {
    "roadtrips-overture-places-v1": "overture",
    "kaggle-boulder-trailheads/1": "boulder-osmp",
    "kaggle-nps-arrivals/1": "nps",
    "nps-public-arrivals/1": "nps-public",
    "nps-heritage-arrivals/1": "nps-heritage",
    "kaggle-loc-roadside-arrivals/1": "kaggle-loc-roadside",
    "usfs-public-facilities/1": "usfs",
    "kaggle-usda-markets-reviewed-arrivals/1": "kaggle-usda-markets",
    "kaggle-rideinpark-reviewed-arrivals/1": "kaggle-rideinpark",
}


def read_json(path, ceiling=32_768):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= ceiling:
        raise ValueError("retained JSON input missing or oversized")
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def names(row):
    values = [row["name"]]
    # NPS display names include the parent park. Compare its independently
    # published facility name as well when looking for cross-source duplicates.
    if " — " in row["name"]:
        values.append(row["name"].split(" — ", 1)[1])
    return {
        "".join(c for c in unicodedata.normalize("NFKD", s).casefold() if c.isalnum())
        for s in values
    }


def distance(a, b):
    la, lb = math.radians(a["latitude"]), math.radians(b["latitude"])
    dl = math.radians(a["longitude"] - b["longitude"])
    return (
        6371000
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin((la - lb) / 2) ** 2
                    + math.cos(la) * math.cos(lb) * math.sin(dl / 2) ** 2
                ),
            )
        )
    )


def assemble(bundle, *, max_rows, max_bytes):
    from app.catalog.ingest import prepare

    inputs = bundle.get("inputs")
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 30:
        raise ValueError("mixed bundle requires 1..30 reviewed source inputs")
    rows, sources, licenses = {}, {}, {}
    source_reports = []
    total_bytes = scanned = duplicates = 0
    for item in inputs:
        child, sha = read_json(item["manifest"])
        if sha != item.get("manifest_sha256"):
            raise ValueError("child manifest checksum mismatch")
        source = SOURCE_SCHEMAS.get(child.get("schema_version"))
        if source is None:
            raise ValueError(
                "mixed bundle accepts explicit source adapters only; nesting is refused"
            )
        metadata = {"release": child["release"], "attribution": child["attribution"]}
        if source in sources:
            if sources[source]["release"] != metadata["release"]:
                raise ValueError("mixed source inputs require one consistent source release")
            metadata["attribution"] = "; ".join(
                sorted(
                    set(sources[source]["attribution"].split("; "))
                    | set(metadata["attribution"].split("; "))
                )
            )
        sources[source] = metadata
        for identifier, evidence in child["licenses"].items():
            if identifier in licenses and (
                licenses[identifier]["sha256"] != evidence["sha256"]
                or licenses[identifier].get("notice", {}).get("sha256")
                != evidence.get("notice", {}).get("sha256")
            ):
                raise ValueError("conflicting source license evidence")
            licenses[identifier] = evidence
        admitted, report = prepare(item["path"], child, max_rows=max_rows, max_bytes=max_bytes)
        source_reports.append(
            {"source": source, "artifact_sha256": child["sha256"], "report": report}
        )
        scanned += report["scanned"]
        total_bytes += report["bytes"]
        if total_bytes > max_bytes or scanned > 50_000:
            raise ValueError("mixed aggregate source row/byte ceiling exceeded")
        if not admitted:
            raise ValueError("empty source input cannot enter a mixed generation")
        for row in admitted:
            key, actual_source = identity(row["source_id"])
            if actual_source != source:
                raise ValueError("source adapter returned an unexpected identity namespace")
            if key in rows:
                if row != rows[key]:
                    raise ValueError("conflicting duplicate identity across source inputs")
                duplicates += 1
                continue
            rows[key] = row
            if len(rows) > max_rows:
                raise ValueError("mixed unique row ceiling exceeded")
    merges = bundle.get("deduplications", [])
    if not isinstance(merges, list) or len(merges) > 500:
        raise ValueError("mixed deduplication mapping oversized")
    for rule in merges:
        keep, donor = rule.get("keep"), rule.get("merge")
        if keep == donor or keep not in rows or donor not in rows:
            raise ValueError("deduplication references missing/identical identities")
        a, b = rows[keep], rows[donor]
        if (
            a["region"] != b["region"]
            or not names(a).intersection(names(b))
            or distance(a, b) > 250
        ):
            raise ValueError("deduplication lacks matching name, state and spatial evidence")
        if not isinstance(rule.get("evidence_url"), str) or not rule["evidence_url"].startswith(
            "https://"
        ):
            raise ValueError("deduplication requires reviewed public evidence")
        a["provenance"] = (
            a["provenance"]
            + [
                {
                    "dataset": "Roadtrips reviewed source mapping",
                    "provider_id": donor,
                    "evidence_url": rule["evidence_url"],
                    "source_release": sources[identity(b["source_id"])[1]]["release"],
                    "source_attribution": sources[identity(b["source_id"])[1]]["attribution"],
                }
            ]
            + b["provenance"]
        )
        del rows[donor]
        duplicates += 1
    # Report exact-name colocated records for review; never silently merge by
    # proximity, and never promote an unresolved duplicate into accepted counts.
    by_name = {}
    for key, row in rows.items():
        for name in names(row):
            for other_key, other in by_name.get((row["region"], name), []):
                if distance(row, other) <= 100:
                    raise ValueError(f"unresolved colocated identity: {key} / {other_key}")
            by_name.setdefault((row["region"], name), []).append((key, row))
    regions, categories, source_counts = Counter(), Counter(), Counter()
    for key, row in rows.items():
        regions[row["region"]] += 1
        source_counts[identity(row["source_id"])[1]] += 1
        categories.update(row["categories"])
    return (
        list(rows.values()),
        sources,
        licenses,
        {
            "scanned": scanned,
            "accepted": len(rows),
            "bytes": total_bytes,
            "duplicates": duplicates,
            "rejects": {},
            "regions": dict(regions),
            "categories": dict(categories),
            "source_counts": dict(source_counts),
            "source_reports": source_reports,
        },
    )


def prepare(path, manifest, *, max_rows, max_bytes):
    if manifest.get("source_url") != SOURCE_URL or not re.fullmatch(
        r"pilot-\d{4}-\d{2}-\d{2}\.\d+", manifest.get("release", "")
    ):
        raise ValueError("mixed manifest requires an explicit dated pilot release")
    bundle, sha = read_json(path)
    if sha != manifest.get("sha256"):
        raise ValueError("mixed bundle checksum mismatch")
    rows, sources, licenses, report = assemble(bundle, max_rows=max_rows, max_bytes=max_bytes)
    if (
        sources != manifest.get("source_catalogs")
        or licenses != manifest.get("licenses")
        or manifest.get("attribution") != "; ".join(s["attribution"] for s in sources.values())
    ):
        raise ValueError("mixed manifest source/rights metadata differs from admitted inputs")
    return rows, report
