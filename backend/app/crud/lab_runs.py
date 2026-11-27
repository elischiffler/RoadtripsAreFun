"""Owner-scoped experiment storage. Schema is applied explicitly, never at request time."""

from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from app.core.config import settings
from app.crud.chat_crud import _get_conn, _put_conn
from app.schemas.chat_schemas import without_road_data


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


def begin(user_id, payload, run_id=None):
    run_id = str(run_id or uuid4())
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


_ROAD_METRICS = {
    "baseline_gaps_seconds",
    "baseline_seconds",
    "detour_provenance",
    "detour_raw_seconds",
    "detour_seconds",
    "direct_route",
    "distance_meters",
    "driving",
    "driving_gaps",
    "duration_seconds",
    "estimated_detour_seconds",
    "extra_distance_meters",
    "extra_duration_seconds",
    "maximum_baseline_gap_seconds",
    "maximum_stretch_seconds",
    "query_points",
    "road_checks",
    "route_progress_seconds",
    "solo_duration_seconds",
}


def _remove_provider_metrics(value):
    if isinstance(value, dict):
        return {
            key: _remove_provider_metrics(item)
            for key, item in value.items()
            if key not in _ROAD_METRICS
        }
    if isinstance(value, list):
        return [_remove_provider_metrics(item) for item in value]
    return value


def durable_result(envelope):
    provider = envelope.get("directions_provider") or (envelope.get("route") or {}).get(
        "directions_provider"
    )
    if provider != "apple":
        return envelope
    return _remove_provider_metrics(without_road_data(envelope))


def finish(user_id, run_id, envelope, metrics):
    durable = durable_result(envelope)
    if durable is not envelope:
        envelope = durable
        metrics = _remove_provider_metrics(without_road_data(metrics))
    rows = _query(
        "UPDATE algorithm_lab_runs SET status=%s, finished_at=now(), input=%s, metrics=%s, "
        "error_code=%s, result=%s WHERE id=%s AND user_id=%s AND status='running' RETURNING id",
        (
            "failed" if envelope["error"] else "completed",
            Json(envelope["input_snapshot"]),
            Json(metrics),
            (envelope["error"] or {}).get("code"),
            Json(
                {
                    key: envelope.get(key)
                    for key in (
                        "route",
                        "itinerary",
                        "error",
                        "stages",
                        "attempts",
                        "explanation",
                        "direct_route",
                        "directions_provider",
                        "input_snapshot",
                    )
                }
            ),
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
        "metrics,error_code,result->'error' AS error,result->'stages' AS stages,"
        "result->'attempts' AS attempts,(result->'route' IS NOT NULL AND result->'route' != 'null'::jsonb) AS has_result "
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


def record(user_id, run_id):
    rows = _query(
        "SELECT id,status,mode,input,metrics,result FROM algorithm_lab_runs "
        "WHERE id=%s AND user_id=%s",
        (str(run_id), user_id),
    )
    return rows[0] if rows else None


def cancel(user_id, run_id):
    _query(
        "UPDATE algorithm_lab_runs SET status='failed', finished_at=now(), "
        "error_code='cancelled', result=%s WHERE id=%s AND user_id=%s "
        "AND status='running' RETURNING id",
        (Json({"error": {"code": "cancelled", "message": "Run cancelled."}}), str(run_id), user_id),
        write=True,
    )
