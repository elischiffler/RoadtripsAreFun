"""Local operator tools for explicit research replacement, execution and exports."""

import argparse
import json
import os
import shutil
import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import app.routing  # noqa: F401 -- initialize shared models before the database layer
from app.research import database, store
from app.research.design import Design, plan
from app.routers import studio_research as api
from app.routing.evaluation.runner import identity


def private_json(path, value):
    with path.open("x") as handle:
        os.chmod(path, 0o600)
        json.dump(value, handle, default=str)


def remove_studies(ids, backup):
    """Remove only explicitly named inactive studies, after a verified recovery copy."""
    ids = [str(UUID(value)) for value in ids]
    backup = Path(backup).resolve()
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    with database.transaction(write=True) as cur:
        # Same lock as replication: old SQLite rows cannot be copied back during removal.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('studio-research-mirror'))")
        with store.connection() as local:
            local.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in ids)
            studies = local.execute(
                f"SELECT id,state FROM studies WHERE id IN ({placeholders})", ids
            ).fetchall()
            if any(row["state"] in {"starting", "running", "pausing"} for row in studies):
                raise ValueError("Let active research finish pausing before removal")
            source = sqlite3.connect(
                (store.directory() / "studies.sqlite3").as_uri() + "?mode=ro", uri=True
            )
            destination = sqlite3.connect(backup / "studies.sqlite3")
            try:
                source.backup(destination)
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Research recovery copy failed verification")
            finally:
                source.close()
                destination.close()
            os.chmod(backup / "studies.sqlite3", 0o600)
            for table, column in (
                ("studio_research_studies", "id"),
                ("studio_research_runs", "study_id"),
                ("algorithm_lab_runs", "batch_id"),
            ):
                cur.execute(f"SELECT * FROM {table} WHERE {column}=ANY(%s::uuid[])", (ids,))
                private_json(backup / f"{table}.json", [dict(row) for row in cur.fetchall()])
            for study_id in ids:
                directory = store.directory() / study_id
                if directory.is_dir():
                    shutil.copytree(directory, backup / study_id)
            for table, column in (("events", "study"), ("cases", "study"), ("studies", "id")):
                local.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", ids)
            for table, column in (
                ("studio_research_runs", "study_id"),
                ("studio_research_studies", "id"),
                ("algorithm_lab_runs", "batch_id"),
            ):
                cur.execute(f"DELETE FROM {table} WHERE {column}=ANY(%s::uuid[])", (ids,))
        # If the transaction fails, the backup and named IDs permit reconciliation.
    for study_id in ids:
        directory = store.directory() / study_id
        if directory.is_dir():
            shutil.rmtree(directory)
    return {"removed_studies": ids, "recovery_directory": str(backup)}


def create_study(output, *, start=True):
    api.require_execution()
    if not database.enabled() or os.getenv("PLACE_TRAITS_CACHE_ENABLED") != "true":
        raise ValueError("Research database and persistent place traits must both be enabled")
    with database.transaction(write=True) as cur:
        for table in ("studio_research_studies", "studio_research_runs", "place_attribute_traits"):
            cur.execute(f"SELECT 1 FROM {table} LIMIT 1")
    study_id = str(uuid4())
    planned = plan(Design())
    key = store.create(study_id, f"studio:research-{study_id}", planned, identity())
    private_json(Path(output), {"id": study_id, "key": key})
    database.mirror_once()
    if start:
        api.start(store.study(study_id, key))
    return {"id": study_id, "counts": planned["counts"], "state": "starting" if start else "ready"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("remove")
    reset.add_argument("--study-id", action="append", required=True)
    reset.add_argument("--backup", required=True)
    create = commands.add_parser("create")
    create.add_argument("--control-file", required=True)
    create.add_argument("--no-start", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("study_id")
    args = parser.parse_args()
    if args.command == "remove":
        result = remove_studies(args.study_id, args.backup)
    elif args.command == "create":
        result = create_study(args.control_file, start=not args.no_start)
    else:
        study = store.study(str(UUID(args.study_id)), trusted=True)
        rows, progress, _ = store.changes(study["id"])
        result = {
            "id": study["id"],
            "state": study["state"],
            "progress": progress,
            "completed": sum(bool(row.get("completed")) for row in rows),
            "captures": sum(bool(row.get("capture")) for row in rows),
        }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
