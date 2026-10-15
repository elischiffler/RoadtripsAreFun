"""Serial campaigns with isolated, bounded workers and atomic local artifacts."""

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, replace
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from time import perf_counter, process_time

try:
    import resource
except ImportError:  # Windows: preserve measured CPU and explicit unavailable RSS.
    resource = None

from pydantic import ValidationError

from app.agent.progress import reporting
from app.models.trip_limits import MAPBOX_MAX_COORDINATES, MAX_STOPS
from app.routing.cp_sat_selection import SelectionConfig, select_attractions
from app.routing.evaluation import HARNESS_VERSION
from app.routing.evaluation.fixtures import EvidenceError, Fixture
from app.routing.evaluation.methods import comparator
from app.routing.evaluation.network import no_network
from app.routing.evaluation.offline import pipeline
from app.routing.evaluation.scenarios import PERSONAS, Scenario
from app.routing.evaluation.workload import screen_workload
from app.routing.explanation import capture_explanation, record_explanation
from app.routing.profiles import crossmatch
from app.routing.run_metrics import METRIC_VERSION, compile_metrics, fingerprint, measuring, timed

PARAMETERS = {
    "quality_loss": (0, 0.05, 0.10, 0.20),
    "utility_threshold": (0.50, 0.60, 0.70),
    "detour_weight": (0, 0.25, 1, 4),
    "time_limit_seconds": (0.25, 1, 5, 15),
    "persona_interpolation": (0, 0.25, 0.50, 0.75, 1),
    "budget": (60, 120, 180, 240),
}


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8, strict JSON, fsync and replace: no partial result presented as terminal.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    Path(handle.name).replace(path)


def json_text(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def physical_memory():
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        try:
            return int(
                subprocess.check_output(
                    ["sysctl", "-n", "hw.memsize"], stderr=subprocess.PIPE, text=True
                )
            )
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            return None


def process_resources():
    if resource is None:
        return {
            "cpu_seconds": process_time(),
            "peak_rss_bytes": None,
            "rss_reason": "platform_not_supported",
        }
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "peak_rss_bytes": int(usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)),
    }


def identity():
    source = Path(__file__).resolve().parents[2]
    root = next((parent for parent in source.parents if (parent / ".git").exists()), None)
    source_hash = fingerprint(
        {
            str(path.relative_to(source)): fingerprint(path.read_bytes().hex())
            for path in sorted(source.rglob("*.py"))
        }
    )
    revision = os.getenv("ROADTRIPS_REVISION", "unversioned-source")
    dirty, patch_hash, git_available = None, None, False
    if root is not None and shutil.which("git"):

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE
            ).strip()

        try:
            patch = git("diff", "HEAD")
            status = git("status", "--porcelain")
            untracked = {}
            # Only non-ignored repository files: no dotenv or credentials are read.
            for name in git("ls-files", "--others", "--exclude-standard").splitlines():
                path = root / name
                if path.is_file():
                    untracked[name] = fingerprint(path.read_bytes().hex())
            revision = git("rev-parse", "HEAD")
            dirty = bool(status)
            patch_hash = fingerprint({"diff": patch, "untracked": untracked}) if status else None
            git_available = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    return {
        "revision": revision,
        "dirty": dirty,
        "patch_hash": patch_hash,
        "source_snapshot_hash": source_hash,
        "git_metadata_available": git_available,
        "python": platform.python_version(),
        "ortools": version("ortools"),
        "tzdata": version("tzdata"),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "physical_memory_bytes": physical_memory(),
        "harness_version": HARNESS_VERSION,
        "metric_version": METRIC_VERSION,
        "max_attractions": MAX_STOPS,
        "mapbox_max_coordinates": MAPBOX_MAX_COORDINATES,
    }


def base_row(spec):
    raw = spec["scenario"]
    return {
        "run_id": spec["run_id"],
        "repeat_index": spec.get("repeat_index", 1),
        "scenario_id": raw["id"],
        "trip_type": raw["trip_type"],
        "persona": raw["persona"],
        "stops_per_day": raw["stops_per_day"],
        "target_days": raw["target_days"],
        "track": spec["track"],
        "method": spec["method"],
        "configuration": spec["config"],
        "parameter": spec.get("parameter"),
        "parameter_value": spec.get("parameter_value"),
        "identity": spec["identity"],
        "scenario": raw,
        "status": "running",
        "error": None,
        "evidence_type": None,
        "metrics": None,
        "solver_status": "NOT_RUN" if spec["method"] == "cp_sat" else "NOT_APPLICABLE",
        "persistence": "local_files_only",
        "stage": "input_validation",
        "external_calls": 0,
    }


def execute(spec):
    row = base_row(spec)
    started = perf_counter()
    initial_resources = process_resources()
    envelope = {
        "mode": "offline_pipeline" if spec["track"] == "offline-pipeline" else "replay",
        "input_snapshot": {},
        "route": None,
        "itinerary": None,
        "error": None,
        "stages": [],
        "revision": spec["identity"]["revision"],
        "method": spec["method"],
    }

    def progress_event(event):
        if event["state"] == "failed":
            envelope["stages"].append({"name": event["stage"], "status": "failed"})

    with (
        no_network(),
        reporting(progress_event),
        measuring() as telemetry,
        capture_explanation() as explanation,
    ):
        envelope["explanation"] = explanation
        try:
            scenario = Scenario.model_validate(spec["scenario"])
            row["stage"] = "fixture_validation"
            config = SelectionConfig(**spec["config"])
            fixture = Fixture(
                Path(spec["fixtures"]) / scenario.fixture, allow_synthetic=spec["unit_only"]
            )
            fixture.require_access_until(
                scenario.departure().date() + timedelta(days=scenario.target_days - 1)
            )
            manifest = fixture.manifest
            envelope["evidence_type"] = manifest.evidence_type
            row.update(
                evidence_type=manifest.evidence_type,
                fixture_hash=fixture.hash,
                catalog_generation=manifest.catalog_generation,
                catalog_release=manifest.catalog_release,
                node_order_hash=fingerprint(fixture.data["nodes"]),
                matrix_hashes={
                    k: fingerprint(fixture.data.get(k))
                    for k in ("travel_time_seconds", "travel_distance_meters")
                },
                capture=manifest.model_dump(),
                source_count=len(fixture.data["attractions"]),
            )
            if manifest.endpoints != [scenario.inputs.start_id, scenario.inputs.destination_id]:
                raise EvidenceError("scenario endpoints disagree with captured fixture")
            if (
                manifest.departure != scenario.departure().isoformat()
                or manifest.evaluation_clock != scenario.evaluation_clock.isoformat()
            ):
                raise EvidenceError("scenario date/clock disagrees with frozen capture")
            envelope["input_snapshot"] = scenario.inputs.model_dump(mode="json") | {
                "start_date": scenario.departure().isoformat(),
                "effective_weights": scenario.inputs.persona_weights,
            }
            row["workload_screening"] = screen_workload(fixture, scenario)
            envelope["scenario_target"] = {
                "days": scenario.target_days,
                "stops_per_day": scenario.stops_per_day,
            }
            envelope["direct_route"] = {
                "duration": fixture.baseline.duration,
                "distance": fixture.baseline.distance,
            }
            if spec["track"] == "offline-pipeline":

                def progress(name):
                    row["stage"] = name

                row["offline_provider_reads"] = asyncio.run(
                    pipeline(fixture, scenario, config, spec["method"], envelope, progress)
                )
            else:
                row["stage"] = "selection_evidence"
                candidates = []
                for item in fixture.data["attractions"]:
                    match = crossmatch(scenario.inputs.persona_weights, item["attribute_ratings"])
                    candidates.append({**item, **match.model_dump()})
                if spec["track"] == "selection-100" and len(candidates) != 100:
                    raise EvidenceError(
                        "insufficient_real_fixture_coverage: selection-100 requires exactly 100 unique records"
                    )
                if spec["track"] == "production-shortlist":
                    ids = fixture.data.get("production_shortlists", {}).get(scenario.id)
                    if ids is None:
                        raise EvidenceError("frozen scenario production shortlist missing")
                    by_id = {item["provider_id"]: item for item in candidates}
                    candidates = [by_id[key] for key in ids]
                row["stage"] = "selection"
                record_explanation(weights=scenario.inputs.persona_weights)
                with timed("route.solver"):
                    if spec["method"] == "cp_sat":
                        select_attractions(
                            candidates,
                            [],
                            scenario.inputs.num_stops,
                            fixture.baseline.duration,
                            config=config,
                        )
                    else:
                        comparator(
                            spec["method"],
                            candidates,
                            [],
                            scenario.inputs.num_stops,
                            fixture.baseline.duration,
                            config,
                        )
            row["status"] = "completed"
            row["stage"] = "complete"
        except ValidationError as exc:
            row.update(
                status="unsupported" if row["stage"] == "input_validation" else "blocked",
                error=str(exc),
            )
        except (FileNotFoundError, EvidenceError) as exc:
            row.update(status="blocked", error=str(exc))
        except Exception as exc:
            row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if envelope["stages"]:
            row["stage"] = envelope["stages"][0]["name"]
        if row["error"]:
            envelope["error"] = {"code": row["stage"], "message": row["error"]}
            envelope["stages"].append({"name": row["stage"], "status": "failed"})
        envelope["stages"] = [*explanation.get("stages", []), *envelope["stages"]]
        # Metrics use an honest offline mode; never save these as live Lab history.
        row["offline_provider_reads"] = envelope.get(
            "offline_provider_reads", row.get("offline_provider_reads", {})
        )
        row["metrics"] = compile_metrics(envelope, telemetry, (perf_counter() - started) * 1000)
        row["solver_status"] = (explanation.get("solver") or {}).get(
            "status", "NOT_RUN" if spec["method"] == "cp_sat" else "NOT_APPLICABLE"
        )
        row["solver"] = explanation.get("solver")
        row["selected_ids"] = [
            item["provider_id"] for item in explanation["candidates"] if item.get("selected")
        ]
        row["delivered_ids"] = [
            stop["provider_id"]
            for stop in (envelope["route"] or {}).get("stops", [])
            if stop.get("type") == "stop"
        ]
        row["explanation"] = explanation
        row["route"] = envelope["route"]
        row["itinerary"] = envelope["itinerary"]
        config_model = {
            key: value
            for key, value in spec["config"].items()
            if key not in {"seed", "workers", "time_limit_seconds"}
        }
        row["model_key"] = fingerprint(
            {
                "candidates": row["metrics"]["candidate_hash"],
                "config": config_model,
                "requested": spec["scenario"]["inputs"]["num_stops"],
                "baseline": envelope.get("direct_route"),
                "fixture": row.get("fixture_hash"),
                "revision": spec["identity"],
                "method": spec["method"],
                "weights": envelope["input_snapshot"].get("effective_weights"),
                "metric": METRIC_VERSION,
            }
        )
        trip = row["metrics"]["trip_evaluation"]
        selected_count = len(row["selected_ids"])
        required = spec["scenario"]["inputs"]["num_stops"]
        pipeline_track = spec["track"] == "offline-pipeline"
        fulfilled = (
            trip["stop_fulfillment"]["delivered"] == required
            if pipeline_track and envelope["route"]
            else selected_count == required
            if row["status"] == "completed"
            else None
        )
        controls = dict(spec["config"])
        controls.pop(spec.get("parameter"), None)
        trip_controls = dict(spec["scenario"]["inputs"])
        if spec.get("parameter") == "budget":
            trip_controls.pop("budget", None)
        if spec.get("parameter") == "persona_interpolation":
            trip_controls.pop("persona_weights", None)
        row["paired_key"] = fingerprint(
            {
                "scenario": spec["scenario"]["id"],
                "trip_controls": trip_controls,
                "configuration_controls": controls,
                "fixture": row.get("fixture_hash"),
                "track": spec["track"],
                "method": spec["method"],
                "repeat": spec.get("repeat_index", 1),
                "parameter": spec.get("parameter"),
                "identity": spec["identity"],
            }
        )
        row["assessments"] = {
            "input_support": "unsupported" if row["status"] == "unsupported" else "pass",
            "request_fulfillment": "pass"
            if fulfilled
            else "fail"
            if fulfilled is not None
            else "unassessed",
            "schedule": "pass"
            if trip["schedule_compliance"]["violation_count"] == 0
            else "fail"
            if trip["schedule_compliance"]["violation_count"] is not None
            else "unassessed",
            "scenario_target": "pass"
            if trip["scenario_target"]["days_met"] and trip["scenario_target"]["density_met"]
            else "fail"
            if trip["scenario_target"]["days_met"] is not None
            else "unassessed",
            "nightly_room_target": "pass"
            if trip["hotel_costs"]["over_target_room_nights"] == 0
            else "fail"
            if trip["hotel_costs"]["over_target_room_nights"] is not None
            else "unassessed",
            "pipeline_completion": "pass"
            if trip["completed"]
            else "fail"
            if pipeline_track and row["status"] == "failed"
            else "unassessed",
        }
    row["resources"] = process_resources()
    row["resources"]["cpu_seconds"] -= initial_resources["cpu_seconds"]
    return row


def configurations(base, parameter, raw):
    if not parameter:
        yield base, raw, None
        return
    for value in PARAMETERS[parameter]:
        scenario = json.loads(json.dumps(raw))
        config = base
        if parameter == "persona_interpolation":
            scenario["inputs"]["persona_weights"] = {
                key: (1 - value) * PERSONAS["nature"][key] + value * PERSONAS["entertainment"][key]
                for key in PERSONAS["nature"]
            }
        elif parameter == "budget":
            scenario["inputs"]["budget"] = value
        else:
            config = replace(base, **{parameter: value})
        yield config, scenario, value


def run_worker(spec, deadline):
    parent_start = perf_counter()
    with tempfile.TemporaryDirectory(prefix="route-evaluation-") as temp:
        request, response = Path(temp) / "request.json", Path(temp) / "result.json"
        request.write_text(json_text(spec))
        try:
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.routing.evaluation",
                    "_worker",
                    str(request),
                    str(response),
                ],
                capture_output=True,
                text=True,
                timeout=deadline,
            )
            if run.returncode or not response.exists():
                row = base_row(spec) | {
                    "status": "failed",
                    "stage": "worker_start",
                    "error": run.stderr[-3000:] or "worker produced no terminal row",
                }
            else:
                row = json.loads(response.read_text())
        except subprocess.TimeoutExpired:
            row = base_row(spec) | {
                "status": "failed",
                "stage": "harness_deadline",
                "error": "isolated worker terminated at whole-run deadline",
                "stop_reason": "harness_deadline",
                "solver_status": "NOT_RUN" if spec["method"] == "cp_sat" else "NOT_APPLICABLE",
                "solver_status_reason": "unobserved_at_termination",
            }
    row["worker_elapsed_ms"] = (perf_counter() - parent_start) * 1000
    return row


def campaign(args, scenarios):
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Use a new empty campaign directory; immutable results are never overwritten"
        )
    output.mkdir(parents=True, exist_ok=True)
    machine = identity()
    # Explicitly record every expected scenario/method/parameter cell before any work.
    specs = []
    base = SelectionConfig(
        candidate_limit=100 if args.track == "selection-100" else 60,
        seed=getattr(args, "seed", 0),
        workers=getattr(args, "workers", 1),
        time_limit_seconds=getattr(args, "time_limit", 5),
    )
    for raw in scenarios:
        for config, row, parameter_value in configurations(base, args.sweep, raw):
            for method in args.methods:
                for repeat in range(getattr(args, "repeat", 1)):
                    specs.append(
                        {
                            "run_id": str(uuid.uuid4()),
                            "repeat_index": repeat + 1,
                            "scenario": row,
                            "track": args.track,
                            "method": method,
                            "config": asdict(config),
                            "identity": machine,
                            "fixtures": str(Path(args.fixtures).resolve()),
                            "unit_only": args.unit_only,
                            "parameter": args.sweep,
                            "parameter_value": parameter_value,
                        }
                    )
    atomic(
        output / "manifest.json",
        json_text(
            {
                "identity": machine,
                "track": args.track,
                "expected_runs": len(specs),
                "deadline_seconds_per_run": args.deadline,
                "unit_only": args.unit_only,
                "specifications": specs,
                "warmup_trials": getattr(args, "warmup", 0),
                "timing": "serial isolated workers; warm-up trials use separate processes and are excluded; setup overhead recorded separately",
            }
        ),
    )
    warmups = []
    for index in range(getattr(args, "warmup", 0)):
        trial = {**specs[0], "run_id": str(uuid.uuid4()), "warmup_index": index + 1}
        warmups.append(run_worker(trial, args.deadline))
    atomic(
        output / "warmups.jsonl",
        "".join(json.dumps(row, allow_nan=False) + "\n" for row in warmups),
    )
    results = []
    for spec in specs:
        row = run_worker(spec, args.deadline)
        for kind in ("route", "itinerary"):
            artifact = row.pop(kind, None)
            if artifact is not None:
                name = f"{kind}s/{row['run_id']}.json"
                atomic(output / name, json_text(artifact))
                row[f"{kind}_artifact"] = name
        results.append(row)
        atomic(
            output / "runs.jsonl",
            "".join(json.dumps(row, allow_nan=False) + "\n" for row in results),
        )
        atomic(
            output / "failures.jsonl",
            "".join(
                json.dumps(row, allow_nan=False) + "\n"
                for row in results
                if row["status"] != "completed"
            ),
        )
        print(
            f"{row['scenario_id']} / {row['method']}: {row['status']} ({row['solver_status']})",
            flush=True,
        )
    return output
