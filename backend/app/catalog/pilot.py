"""Replay field evidence and exclusion-only reviews for a bounded browse pilot.

This adapter admits T2 physical destinations only. It never manufactures arrival
points, calendars or routing eligibility. Agent-assisted source review and byte replay
remain distinct: proof bindings detect changed facts, not whether a publisher is
truthful or whether a place is open at a future arrival.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import math
import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.catalog import pilot_personas, usfs
from app.catalog.mixed import distance, names

SCHEMA = "roadtrips-reviewed-browse-pilot/1"
MAX_RECORDS = 600
MAX_BYTES = 64 * 1024 * 1024
SOURCE_LICENSES = {
    "baltimore-heritage": "CC-BY-4.0",
    "wikidata": "CC0-1.0",
    "nps-nhl": "LicenseRef-US-Agency-Factual-Data",
    "nys-historic": "LicenseRef-NY-Open-Data",
    "ny-market": "LicenseRef-NY-Open-Data",
    "sf-civic-art": "PDDL-1.0",
    "fws": "LicenseRef-US-Agency-Factual-Data",
    "blm": "LicenseRef-US-Agency-Factual-Data",
}
SOURCE_HOSTS = {
    "baltimore-heritage": {"explore.baltimoreheritage.org"},
    "wikidata": {"query.wikidata.org", "www.wikidata.org"},
    "nps-nhl": {"mapservices.nps.gov"},
    "nys-historic": {"data.ny.gov"},
    "ny-market": {"data.ny.gov"},
    "sf-civic-art": {"data.sf.gov", "data.sfgov.org"},
    "fws": {"services.arcgis.com", "services3.arcgis.com", "gis.fws.gov"},
    "blm": {"gis.blm.gov"},
}
NATIVE_PATHS = {
    "baltimore-heritage": {f"/items/show/{n}" for n in (82, 200, 392, 396)},
    "wikidata": {"/sparql"},
    "nps-nhl": {
        f"/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer/{n}/query"
        for n in (0, 1)
    },
    "nys-historic": {"/resource/m384-u5q6.json"},
    "ny-market": {"/resource/qq4h-8p86.json"},
    "sf-civic-art": {"/resource/r7bn-7v9c.json"},
    "fws": {
        "/QVENGdaPbd4LUkLV/arcgis/rest/services/FWS_HQ_Fac_Building_Pt_PubicView/FeatureServer/0/query",
        "/QVENGdaPbd4LUkLV/arcgis/rest/services/FWS_HQ_Tran_Gate_Access_PublicView/FeatureServer/0/query",
    },
    "blm": {
        f"/natl/rest/services/recreation/BLM_Natl_Recs_pts/FeatureServer/{n}/query"
        for n in (6, 10, 13, 15, 17, 20, 21)
    },
}
NY_TERMS_PATH = "/api/views/77gx-ii52/files/ef0c1840-ad54-4240-92fd-6397c49fde46"
RIGHTS_TARGETS = {
    "baltimore-heritage": {("explore.baltimoreheritage.org", "/")},
    "wikidata": {("www.wikidata.org", "/wiki/Wikidata:Copyright")},
    "nps-nhl": {("www.nps.gov", "/aboutus/disclaimer.htm"), ("www.doi.gov", "/copyright")},
    "fws": {("www.fws.gov", "/disclaimer"), ("www.doi.gov", "/copyright")},
    "blm": {("www.blm.gov", "/info/notices/drctp-policy"), ("www.doi.gov", "/copyright")},
    "nys-historic": {("data.ny.gov", NY_TERMS_PATH)},
    "ny-market": {("data.ny.gov", NY_TERMS_PATH)},
    "sf-civic-art": {
        ("data.sf.gov", "/api/views/r7bn-7v9c.json"),
        ("data.sfgov.org", "/api/views/r7bn-7v9c.json"),
    },
}
# Reviewed original notices, 2026-10-21. Changed notices require a new explicit
# rights review; neither a caller-supplied label nor a convenient excerpt grants
# commercial rights. Source records/operators remain separately reviewed.
RIGHTS_PINS = {
    "baltimore-heritage": {"534efb5e95b0ce925e904fa0f4276c3ffef3ace06eddef8fbbdb120e9a8397a7"},
    "wikidata": {
        "3e5d1bc82606c2ca57c41baaaa254a6b2de948fea61b8ef6ae1fe050d4c9416d",
        "e0744a22fe6ed5e46fa537e41625f26f560c9eb1a34cb28db4ef52b03a2f618e",
    },
    "nps-nhl": {"1b3b523964301d1c30ec8d6243cc551e99cac340b187c8883b356d93bea5e363"},
    "fws": {"af669cd6a33bae15fe9dd714a344b166c3c47e0495dea682c471f5ac804d88c0"},
    "blm": {
        "af669cd6a33bae15fe9dd714a344b166c3c47e0495dea682c471f5ac804d88c0",
        "ff96b94f8dda0b7531bda06b18e8b94bc1b362a749ad11bf613ec8acd5c91c32",
    },
    "ny-market": {"9437c849705d58df008f01fc23f404444becce6b86676adc3974f9160a4cb650"},
    "nys-historic": {"9437c849705d58df008f01fc23f404444becce6b86676adc3974f9160a4cb650"},
    "sf-civic-art": set(),
}
FWS_STEWARD_ITEM = (
    "https://www.arcgis.com/sharing/rest/content/items/a8166d1ed8c24a0aba9078bfa5fdd84f"
)
FWS_STEWARD_SHA = "fb55f63981fcd3ed119b7c69c6fa5034ad3e859c79b677241ebae465c3506ab9"
FWS_EXCEPTIONS_SHA = "a2f5e9be2ccf5fb39f4d5845d2a518decb05e0d3b77f913e112394229c1b18d4"


def plain(text):
    return " ".join(re.sub(r"<[^>]*>", " ", html.unescape(text)).split())


@lru_cache(maxsize=32)
def evidence_text(body):
    if body.startswith(b"%PDF"):
        from pypdf import PdfReader

        document = PdfReader(io.BytesIO(body))
        if len(document.pages) > 40:
            raise ValueError("rights PDF exceeds bounded page count")
        text = " ".join(page.extract_text() or "" for page in document.pages)
        if len(text) > 250_000:
            raise ValueError("rights PDF text exceeds bounded extraction")
        return plain(text)
    return plain(body.decode("utf-8"))


def pointer(document, value):
    """Resolve an explicit RFC6901 pointer; no search, evaluation or heuristics."""
    if not isinstance(value, str) or (value and not value.startswith("/")):
        raise ValueError("invalid source JSON pointer")
    for part in value.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def source_host(family, url):
    target = urlparse(url)
    return (
        target.scheme == "https"
        and target.hostname in SOURCE_HOSTS[family]
        and target.path in NATIVE_PATHS[family]
        and (
            family != "baltimore-heritage"
            or parse_qs(target.query).get("output") == ["mobile-json"]
        )
    )


def _native_aliases(row):
    aliases = {row["source_id"]}
    for fact in row.get("provenance", []):
        stored = fact.get("aliases", [])
        if isinstance(stored, list):
            aliases.update(value for value in stored if isinstance(value, str))
        for key in ("wikidata_id", "qid", "nris_refnum", "national_register_id"):
            if value := fact.get(key):
                aliases.add(str(value))
    for value in list(aliases):
        tail = value.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if re.fullmatch(r"Q\d+", tail):
            aliases.add(tail)
    return aliases


def _native_source_rows(evidence):
    seen, count = set(), 0
    for receipt, body in evidence.values():
        if receipt["sha256"] in seen or not any(
            source_host(family, receipt["url"]) for family in SOURCE_LICENSES
        ):
            continue
        seen.add(receipt["sha256"])
        document = json.loads(body)
        if receipt["url"].startswith("https://explore.baltimoreheritage.org/items/show/"):
            if not isinstance(document, dict) or type(document.get("id")) is not int:
                raise ValueError("Baltimore source is not one native item")
            count += 1
            continue
        rows = (
            document
            if isinstance(document, list)
            else document.get("features", document.get("results", {}).get("bindings", []))
        )
        if not isinstance(rows, list):
            raise ValueError("native source body is not a bounded row collection")
        count += len(rows)
    return count


def _value(binding, evidence, *, family=None):
    if isinstance(binding, dict) and binding.get("transform") == "sha256_fields":
        fields = binding.get("fields")
        if not isinstance(fields, list) or not 2 <= len(fields) <= 6:
            raise ValueError("derived source identity requires two to six native fields")
        values = [_value(field, evidence, family=family) for field in fields]
        if any(
            not isinstance(value, (str, int, float)) or isinstance(value, bool) for value in values
        ):
            raise ValueError("derived source identity contains a missing or composite field")
        encoded = json.dumps(values, separators=(",", ":"), allow_nan=False).encode()
        return "derived-" + hashlib.sha256(encoded).hexdigest()[:32]
    if not isinstance(binding, dict) or binding.get("evidence_id") not in evidence:
        raise ValueError("missing native field evidence")
    receipt, body = evidence[binding["evidence_id"]]
    if family and (
        not source_host(family, receipt["url"])
        or not source_host(family, receipt.get("final_url", receipt["url"]))
    ):
        raise ValueError("native field evidence is not an approved primary source")
    value = pointer(json.loads(body), binding["pointer"])
    if binding.get("transform") == "url_tail":
        if not isinstance(value, str):
            raise ValueError("native URL identity is not a string")
        value = str(value).rstrip("/").rsplit("/", 1)[-1]
    elif binding.get("transform") == "uuid":
        value = str(uuid.UUID(value))
    elif binding.get("transform") is not None:
        raise ValueError("unreviewed native field transform")
    return value


def _coordinates(spec, evidence, family):
    kind = spec["encoding"]
    if kind == "latlon":
        lat = _value(spec["latitude"], evidence, family=family)
        lon = _value(spec["longitude"], evidence, family=family)
    else:
        value = _value(spec["value"], evidence, family=family)
        if kind == "wkt":
            match = re.fullmatch(r"Point\((-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\)", value)
            if not match:
                raise ValueError("native point is not finite WGS84 WKT")
            lon, lat = match.groups()
        elif kind == "geojson":
            lon, lat = value
        elif kind == "arcgis":
            lon, lat = value["x"], value["y"]
        else:
            raise ValueError("unreviewed source coordinate encoding")
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("invalid boolean coordinate")
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat + lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("native point is not finite WGS84")
    return lat, lon


def _proofs(items, evidence, *, label):
    """Replay literal evidence selected in a named, agent-assisted source review."""
    if not isinstance(items, list) or not items:
        raise ValueError(f"missing {label} evidence")
    output = []
    for proof in items:
        receipt, body = evidence[proof["evidence_id"]]
        excerpt = proof.get("literal")
        if not isinstance(excerpt, str) or not 5 <= len(excerpt) <= 500:
            raise ValueError(f"missing bounded {label} evidence fragment")
        if plain(excerpt).casefold() not in evidence_text(body).casefold():
            raise ValueError(f"retained {label} evidence fragment differs")
        output.append(
            {
                "source_url": receipt["url"],
                "snapshot_sha256": receipt["sha256"],
                "checked_at": receipt["checked_at"],
                "evidence_path": receipt["path"],
            }
        )
    return output


def _native_receipts(bindings, evidence):
    identifiers = set()

    def walk(value):
        if isinstance(value, dict):
            if "evidence_id" in value:
                identifiers.add(value["evidence_id"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(bindings)
    return [
        {
            "source_url": evidence[key][0]["url"],
            "snapshot_sha256": evidence[key][0]["sha256"],
            "checked_at": evidence[key][0]["checked_at"],
            "evidence_path": evidence[key][0]["path"],
        }
        for key in sorted(identifiers)
    ]


def _same_native_entity(bindings, family):
    """A source ID, name and point must descend from the same original row.

    Approved-host checks alone cannot prevent mixing fields from unrelated
    entities in a broad query result. Cross-receipt joins need a separate typed
    source contract and are deliberately not supported by this pilot adapter.
    """
    leaves = []

    def walk(value):
        if isinstance(value, dict):
            if "evidence_id" in value:
                leaves.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(bindings)
    if family == "baltimore-heritage":
        if (
            len(leaves) != 4
            or len({leaf["evidence_id"] for leaf in leaves}) != 1
            or {leaf.get("pointer") for leaf in leaves}
            != {"/id", "/title", "/latitude", "/longitude"}
        ):
            raise ValueError("Baltimore native facts must belong to one complete original item")
        return leaves[0]["evidence_id"], ""
    pattern = (
        r"^(/results/bindings/\d+)/"
        if family == "wikidata"
        else r"^(/\d+)/"
        if family in {"ny-market", "nys-historic", "sf-civic-art"}
        else r"^(/features/\d+)/"
    )
    anchors = set()
    for binding in leaves:
        match = re.match(pattern, binding.get("pointer", ""))
        if match is None:
            raise ValueError("native field does not identify a source record anchor")
        anchors.add((binding["evidence_id"], match[1]))
    if len(anchors) != 1 or len(leaves) < 3:
        raise ValueError("native identity/name/point refer to different source entities")
    return next(iter(anchors))


def _source_contract(record, family, evidence, anchor):
    """Check primary dataset/steward rights, not a platform-wide blanket grant."""
    bindings = record["bindings"]
    native, name = bindings["native_id"], bindings["name"]
    id_fields = {
        "baltimore-heritage": "/id",
        "wikidata": "/item/value",
        "nps-nhl": "/attributes/NRIS_Refnum",
        "fws": "/attributes/OrgCode",
        "blm": "/attributes/GlobalID",
        "ny-market": "/:id",
        "nys-historic": "/:id",
        "sf-civic-art": "/accession_number",
    }
    name_fields = {
        "baltimore-heritage": "/title",
        "wikidata": "/itemLabel/value",
        "nps-nhl": "/attributes/RESNAME",
        "fws": "/attributes/OrgName",
        "blm": "/attributes/FET_NAME",
        "ny-market": "/market_name",
        "nys-historic": "/name",
        "sf-civic-art": "/display_title",
    }
    if name.get("pointer") != anchor[1] + name_fields[family] or name.get("transform") is not None:
        raise ValueError("native name does not use the reviewed source field")
    if native.get("transform") == "sha256_fields" and family in {"ny-market", "nys-historic"}:
        allowed = {"/:id", "/market_name", "/name", "/address_line_1", "/latitude", "/longitude"}
        if any(
            field.get("pointer", "").removeprefix(anchor[1]) not in allowed
            for field in native["fields"]
        ):
            raise ValueError("derived identity uses unreviewed source fields")
    elif native.get("pointer") != anchor[1] + id_fields[family]:
        raise ValueError("native identity does not use the reviewed identifier field")
    expected_transform = "url_tail" if family == "wikidata" else "uuid" if family == "blm" else None
    if native.get("transform") not in {
        expected_transform,
        "sha256_fields" if family in {"ny-market", "nys-historic"} else expected_transform,
    }:
        raise ValueError("native identity transform differs from source contract")
    if family in {"nps-nhl", "fws", "blm"}:
        receipt = evidence[anchor[0]][0]
        if parse_qs(urlparse(receipt["url"]).query).get("outSR") != ["4326"]:
            raise ValueError("agency geometry was not acquired in explicit WGS84")
        if (
            bindings["coordinates"].get("encoding") != "arcgis"
            or bindings["coordinates"].get("value", {}).get("pointer") != anchor[1] + "/geometry"
        ):
            raise ValueError("agency point is not its original native geometry")
    if family == "wikidata" and (
        bindings["coordinates"].get("encoding") != "wkt"
        or bindings["coordinates"].get("value", {}).get("pointer") != anchor[1] + "/coord/value"
    ):
        raise ValueError("Wikidata point is not the reviewed coordinate field")
    if family == "wikidata":
        document = json.loads(evidence[anchor[0]][1])
        chosen = pointer(document, anchor[1])
        locations = {
            row.get("coord", {}).get("value")
            for row in document["results"]["bindings"]
            if row.get("item", {}).get("value") == chosen.get("item", {}).get("value")
            and row.get("coord", {}).get("value")
        }
        if len(locations) > 1:
            raise ValueError(
                "multiple retained native coordinates require an explicit location review"
            )
    if family == "nps-nhl":
        document = json.loads(evidence[anchor[0]][1])
        chosen = pointer(document, anchor[1])["attributes"]
        entities = {
            row["attributes"].get("RESNAME")
            for row in document["features"]
            if row["attributes"].get("NRIS_Refnum") == chosen.get("NRIS_Refnum")
        }
        if len(entities) > 1:
            raise ValueError(
                "register reference spans multiple named entities; identity scope unresolved"
            )
    if family in {"ny-market", "nys-historic", "sf-civic-art"}:
        expected = ("/y", "/x") if family == "nys-historic" else ("/latitude", "/longitude")
        coordinates = bindings["coordinates"]
        if coordinates.get("encoding") != "latlon" or any(
            coordinates.get(key, {}).get("pointer") != anchor[1] + suffix
            for key, suffix in zip(("latitude", "longitude"), expected, strict=True)
        ):
            raise ValueError("Socrata point is not the reviewed native latitude/longitude fields")
    if family == "baltimore-heritage":
        document = json.loads(evidence[anchor[0]][1])
        receipt = evidence[anchor[0]][0]
        if type(document.get("id")) is not int or any(
            urlparse(url).path != f"/items/show/{document['id']}"
            for url in (receipt["url"], receipt.get("final_url", receipt["url"]))
        ):
            raise ValueError("Baltimore item identifier differs from original endpoint")
        coordinates = bindings["coordinates"]
        if coordinates.get("encoding") != "latlon" or any(
            coordinates.get(key, {}).get("pointer") != "/" + key
            for key in ("latitude", "longitude")
        ):
            raise ValueError("Baltimore point differs from original item coordinate fields")
        if document.get("creator") == ["Theresa Donnelly"] and document["id"] == 82:
            # The named contributor's item page independently repeats the
            # publisher's CC BY4.0 grant. Do not generalize it to other authors,
            # item text versions or separately licensed photographs.
            if not any(
                r["sha256"] == "12b8c9a9c365c1f7556b1b6fb6e25e3dc3e3f0d73b5665ca62ba8b0f53f2c22a"
                and r["url"] == "https://explore.baltimoreheritage.org/items/show/82"
                and "Creative Commons Attribution 4.0 International License" in evidence_text(body)
                and "Theresa Donnelly" in evidence_text(body)
                for r, body in evidence.values()
            ):
                raise ValueError("Baltimore contributor item lacks its reviewed attribution/grant")
        elif document.get("creator") != ["Explore Baltimore Heritage"]:
            raise ValueError("Baltimore factual item has unreviewed creator/rights scope")
    for proof in record["rights_proofs"]:
        receipt = evidence[proof["evidence_id"]][0]
        if receipt["sha256"] not in RIGHTS_PINS[family]:
            raise ValueError("rights notice version has not received the pinned source review")
        for raw in (receipt["url"], receipt.get("final_url", receipt["url"])):
            target = urlparse(raw)
            if (
                target.scheme != "https"
                or (target.hostname, target.path) not in RIGHTS_TARGETS[family]
            ):
                raise ValueError("rights evidence is not the reviewed source-family grant")
    if family == "fws":
        native = pointer(json.loads(evidence[anchor[0]][1]), anchor[1])["attributes"]
        if (
            native.get("Owner") != "Fish and Wildlife Service"
            or native.get("Status") != "Valid"
            or native.get("Pub_Use", native.get("Public_Use")) != "Public Use"
        ):
            raise ValueError("FWS original agency ownership/public-use fields are unresolved")
        steward = [
            receipt
            for receipt, _ in evidence.values()
            if receipt["sha256"] == FWS_STEWARD_SHA
            and receipt["url"].split("?", 1)[0] == FWS_STEWARD_ITEM
            and receipt.get("final_url", receipt["url"]).split("?", 1)[0] == FWS_STEWARD_ITEM
        ]
        exceptions = [
            receipt
            for receipt, _ in evidence.values()
            if receipt["sha256"] == FWS_EXCEPTIONS_SHA
            and receipt["url"] == "https://www.fws.gov/disclaimer"
        ]
        if not steward or not exceptions:
            raise ValueError("pinned FWS agency lineage/third-party exceptions evidence is missing")
        if "FWS_HQ_Fac_Building_Pt_PubicView" not in evidence[anchor[0]][0]["url"]:
            raise ValueError("FWS asset family requires its own reviewed stewardship contract")
        return [
            {
                "source_url": receipt["url"],
                "snapshot_sha256": receipt["sha256"],
                "checked_at": receipt["checked_at"],
                "evidence_path": receipt["path"],
            }
            for receipt in steward + exceptions
        ]
    return []


def prepare(path, manifest, *, max_rows=50_000, max_bytes=MAX_BYTES):
    """Return reviewed browse rows and all holds, preserving original facts."""
    from app.catalog import admission
    from app.catalog.calendar_enrichment import Reader

    path = Path(path).resolve()
    if not 1 <= max_bytes <= 100 * 1024 * 1024 or not 1 <= max_rows <= 50_000:
        raise ValueError("pilot replay exceeds unchanged importer ceilings")
    if not path.is_file() or not 0 < path.stat().st_size <= min(max_bytes, 8 * 1024 * 1024):
        raise ValueError("pilot artifact exceeds byte ceiling")
    raw = path.read_bytes()
    if manifest.get("schema_version") != SCHEMA or hashlib.sha256(raw).hexdigest() != manifest.get(
        "sha256"
    ):
        raise ValueError("reviewed pilot manifest differs")
    payload = json.loads(raw)
    records = payload.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= min(MAX_RECORDS, max_rows):
        raise ValueError("pilot requires a bounded prospect denominator")
    if len({r["pilot_id"] for r in records}) != len(records):
        raise ValueError("pilot prospect identities are not unique")
    reader = Reader(path.parent, min(MAX_BYTES, max_bytes) - len(raw))
    evidence = {}
    for receipt in payload.get("evidence", []):
        ident = receipt["id"]
        if ident in evidence or receipt.get("status") != 200:
            raise ValueError("pilot evidence receipt is duplicate or unsuccessful")
        stamp = datetime.fromisoformat(receipt["checked_at"].replace("Z", "+00:00"))
        if (
            stamp.tzinfo is None
            or stamp.timestamp() > datetime.now(UTC).timestamp()
            or urlparse(receipt["url"]).scheme != "https"
        ):
            raise ValueError("pilot evidence requires dated public HTTPS provenance")
        evidence[ident] = receipt, reader.read(receipt["path"], receipt["sha256"])
    states = payload["states"]
    shapes = usfs.state_shapes(json.loads(reader.read(states["path"], states["sha256"])))
    parent = payload["local_baseline"]
    baseline = json.loads(reader.read(parent["path"], parent["sha256"]))
    if not isinstance(baseline, list) or not 1 <= len(baseline) <= max_rows - len(records):
        raise ValueError("local duplicate comparison baseline exceeds row ceiling")
    baseline_aliases = set().union(*(_native_aliases(row) for row in baseline))
    native_scanned = _native_source_rows(evidence)
    scanned = len(records) + len(baseline) + native_scanned + 56
    if scanned > max_rows:
        raise ValueError(
            "pilot source, baseline and Census rows exceed unchanged aggregate ceiling"
        )
    excluded = payload.get("documented_later_exclusion_ids", [])
    if (
        not isinstance(excluded, list)
        or len(excluded) > 1000
        or any(not isinstance(value, str) or not 1 <= len(value) <= 512 for value in excluded)
    ):
        raise ValueError("documented later exclusions are not a bounded identity list")
    for value in excluded:
        baseline_aliases.update(_native_aliases({"source_id": value, "provenance": []}))
    observed_at = datetime.now(UTC).timestamp()
    now = int(observed_at)
    rows, profiles, decisions = [], [], []
    for record in records:
        reason = record.get("hold_reason") or "source_review_pending"
        if record.get("review", {}).get("decision") != "T2":
            decisions.append({"pilot_id": record["pilot_id"], "tier": "T1", "reason": reason})
            continue
        try:
            family, review = record["source_family"], record["review"]
            if family not in SOURCE_LICENSES:
                raise ValueError("source family has no reviewed field-rights contract")
            if review.get("license") != SOURCE_LICENSES[family]:
                raise ValueError("source license differs from reviewed family")
            anchor = _same_native_entity(record["bindings"], family)
            stewardship = _source_contract(record, family, evidence, anchor)
            if (
                not review.get("reviewer")
                or not review.get("reason")
                or not all(
                    review.get(key) is True
                    for key in (
                        "operator_is_primary",
                        "public_visit_affirmed",
                        "closure_conflicts_reviewed",
                    )
                )
            ):
                raise ValueError("affirmative named operator review is incomplete")
            rights = _proofs(record["rights_proofs"], evidence, label="rights")
            access = _proofs(record["access_proofs"], evidence, label="public visit")
            operator_identity = _proofs(
                record["operator_identity_location_proofs"],
                evidence,
                label="operator identity/location",
            )
            operator_host = urlparse(record["operator_url"]).hostname
            if (
                urlparse(record["operator_url"]).scheme != "https"
                or not operator_host
                or not all(
                    urlparse(proof["source_url"]).hostname.removeprefix("www.")
                    == operator_host.removeprefix("www.")
                    for proof in access + operator_identity
                )
            ):
                raise ValueError("public visit evidence differs from reviewed operator")
            if any(
                not 0
                <= observed_at
                - datetime.fromisoformat(proof["checked_at"].replace("Z", "+00:00")).timestamp()
                <= 31 * 86400
                for proof in access + operator_identity
            ):
                raise ValueError("public visit evidence acquisition is stale or in the future")
            native_value = _value(record["bindings"]["native_id"], evidence, family=family)
            if type(native_value) not in {str, int} or native_value == "":
                raise ValueError("native identity is not a nonempty original scalar")
            native_id = str(native_value)
            if not (
                re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", native_id)
                or family == "ny-market"
                and re.fullmatch(r"row-[a-z0-9]{4}[~_.-][a-z0-9]{4}[~_.-][a-z0-9]{4}", native_id)
            ):
                raise ValueError("native identity is missing or ambiguous")
            if family == "wikidata" and not re.fullmatch(r"Q[1-9][0-9]*", native_id):
                raise ValueError("Wikidata native identity is not a QID")
            if family == "fws" and not re.fullmatch(r"[0-9]{4,6}", native_id):
                raise ValueError("FWS native identity is not an organization code")
            if family == "nps-nhl" and not re.fullmatch(r"[0-9]{6,10}", native_id):
                raise ValueError("NPS native identity is not a reviewed register reference")
            if family == "baltimore-heritage" and not re.fullmatch(r"[1-9][0-9]{0,7}", native_id):
                raise ValueError("Baltimore item identifier is invalid")
            aliases = record.get("aliases", [])
            if (
                not isinstance(aliases, list)
                or len(aliases) > 100
                or any(
                    not isinstance(value, str) or not 1 <= len(value) <= 512 for value in aliases
                )
            ):
                raise ValueError("source aliases are not bounded nonempty identities")
            name = _value(record["bindings"]["name"], evidence, family=family)
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 180:
                raise ValueError("native destination name is missing or oversized")
            lat, lon = _coordinates(record["bindings"]["coordinates"], evidence, family)
            state = usfs.state_for([lat, lon], shapes)
            if state is None or state != record["state"]:
                raise ValueError("native point conflicts with Census state containment")
            category = record["category"]
            if category not in pilot_personas.RULES:
                raise ValueError("source category has no reviewed persona rule")
            sid = f"catalog-pilot:{family}:{native_id}"
            reviewed = review["reviewed_at_epoch"]
            if type(reviewed) is not int or not 0 <= now - reviewed <= 31 * 86400:
                raise ValueError("operator/source review is stale or in the future")
            marker = {
                "schema_version": "roadtrips-catalog-admission/1",
                "source_id": sid,
                "tier": "T2",
                "review_status": "approved",
                "reviewed_at_epoch": reviewed,
                "expires_at_epoch": reviewed + 30 * 86400,
                "gates": dict.fromkeys(
                    ("rights", "identity", "location", "public_access", "local_duplicate_review"),
                    True,
                )
                | {"arrival": False, "calendar": False},
            }
            row = {
                "source_id": sid,
                "name": name.strip(),
                "latitude": lat,
                "longitude": lon,
                "region": state,
                "categories": sorted(
                    {category, "catalog_browse", "culture"}
                    if category
                    in {
                        "museum",
                        "science_center",
                        "historic_site",
                        "public_art",
                        "industrial_heritage",
                        "lighthouse",
                        "heritage_rail",
                    }
                    else {category, "catalog_browse"}
                ),
                "address": None,
                "url": record["operator_url"],
                "source_updated_at": None,
                "provenance": [
                    {
                        "dataset": "Roadtrips reviewed pilot native feature facts",
                        "source_family": family,
                        "native_id": native_id,
                        "native_id_kind": "derived_native_field_key"
                        if record["bindings"]["native_id"].get("transform") == "sha256_fields"
                        else "publisher_identifier",
                        "aliases": record.get("aliases", []),
                        "source_bindings": record["bindings"],
                        "native_source_evidence": _native_receipts(record["bindings"], evidence),
                        "agency_stewardship_evidence": stewardship,
                        "state_classification": {
                            "source_url": usfs.STATE_URL,
                            "snapshot_sha256": states["sha256"],
                            "method": "Census2025 polygon containment; not a surveyed arrival",
                        },
                        "license": review["license"],
                        "source_attribution": f"{family} original factual identity/feature fields, {review['license']}; operator public-visit facts reviewed separately. State classification: U.S. Census Bureau ACS2025. No endorsement or live availability claim.",
                        "rights_evidence": rights,
                        "public_visit_evidence": access,
                        "operator_identity_location_evidence": operator_identity,
                        "reviewer": review["reviewer"],
                        "review_method": "Codex-assisted source reading and deterministic replay; no independent human signoff or field survey",
                        "classification_basis": "Codex-assisted classification of native facility and operator context; not a publisher taxonomy or a verified activity inventory",
                        "review_reason": review["reason"],
                        "reviewed_constraints": record.get(
                            "constraints", record.get("source_constraints", [])
                        ),
                        "public_access_status": record.get(
                            "public_access_status",
                            record.get(
                                "public_access_mode",
                                "public_visitor_purpose_confirmed; operating_status_unknown",
                            ),
                        ),
                        "point_role": "physical_feature_not_verified_arrival",
                        "limitations": "Source-reviewed identity/location/public visitor purpose; not field verification, current availability or routing readiness.",
                        "live_parent_reconciled": False,
                    },
                    {"dataset": "Roadtrips catalog admission", "catalog_admission": marker},
                ],
            }
            aliases = _native_aliases(row) | set(record.get("aliases", []))
            if family == "baltimore-heritage":
                native_document = json.loads(evidence[anchor[0]][1])
                row["provenance"][0]["source_attribution"] = (
                    f"{', '.join(native_document['creator'])}; Explore Baltimore Heritage / Baltimore Heritage, Inc., {name.strip()}, "
                    f"https://explore.baltimoreheritage.org/items/show/{native_id}, "
                    "CC BY4.0 https://creativecommons.org/licenses/by/4.0/. "
                    "Factual fields extracted; category and traveler-fit inferences added. "
                    "Photos and article prose excluded; no endorsement."
                )
                row["provenance"][0]["native_creator"] = native_document["creator"]
                row["provenance"][0]["native_modified"] = native_document.get("modified")
            if aliases & baseline_aliases or any(
                aliases & _native_aliases(other)
                or row["region"] == other["region"]
                and names(row) & names(other)
                or distance(row, other) < 250
                for other in [*baseline, *rows]
            ):
                raise ValueError("unresolved local identity/name/250m duplicate or co-location")
            if not admission.browse_eligible(row) or admission.routing_eligible(row):
                raise ValueError("pilot browse/routing tier contract differs")
            profile = pilot_personas.build(
                row,
                category,
                marker,
                release=manifest.get("release", "catalog-pilot-600-20261021"),
            )
            row["provenance"].append(pilot_personas.stored(profile))
            rows.append(row)
            profiles.append(profile)
            decisions.append(
                {
                    "pilot_id": record["pilot_id"],
                    "source_id": sid,
                    "tier": "T2",
                    "reason": "source_review_replayed; live_parent_reconciliation_pending",
                }
            )
        except (ValueError, TypeError, KeyError, IndexError, UnicodeError) as exc:
            decisions.append({"pilot_id": record["pilot_id"], "tier": "T1", "reason": str(exc)})
    return rows, {
        "scanned": scanned,
        "native_source_rows": native_scanned,
        "prospects": len(records),
        "accepted": len(rows),
        "bytes": len(raw) + reader.bytes,
        "calendar_entries": [],
        "profiles": profiles,
        "decisions": decisions,
        "held_reasons": dict(Counter(item["reason"] for item in decisions if item["tier"] == "T1")),
        "itinerary_ready": 0,
        "live_net_new": None,
        "scope": "Field-evidence replay plus dated Codex-assisted source review; not independent human verification, factual survey or live-parent reconciliation.",
    }
