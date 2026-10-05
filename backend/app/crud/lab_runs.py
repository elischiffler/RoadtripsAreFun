"""Owner-scoped experiment storage. Schema is applied explicitly, never at request time."""

from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from app.core.config import settings
from app.crud.chat_crud import _get_conn, _put_conn


def _query(sql, args, *, write=False):
    if write and settings.NEON_READ_ONLY:
        raise RuntimeError("Database writes are disabled")
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = 5000")
            cur.execute(sql, args)
            rows = [dict(row) for row in cur.fetchall()]
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def begin(user_id, payload):
    run_id = str(uuid4())
    _query(
        "INSERT INTO algorithm_lab_runs (id,user_id,mode,preset_id,run_type,batch_id,repeat_index,input) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (
            run_id,
            user_id,
            payload["mode"],
            payload["preset_id"],
            "benchmark" if payload.get("batch_id") else "interactive",
            payload.get("batch_id"),
            payload.get("repeat_index", 1),
            Json(payload),
        ),
        write=True,
    )
    return run_id


def finish(user_id, run_id, envelope, metrics):
    rows = _query(
        "UPDATE algorithm_lab_runs SET status=%s, finished_at=now(), input=%s, metrics=%s, "
        "error_code=%s, result=%s WHERE id=%s AND user_id=%s AND status='running' RETURNING id",
        (
            "failed" if envelope["error"] else "completed",
            Json(envelope["input_snapshot"]),
            Json(metrics),
            (envelope["error"] or {}).get("code"),
            Json({key: envelope.get(key) for key in ("route", "itinerary")}),
            run_id,
            user_id,
        ),
        write=True,
    )
    if not rows:
        raise ValueError("Run does not exist or is already finalized")


def history(user_id, limit=100, offset=0):
    return _query(
        "SELECT id,started_at,finished_at,status,mode,preset_id,run_type,batch_id,repeat_index,input,"
        "metrics,error_code,(result->'route' IS NOT NULL AND result->'route' != 'null'::jsonb) AS has_result "
        "FROM algorithm_lab_runs WHERE user_id=%s "
        "ORDER BY started_at DESC,id DESC LIMIT %s OFFSET %s",
        (user_id, limit, offset),
    )


def result(user_id, run_id):
    rows = _query(
        "SELECT result FROM algorithm_lab_runs WHERE id=%s AND user_id=%s",
        (str(run_id), user_id),
    )
    return rows[0]["result"] if rows else None
