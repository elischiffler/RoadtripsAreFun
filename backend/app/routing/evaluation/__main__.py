"""python -m app.routing.evaluation: validate, run, report; no capture/live command."""

import argparse
import json
from pathlib import Path

from app.routing.evaluation.fixtures import Fixture
from app.routing.evaluation.report import render
from app.routing.evaluation.runner import PARAMETERS, atomic, campaign, execute, json_text
from app.routing.evaluation.scenarios import Scenario, core_scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scenarios = sub.add_parser("scenarios")
    scenarios.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--fixtures", required=True)
    validate.add_argument("--unit-only", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--fixtures", default="tests/fixtures/route_evaluation/v1")
    run.add_argument("--scenarios", default=None)
    run.add_argument("--scenario", action="append", help="exact ID, repeat to select several")
    run.add_argument("--suite", choices=["core-v1", "weekend-v1"], default="core-v1")
    run.add_argument(
        "--track",
        choices=["selection-100", "production-shortlist", "offline-pipeline"],
        required=True,
    )
    run.add_argument("--output", required=True)
    run.add_argument("--unit-only", action="store_true")
    run.add_argument("--sweep", choices=sorted(PARAMETERS))
    run.add_argument(
        "--methods",
        nargs="+",
        choices=["cp_sat", "utility_first", "spacing_first"],
        default=["cp_sat"],
    )
    run.add_argument("--deadline", type=float, default=120)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--time-limit", type=float, default=5)
    run.add_argument("--repeat", type=int, default=1)
    report = sub.add_parser("report")
    report.add_argument("--input", required=True)
    worker = sub.add_parser("_worker")
    worker.add_argument("request")
    worker.add_argument("response")
    args = parser.parse_args()
    if args.command == "scenarios":
        rows = core_scenarios()
        for row in rows:
            Scenario.model_validate(row)
        atomic(args.output, json_text({"schema_version": 1, "scenarios": rows}))
        print(f"Saved {len(rows)} validated scenarios")
    elif args.command == "validate":
        found = sorted(Path(args.fixtures).glob("*/manifest.json"))
        if not found:
            parser.error("no captured fixture manifests; real evidence remains blocked")
        for path in found:
            fixture = Fixture(path.parent, allow_synthetic=args.unit_only)
            print(
                f"{path.parent.name}: {fixture.manifest.attraction_count} / {fixture.manifest.evidence_type} / {fixture.hash}"
            )
    elif args.command == "report":
        print(json_text(render(args.input)))
    elif args.command == "_worker":
        spec = json.loads(Path(args.request).read_text())
        atomic(args.response, json_text(execute(spec)))
    else:
        if not 1 <= args.repeat <= 10:
            parser.error("repeat must be 1..10")
        if not 1 <= args.deadline <= 600:
            parser.error("deadline must be 1..600 seconds")
        if args.sweep == "budget" and args.track != "offline-pipeline":
            parser.error("nightly target sweeps belong to the full pipeline")
        if args.track == "offline-pipeline" and args.sweep and args.sweep != "budget":
            parser.error("selection parameter sweeps require a frozen selection pool")
        rows = (
            json.loads(Path(args.scenarios).read_text())["scenarios"]
            if args.scenarios
            else core_scenarios()
        )
        if args.suite == "weekend-v1":
            rows = [
                row for row in rows if row["trip_type"] == "medium-2d" and row["stops_per_day"] == 2
            ]
        if args.scenario:
            unknown = set(args.scenario) - {row["id"] for row in rows}
            if unknown:
                parser.error(f"unknown scenario IDs: {sorted(unknown)}")
            rows = [row for row in rows if row["id"] in args.scenario]
        if args.sweep == "budget":
            rows = [row for row in rows if row["trip_type"] == "medium-2d"]
        if not rows or len({row["id"] for row in rows}) != len(rows):
            parser.error("scenario suite is empty or contains duplicate IDs")
        print(json_text(render(campaign(args, rows))))


if __name__ == "__main__":
    main()
