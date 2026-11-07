import hashlib
import json
import logging
from threading import Lock
from typing import Any
from uuid import uuid4

import psycopg2
import psycopg2.extras
import psycopg2.pool
from pydantic import BaseModel

from app.core.config import settings
from app.schemas import chat_schemas

from ..utils.crud_helpers import segment_route

logger = logging.getLogger(__name__)

# Module-level connection pool, initialized lazily for concurrent agent workers.
# minconn=1 keeps one connection warm; maxconn=5 handles burst traffic.
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = Lock()


class ChatIdentityConflict(ValueError):
    """A trip number already belongs to another planning operation."""


class ChatSnapshotConflict(ValueError):
    """The saved trip changed after the editor loaded its snapshot."""


def chat_data_revision(data: dict[str, Any]) -> str:
    """Opaque revision of exact durable JSON, before geometry hydration."""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None or _pool.closed:
            url = (settings.DATABASE_URL or "").strip()
            _pool = psycopg2.pool.ThreadedConnectionPool(
                1, 5, url, sslmode=settings.DATABASE_SSLMODE, connect_timeout=5
            )
        return _pool


def _get_conn():
    """Check out a connection from the pool, replacing it if Neon dropped it."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        # Validate idle connections before use; keep replacements pool-owned.
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    return conn


def _put_conn(conn):
    """Return a connection to the pool."""
    _get_pool().putconn(conn)


def _store_legs(conn, auth_token: str, chat_id: str, route_id: str, legs: list):
    """Store step coordinates for each leg into the steps table."""
    with conn.cursor() as cur:
        for i, leg in enumerate(legs):
            leg_id = f"{route_id}-leg-{i}"
            steps = leg.get("steps", [])
            for step_idx, step in enumerate(steps):
                coords = step["geometry"]["coordinates"]
                cur.execute(
                    """
                    INSERT INTO steps (user_id, chat_id, leg_id, step_id, coordinates)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (leg_id, step_id) DO UPDATE
                      SET coordinates = EXCLUDED.coordinates
                      WHERE steps.user_id = EXCLUDED.user_id
                        AND steps.chat_id = EXCLUDED.chat_id
                    RETURNING user_id
                    """,
                    (auth_token, chat_id, leg_id, step_idx, json.dumps(coords)),
                )
                if cur.fetchone() is None:
                    raise PermissionError("Step identifier belongs to a different chat")
                step["geometry"]["coordinates"] = leg_id
    return legs


def create_chat(
    auth_token: str, chat_id: str, chat_data: dict[str, Any], chat_logs: dict[str, Any]
):
    """Create a trip, allowing repeated creates only for the same planning ID.

    The conflict predicate is part of the upsert and checked while PostgreSQL
    locks the conflicting row. A separate existence read would race across tabs.
    Modern repeated creates return their existing durable snapshot unchanged.
    Missing/null legacy planning IDs retain their prior upsert behavior.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chats (user_id, chat_id, chat_data, chat_log)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                  SET chat_data = CASE WHEN chats.chat_data->>'agentChatId' IS NULL
                        THEN EXCLUDED.chat_data ELSE chats.chat_data END,
                      chat_log = CASE WHEN chats.chat_data->>'agentChatId' IS NULL
                        THEN EXCLUDED.chat_log ELSE chats.chat_log END
                  WHERE chats.chat_data->>'agentChatId'
                    IS NOT DISTINCT FROM EXCLUDED.chat_data->>'agentChatId'
                RETURNING *
                """,
                (auth_token, chat_id, json.dumps(chat_data), json.dumps(chat_logs)),
            )
            row = cur.fetchone()
            if row is None:
                raise ChatIdentityConflict("Trip ID belongs to a different planning request")
        conn.commit()
        return row
    except Exception as exc:
        logger.error("create_chat DB error chat_id=%s: %s", chat_id, exc)
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def get_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    """Get an individual chat from the database."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM chats WHERE user_id = %s AND chat_id = %s", (auth_token, chat_id)
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def get_all_chats(auth_token: str):
    """Get all chats for a given authentication token."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM chats WHERE user_id = %s", (auth_token,))
            rows = cur.fetchall()
        return [
            {
                "UserId": row["user_id"],
                "ChatId": row["chat_id"],
                "ChatData": row["chat_data"],
                "ChatLog": row["chat_log"],
            }
            for row in rows
        ]
    finally:
        _put_conn(conn)


def get_segments(user_id: str, chat_id: str, route_id: str):
    """Get segments only from the verified user's chat."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM route_segments
                   WHERE user_id = %s AND chat_id = %s AND route_id = %s
                   ORDER BY segment_id::int""",
                (user_id, chat_id, route_id),
            )
            rows = cur.fetchall()
        segs = []
        for row in rows:
            segs.extend(row["coords"])
        return segs
    finally:
        _put_conn(conn)


def update_chat_component(
    auth_token: str,
    chat_id: str,
    chat_schema: BaseModel,
    prefix: str,
    *,
    expected_revision: str | None = None,
    update_scope: str = "route",
):
    """Update a component of a user's chat in the database."""
    # Durable JSON must contain ISO timestamps, not Pydantic datetime objects.
    comp_dict = chat_schema.model_dump(mode="json")
    if prefix == "ChatData" and "presentation" not in chat_schema.model_fields_set:
        # An older client cannot clear UI metadata it never sent or understood.
        comp_dict.pop("presentation", None)

    _ALLOWED_PREFIXES = {
        "ChatData": "chat_data",
        "ChatLog": "chat_log",
    }
    if prefix not in _ALLOWED_PREFIXES:
        raise ValueError(
            f"update_chat_component: invalid prefix {prefix!r}; must be one of {list(_ALLOWED_PREFIXES)}"
        )
    col_name = _ALLOWED_PREFIXES[prefix]

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT {col_name} FROM chats WHERE user_id = %s AND chat_id = %s FOR UPDATE",
                (auth_token, chat_id),
            )
            row = cur.fetchone()
            if not row:
                logger.warning(
                    "update_chat_component: no row found for chat_id=%s prefix=%s — "
                    "createChat was never called or used a different chat_id",
                    chat_id,
                    prefix,
                )
                conn.rollback()
                return None

            current_val = row[col_name] or {}
            if expected_revision is not None:
                if prefix != "ChatData" or chat_data_revision(current_val) != expected_revision:
                    raise ChatSnapshotConflict("Saved trip changed; reload before editing")
                if update_scope == "presentation":
                    comp_dict = {"presentation": comp_dict.get("presentation")}
                elif update_scope == "route":
                    # Route edits cannot replace unrelated car, account or log state.
                    comp_dict = {key: comp_dict[key] for key in ("route", "itinerary", "stops")}
                    comp_dict["tripProfile"] = {
                        **(current_val.get("tripProfile") or {}),
                        "num_stops": comp_dict["stops"],
                    }
                    comp_dict["presentation"] = {
                        **(current_val.get("presentation") or {}),
                        "visitedStopIds": [],
                    }
            empty_vals = [[], {}, None, False, ""]
            route_id = f"{auth_token}-{chat_id}"

            for key, value in comp_dict.items():
                if prefix == "ChatData" and key == "presentation":
                    # Unlike legacy optional fields, an explicitly supplied empty
                    # object/null is an intentional reset of this UI-only state.
                    current_val[key] = value
                    continue
                route = None
                if value not in empty_vals:
                    if key == "initial":
                        route = value["geometry"]["coordinates"]
                        value["geometry"] = route_id
                        value["legs"] = _store_legs(
                            conn, auth_token, chat_id, route_id, value["legs"]
                        )
                    if key == "route":
                        # New final routes use their own storage identity, preserving
                        # legacy initial geometry that may share the old identifier.
                        route_id = f"{auth_token}-{chat_id}-final"
                        route = value["geometry"]["coordinates"]
                        value["geometry"]["coordinates"] = route_id
                    if route:
                        segments = segment_route(route)
                        for seg_id, segment in enumerate(segments):
                            cur.execute(
                                """
                                INSERT INTO route_segments (user_id, chat_id, route_id, segment_id, coords)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (route_id, segment_id) DO UPDATE
                                  SET coords = EXCLUDED.coords
                                  WHERE route_segments.user_id = EXCLUDED.user_id
                                    AND route_segments.chat_id = EXCLUDED.chat_id
                                RETURNING user_id
                                """,
                                (auth_token, chat_id, route_id, str(seg_id), json.dumps(segment)),
                            )
                            if cur.fetchone() is None:
                                raise PermissionError(
                                    "Route segment identifier belongs to a different chat"
                                )
                        cur.execute(
                            """DELETE FROM route_segments
                               WHERE user_id = %s AND chat_id = %s AND route_id = %s
                                 AND NOT (segment_id = ANY(%s))""",
                            (auth_token, chat_id, route_id, [str(i) for i in range(len(segments))]),
                        )
                    current_val[key] = value

            if prefix == "ChatData":
                # Invalidate snapshots even when only segmented coordinates changed.
                current_val["_storageRevision"] = str(uuid4())
            cur.execute(
                f"UPDATE chats SET {col_name} = %s WHERE user_id = %s AND chat_id = %s RETURNING *",
                (json.dumps(current_val), auth_token, chat_id),
            )
            result = cur.fetchall()
            if not result:
                logger.warning(
                    "update_chat_component: UPDATE RETURNING empty for chat_id=%s prefix=%s",
                    chat_id,
                    prefix,
                )
        conn.commit()
        return result
    except Exception as exc:
        logger.error(
            "update_chat_component DB error chat_id=%s prefix=%s: %s", chat_id, prefix, exc
        )
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def delete_chat(auth_token: str, chat_id: str):
    """Delete a desired chat from the database."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "DELETE FROM chats WHERE user_id = %s AND chat_id = %s RETURNING *",
                (auth_token, chat_id),
            )
            result = cur.fetchall()
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def restore_legs(user_id: str, chat_id: str, legs: list[Any]):
    """Restore step coordinates only from the verified user's chat."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            rest_legs = []
            for leg in legs:
                leg_id = leg["steps"][0]["geometry"]["coordinates"]
                cur.execute(
                    """SELECT * FROM steps
                       WHERE user_id = %s AND chat_id = %s AND leg_id = %s
                       ORDER BY step_id""",
                    (user_id, chat_id, leg_id),
                )
                steps_coords = cur.fetchall()
                num_steps = len(leg["steps"])
                for step_row in steps_coords:
                    idx = step_row["step_id"]
                    # Guard: only restore if the step index still exists in the leg
                    if idx < num_steps:
                        leg["steps"][idx]["geometry"]["coordinates"] = step_row["coordinates"]
                    else:
                        logger.warning(
                            "restore_legs: DB has step_id=%s for leg_id=%s but leg only has %d steps — skipping",
                            idx,
                            leg_id,
                            num_steps,
                        )
                rest_legs.append(leg)
        return rest_legs
    finally:
        _put_conn(conn)
