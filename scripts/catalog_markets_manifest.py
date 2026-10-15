#!/usr/bin/env python3
"""Rebuild the reviewed market child from local, frozen originals; no network/DB.

PDF extraction is deliberately a source producer dependency. Ordinary importer
preparation uses the immutable extracted table receipts, whose hashes and PDF
bindings are locked in the acquisition inventory. Existing outputs are refused.
"""

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import kaggle_markets as markets  # noqa: E402


def verify_pdf_tables(root, index):
    try:
        from importlib.metadata import version

        import pdfplumber
    except ImportError as exc:
        raise ValueError("install scripts/requirements-markets.txt for source replay") from exc
    if pdfplumber.__version__ != "0.11.8" or version("pdfminer.six") != "20251107":
        raise ValueError("market PDF replay requires the pinned source extractor versions")
    for key, table_key, width, header in (
        ("cdfa", "cdfa_rows", 8, "County"),
        ("ct", "ct_rows", 10, "FM Name"),
    ):
        expected = json.loads(markets.retained(root, index[table_key]))["rows"]
        actual = []
        with pdfplumber.open(root / index[key]["path"]) as pdf:
            for page_no, page in enumerate(pdf.pages, 1):
                for table_index, table in enumerate(page.extract_tables()):
                    for row_index, cells in enumerate(table):
                        if cells[0] and header in cells[0]:
                            continue
                        if len(cells) != width:
                            raise ValueError("PDF replay found an unexpected table width")
                        actual.append((page_no, table_index, row_index, cells))
        frozen = [
            (row["pdf_page"], row["table_index"], row["row_index"], row["raw_cells"])
            for row in expected
        ]
        if actual != frozen:
            raise ValueError("PDF replay differs from the immutable extracted table")


def admission_ledger(root, index):
    native, current, rosters, data, _ = markets.load_sources(root, index)
    targets = markets.targeted_records(data)
    census, _ = markets.load_census(root, index)
    lookup = defaultdict(list)
    for roster in rosters:
        lookup[(roster["region"], markets.core(roster["name"]))].append(roster)
    checks = {entry["listing_id"]: entry for entry in index["driving"]}
    ledger, reasons = [], Counter()
    for ident, source in native.items():
        officials = (
            [targets[ident]]
            if ident in targets
            else lookup[(source["state"], markets.core(source["name"]))]
        )
        row, reason = markets.qualification(source, current.get(ident), officials)
        if row:
            if ident not in checks:
                reason = "driving_evidence_not_acquired"
            else:
                try:
                    markets.driving(root, checks[ident], row)
                    _, reason = markets.census_qualification(source, row["official_rows"], census)
                except ValueError:
                    reason = "driving_destination_rejected"
        decision = "selected" if ident in index["selection"] else "hold"
        if decision == "selected" and reason:
            raise ValueError("frozen market selection disagrees with source admission ledger")
        if decision == "hold":
            reasons[reason or "outside_frozen_selection"] += 1
        ledger.append(
            {
                "listing_id": ident,
                "name": source["name"],
                "region": source["state"],
                "decision": decision,
                "reason": reason,
            }
        )
    return {
        "scanned": len(native),
        "selected": len(index["selection"]),
        "hold_reasons": dict(reasons),
        "ledger": ledger,
        "category_policy": "Daytime food destinations; omitted restaurant/evening food query group because source market calendars remain raw facts, not scheduler opening intervals.",
    }


def build(sources, output):
    sources, output = Path(sources).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("market output directory already exists")
    index_path = sources / "markets-acquisition-index.json"
    raw = index_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != markets.INDEX_SHA256:
        raise ValueError("market source inventory differs from frozen review")
    index = json.loads(raw)
    # Verify every original before creating a new candidate artifact.
    receipts = [
        index[key]
        for key in (
            "archive",
            "canonical",
            "kaggle_metadata",
            "cdfa",
            "cdfa_rows",
            "ct",
            "ct_rows",
            "de",
            "vt",
        )
    ]
    receipts += index["rights"] + index["driving"] + list(index["census"].values())
    for receipt in receipts:
        markets.retained(sources, receipt)
    verify_pdf_tables(sources, index)
    ledger = admission_ledger(sources, index)
    output.mkdir(parents=True)
    for receipt in receipts:
        target = output / receipt["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources / receipt["path"], target)
    shutil.copy2(index_path, output / index_path.name)
    now = max(receipt["retrieved_at"] for receipt in receipts)
    bundle = {
        "index": {
            "path": index_path.name,
            "url": markets.SOURCE_URL,
            "sha256": markets.INDEX_SHA256,
            "retrieved_at": now,
            "status": 200,
            "bytes": len(raw),
        },
        "selection": index["selection"],
    }
    bundle_raw = (json.dumps(bundle, indent=2) + "\n").encode()
    bundle_path = output / "reviewed-markets.json"
    bundle_path.write_bytes(bundle_raw)
    manifest = {
        "schema_version": markets.SCHEMA,
        "source_url": markets.SOURCE_URL,
        "release": markets.RELEASE,
        "retrieved_at": index["archive"]["retrieved_at"],
        "sha256": hashlib.sha256(bundle_raw).hexdigest(),
        "attribution": markets.ATTRIBUTION,
        "filters": {
            "country": "US",
            "reviewed_current_rosters": ["CA", "CT", "DE", "VT"],
            "preserve_native_coordinates": True,
        },
        "licenses": {
            identifier: {
                "path": str(ROOT / "frontend/public/licenses" / (identifier + ".txt")),
                "sha256": hashlib.sha256(
                    (ROOT / "frontend/public/licenses" / (identifier + ".txt")).read_bytes()
                ).hexdigest(),
            }
            for identifier in ("CC-BY-4.0", "LicenseRef-US-Census-Geocoder")
        },
    }
    rows, report = markets.prepare(
        bundle_path, manifest, max_rows=50_000, max_bytes=100 * 1024 * 1024
    )
    (output / "reviewed-markets.json.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "reviewed-markets.preview.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    (output / "market-admission-ledger.json").write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    # Completion is last; an interrupted directory is never a release artifact.
    (output / "completion.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.sources, args.output), sort_keys=True))
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(f"Market manifest failed: {type(exc).__name__}: {exc}") from None
