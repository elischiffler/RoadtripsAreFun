"""Build inert, source-attributed parking holds; no network or database writes."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog.parking_holds import build  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-export", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prepared = build(args.parent_export, args.decisions, args.evidence_root, args.output)
    print(json.dumps({"generation": prepared["generation"], **prepared["report"]}, indent=2))


if __name__ == "__main__":
    main()
