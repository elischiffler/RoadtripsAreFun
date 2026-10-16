#!/usr/bin/env python3
"""Validate a portable incremental catalog; writes require explicit CLI actions."""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main():
    enrich = importlib.import_module("app.catalog.calendar_enrichment")
    connect_target = importlib.import_module("scripts.catalog_import").connect_target
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact", type=Path, help="source artifact, or frozen receipt for --rollback"
    )
    parser.add_argument("--target", choices=["local", "neon"], default="local")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stage", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    mode.add_argument(
        "--freeze-rollback",
        action="store_true",
        help="print a verified recovery receipt without changing the pointer",
    )
    parser.add_argument(
        "--receipt-sha256", help="required checksum of the reviewed rollback receipt"
    )
    args = parser.parse_args()
    if args.rollback:
        body = args.artifact.read_bytes()
        if hashlib.sha256(body).hexdigest() != args.receipt_sha256:
            raise ValueError("rollback requires the reviewed receipt SHA-256")
        connection = connect_target(args.target)
        try:
            result = enrich.rollback(connection, json.loads(body))
        finally:
            connection.close()
        print(json.dumps({**result, "database_write": True}, indent=2))
        return
    prepared = enrich.prepare(args.artifact)
    result = {
        **prepared["report"],
        "generation": prepared["generation"],
        "database_write": False,
    }
    if args.stage or args.activate or args.freeze_rollback:
        connection = connect_target(args.target)
        try:
            if args.freeze_rollback:
                result = enrich.recovery_receipt(connection, prepared)
            else:
                result = (
                    enrich.stage(connection, prepared)
                    if args.stage
                    else enrich.activate(connection, prepared)
                )
        finally:
            connection.close()
        if not args.freeze_rollback:
            result["database_write"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- redact every connection/SQL error as the existing CLI does
        raise SystemExit(
            f"Incremental catalog operation failed ({type(exc).__name__}); no secrets logged"
        ) from None
