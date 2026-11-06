"""PostgreSQL results mirror; SQLite remains the isolated, resumable execution queue."""

import asyncio
import json
import logging
import os
from contextlib import contextmanager

from fastapi import HTTPException
from psycopg2.extras import Json, RealDictCursor, execute_values

from app.core.config import settings
from app.crud.chat_crud import _get_conn, _put_conn
from app.research import store

logger = logging.getLogger(__name__)


def enabled():
    return os.getenv("STUDIO_RESEARCH_DATABASE", "false").lower() == "true"


@contextmanager
def transaction(*, write=False):
    if write and settings.NEON_READ_ONLY:
        raise RuntimeError("Database writes are disabled")
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = 15000")
            cur.execute("SET LOCAL lock_timeout = 1000")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def mirror_once():
    """Idempotent, transactional backfill plus incremental completion events. Never deletes."""
    if not (store.directory() / "studies.sqlite3").is_file():
        return 0
    copied = 0
    with store.connection() as local:
        ids = [row[0] for row in local.execute("SELECT id FROM studies").fetchall()]
    for study_id in ids:
        with transaction(write=True) as cur:
            # Serialize API processes without retaining a session-level pool lock.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('studio-research-mirror'))")
            cur.execute(
                "SELECT snapshot,protocol FROM studio_research_studies WHERE id=%s", (study_id,)
            )
            previous = cur.fetchone()
            after = previous["snapshot"]["cursor"] if previous else -1
            with store.connection() as local:
                local.execute("BEGIN")
                study = dict(
                    local.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
                )
                planned = json.loads(study["plan"])
                identity = json.loads(study["identity"])
                cursor = local.execute(
                    "SELECT COALESCE(MAX(revision),0) FROM events WHERE study=?", (study_id,)
                ).fetchone()[0]
                if previous and (
                    previous["protocol"] != planned
                    or previous["snapshot"]["identity"] != identity
                    or cursor < after
                ):
                    raise ValueError("Research source conflicts with its saved database version")
                progress = {
                    row["state"]: row["n"]
                    for row in local.execute(
                        "SELECT state,COUNT(*) n FROM cases WHERE study=? GROUP BY state",
                        (study_id,),
                    )
                }
                rows = local.execute(
                    "SELECT c.*,COALESCE(e.revision,0) revision FROM cases c LEFT JOIN events e "
                    "ON c.study=e.study AND c.id=e.case_id WHERE c.study=? AND "
                    "(?=-1 OR e.revision>?)",
                    (study_id, after, after),
                ).fetchall()
            snapshot = {
                "id": study_id,
                "schema_version": 1,
                "state": study["state"],
                "created_at": study["created_at"],
                "identity": identity,
                **{key: planned[key] for key in ("counts", "design", "variants", "dataset_hash")},
                "progress": progress,
                "cursor": cursor,
            }
            cur.execute(
                "INSERT INTO studio_research_studies(id,snapshot,protocol) VALUES(%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET snapshot=EXCLUDED.snapshot,synced_at=now()",
                (study_id, Json(snapshot), Json(planned)),
            )
            if rows:
                execute_values(
                    cur,
                    "INSERT INTO studio_research_runs(study_id,case_id,state,spec,result,solver_status,revision) "
                    "VALUES %s ON CONFLICT(study_id,case_id) DO UPDATE SET state=EXCLUDED.state,"
                    "result=EXCLUDED.result,solver_status=EXCLUDED.solver_status,revision=EXCLUDED.revision",
                    [
                        (
                            study_id,
                            row["id"],
                            row["state"],
                            Json(json.loads(row["spec"])),
                            Json(json.loads(row["result"])) if row["result"] else None,
                            json.loads(row["result"]).get("solver_status")
                            if row["result"]
                            else None,
                            row["revision"],
                        )
                        for row in rows
                    ],
                    page_size=500,
                )
            copied += len(rows)
    return copied


async def replicate():
    """Startup-owned task: retry failed replication while the runner continues untouched."""
    while True:
        try:
            await asyncio.to_thread(mirror_once)
        except Exception as exc:
            # Drivers can include credentials or result values in error messages.
            logger.warning("Research database sync failed (%s); retrying", type(exc).__name__)
        await asyncio.sleep(5)


def library():
    with transaction() as cur:
        cur.execute(
            "SELECT id,snapshot FROM studio_research_studies "
            "ORDER BY (snapshot->'counts'->>'solver')::int DESC,snapshot->>'created_at' DESC,id DESC"
        )
        return [{"id": str(row["id"]), "database": True} for row in cur.fetchall()]


def read(study_id, after=0, *, export=False):
    with transaction() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("SELECT * FROM studio_research_studies WHERE id=%s", (str(study_id),))
        study = cur.fetchone()
        if not study:
            raise HTTPException(404, "Study not found")
        cursor = study["snapshot"]["cursor"]
        cur.execute(
            "SELECT * FROM studio_research_runs WHERE study_id=%s AND "
            "(%s OR (state='finished' AND revision>%s AND revision<=%s)) ORDER BY case_id",
            (str(study_id), export, after, cursor),
        )
        rows = [
            {"id": row["case_id"], "state": row["state"], **row["spec"], **(row["result"] or {})}
            for row in cur.fetchall()
        ]
    snapshot = study["snapshot"] | {
        "database_synced_at": study["synced_at"].isoformat(),
        "rows": [
            {k: v for k, v in row.items() if k not in {"inputs", "preset_id"}}
            for row in rows
            if row["state"] == "finished"
        ],
    }
    return snapshot, study["protocol"], rows
