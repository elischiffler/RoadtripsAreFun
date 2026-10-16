#!/usr/bin/env python3
"""Build a portable, bounded incremental import from reviewed adapter outputs.

No database/network access occurs. Typed place adapters replay their originals
during preparation. Calendar transformation outputs retain every attributed
receipt; the private source bundle also retains their independent replay inputs.
"""

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(config, output):
    from app.catalog import calendar_enrichment as enrich

    config, output = read(config), Path(output).resolve()
    if output.exists():
        raise ValueError("output exists; choose a new immutable artifact directory")
    output.mkdir(parents=True)
    (output / "evidence").mkdir()
    copied = {}

    def evidence(path, expected=None):
        path = Path(path).resolve()
        body = path.read_bytes()
        sha = hashlib.sha256(body).hexdigest()
        if expected is not None and sha != expected:
            raise ValueError("reviewed source input checksum changed")
        target = output / "evidence" / (sha + ".bin")
        if sha not in copied:
            target.write_bytes(body)
            copied[sha] = {
                "evidence_path": target.relative_to(output).as_posix(),
                "snapshot_sha256": sha,
            }
        return copy.deepcopy(copied[sha])

    def rebase(value, root):
        if isinstance(value, list):
            return [rebase(item, root) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: rebase(item, root) for key, item in value.items()}
        if "snapshot_sha256" in value:
            keys = [
                key
                for key in ("evidence_path", "body_path", "evidence_body_file")
                if key in value
            ]
            if keys:
                item = evidence(Path(root) / value[keys[0]], value["snapshot_sha256"])
                for key in keys:
                    result.pop(key)
                result.update(item)
        return result

    prior_path = Path(config["baseline_rows"])
    if prior_path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in prior_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        rows = read(prior_path)
    if enrich.rows_digest(rows) != config["baseline_normalized_rows_sha256"]:
        raise ValueError("immutable baseline canonical rows differ")
    write(output / "baseline.json", rows)
    parent_metadata = read(config["baseline_manifest"])
    parent = {
        "generation": config["parent_generation"],
        "manifest_sha256": enrich.digest(parent_metadata),
        "row_count": len(rows),
        "normalized_rows_sha256": enrich.rows_digest(rows),
        "calendar_enrichment_sha256": config.get(
            "parent_calendar_enrichment_sha256", enrich.EMPTY_SHA256
        ),
        "snapshot_path": "baseline.json",
        "snapshot_sha256": hashlib.sha256(
            (output / "baseline.json").read_bytes()
        ).hexdigest(),
    }
    entries = []
    for source in config["calendar_inputs"]:
        payload = read(source["path"])
        entries.extend(
            rebase(
                payload["entries"] if isinstance(payload, dict) else payload,
                source["root"],
            )
        )
    for item in config.get("source_files", []):
        evidence(item["path"], item.get("sha256"))
    licenses = [
        {
            **evidence(item["path"], item.get("sha256")),
            "identifier": item["identifier"],
            "source_url": item["source_url"],
        }
        for item in config["licenses"]
    ]
    additions = []
    for number, source in enumerate(config.get("addition_inputs", [])):
        target = output / "inputs" / f"source-{number:02d}"
        target.mkdir(parents=True)
        source_path = Path(source["path"]).resolve()
        for relative in source["files"]:
            if not enrich.portable_relative(relative):
                raise ValueError("source adapter input path is not portable")
            origin = (source_path.parent / relative).resolve()
            if not origin.is_relative_to(source_path.parent):
                raise ValueError("source adapter input escapes its source bundle")
            destination = (target / relative).resolve()
            if not destination.is_relative_to(target):
                raise ValueError("source adapter output escapes the artifact")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
        destination = target / source_path.name
        if not destination.exists():
            shutil.copyfile(source_path, destination)
        additions.append(
            {
                "adapter": source["adapter"],
                "path": destination.relative_to(output).as_posix(),
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "manifest": source["manifest"],
            }
        )
    payload = {
        "schema_version": enrich.SCHEMA,
        "release": config["release"],
        "attribution": config["attribution"],
        "parent": parent,
        "entries": sorted(entries, key=lambda entry: entry["source_id"]),
        "source_inputs": list(copied.values()),
        "source_scanned_rows": config["source_scanned_rows"],
        "licenses": licenses,
        "addition_inputs": additions,
        "additional_source_catalogs": config.get("additional_source_catalogs", {}),
    }
    path = output / "catalog.enrichment.json"
    write(path, payload)
    prepared = enrich.prepare(path)
    write(output / "catalog.preview.json", prepared["rows"])
    write(output / "calendar.preview.json", prepared["entries"])
    write(output / "catalog.manifest.json", prepared["manifest"])
    report = {
        **prepared["report"],
        "generation": prepared["generation"],
        "parent_generation": parent["generation"],
        "preserved_rows": len(rows),
        "normalized_rows_sha256": enrich.rows_digest(prepared["rows"]),
        "network_or_database_calls": False,
    }
    write(output / "completion.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(build(**vars(parser.parse_args())), indent=2))
