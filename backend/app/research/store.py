"""Private local SQLite persistence shared by API and detached research worker."""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException


def directory():
    return Path(
        os.getenv("STUDIO_RESEARCH_DIR")
        or Path(__file__).resolve().parents[3] / ".artifacts" / "studio-research"
    ).resolve()


def now():
    return datetime.now(UTC).isoformat()


def dumps(value):
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


@contextmanager
def connection():
    root = directory()
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        conn = sqlite3.connect(root / "studies.sqlite3", timeout=15)
    except (OSError, sqlite3.Error):
        raise HTTPException(
            503, "Research storage is unavailable. Configure a writable STUDIO_RESEARCH_DIR."
        ) from None
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS studies (id TEXT PRIMARY KEY, owner TEXT NOT NULL, "
            "access_key TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL, "
            "plan TEXT NOT NULL, identity TEXT NOT NULL, pid INTEGER);"
            "CREATE TABLE IF NOT EXISTS cases (study TEXT NOT NULL, id INTEGER NOT NULL, "
            "track TEXT NOT NULL, state TEXT NOT NULL, spec TEXT NOT NULL, result TEXT, "
            "PRIMARY KEY(study,id));"
            "CREATE TABLE IF NOT EXISTS events (revision INTEGER PRIMARY KEY AUTOINCREMENT, "
            "study TEXT NOT NULL, case_id INTEGER NOT NULL, UNIQUE(study,case_id));"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def create(study_id, owner, planned, identity):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
        if existing:
            if existing["owner"] != owner:
                raise HTTPException(404, "Study not found")
            if json.loads(existing["plan"])["design"] != planned["design"]:
                raise HTTPException(409, "This study already has different settings")
            return existing["access_key"]
        key = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO studies VALUES (?,?,?,?,?,?,?,?)",
            (
                study_id,
                owner,
                key,
                now(),
                "ready",
                dumps({k: v for k, v in planned.items() if k != "cases"}),
                dumps(identity),
                None,
            ),
        )
        conn.executemany(
            "INSERT INTO cases VALUES (?,?,?,?,?,NULL)",
            [
                (study_id, i, case["track"], "pending", dumps(case))
                for i, case in enumerate(planned["cases"])
            ],
        )
        return key


def study(study_id, key=None, *, trusted=False):
    with connection() as conn:
        row = conn.execute("SELECT * FROM studies WHERE id=?", (study_id,)).fetchone()
    if row is None or (
        not trusted
        and not hmac.compare_digest(
            hashlib.sha256((key or "").encode()).digest(),
            hashlib.sha256(row["access_key"].encode()).digest(),
        )
    ):
        raise HTTPException(404, "Study not found")
    if os.name == "posix" and row["pid"] and row["state"] in {"starting", "running", "pausing"}:
        try:
            os.kill(row["pid"], 0)
        except ProcessLookupError:
            state(study_id, "interrupted")
            return study(study_id, key, trusted=trusted)
    return dict(row) | {"plan": json.loads(row["plan"]), "identity": json.loads(row["identity"])}


def rows(study_id):
    with connection() as conn:
        data = conn.execute("SELECT * FROM cases WHERE study=? ORDER BY id", (study_id,)).fetchall()
    return [
        {
            "id": row["id"],
            "state": row["state"],
            **json.loads(row["spec"]),
            **(json.loads(row["result"]) if row["result"] else {}),
        }
        for row in data
    ]


def save(study_id, case_id, state, result=None):
    with connection() as conn:
        conn.execute(
            "UPDATE cases SET state=?, result=? WHERE study=? AND id=?",
            (state, dumps(result) if result is not None else None, study_id, case_id),
        )
        if state == "finished":
            conn.execute("DELETE FROM events WHERE study=? AND case_id=?", (study_id, case_id))
            conn.execute("INSERT INTO events(study,case_id) VALUES (?,?)", (study_id, case_id))


def changes(study_id, after=0):
    with connection() as conn:
        conn.execute("BEGIN")
        cursor = conn.execute(
            "SELECT COALESCE(MAX(revision),0) FROM events WHERE study=?", (study_id,)
        ).fetchone()[0]
        counts = {
            row["state"]: row["n"]
            for row in conn.execute(
                "SELECT state,COUNT(*) AS n FROM cases WHERE study=? GROUP BY state", (study_id,)
            ).fetchall()
        }
        data = conn.execute(
            "SELECT cases.* FROM cases JOIN events ON cases.study=events.study AND cases.id=events.case_id WHERE cases.study=? AND events.revision>? AND events.revision<=? ORDER BY events.revision",
            (study_id, after, cursor),
        ).fetchall()
    rows = [
        {
            "id": row["id"],
            "state": row["state"],
            **json.loads(row["spec"]),
            **json.loads(row["result"]),
        }
        for row in data
    ]
    return rows, counts, cursor


def state(study_id, value, pid=None):
    with connection() as conn:
        conn.execute(
            "UPDATE studies SET state=?,pid=COALESCE(?,pid) WHERE id=?", (value, pid, study_id)
        )


def claim(study_id):
    with connection() as conn:
        active_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM studies WHERE state IN ('starting','running','pausing')"
            ).fetchall()
        ]
    for active_id in active_ids:
        study(active_id, trusted=True)
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            "SELECT id FROM studies WHERE state IN ('starting','running','pausing')"
        ).fetchall()
        if active:
            raise HTTPException(409, "A study is already running on this server")
        changed = conn.execute(
            "UPDATE studies SET state='starting',pid=? WHERE id=? AND state IN ('ready','paused','interrupted')",
            (os.getpid(), study_id),
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "This study cannot be started")


def activate(study_id):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        changed = conn.execute(
            "UPDATE studies SET state='running',pid=? WHERE id=? AND state='starting'",
            (os.getpid(), study_id),
        )
        if changed.rowcount != 1:
            conn.execute(
                "UPDATE studies SET state='paused' WHERE id=? AND state='pausing'", (study_id,)
            )
            return False
        return True
