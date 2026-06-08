import json
import logging
import psycopg2
import psycopg2.extras
import psycopg2.pool
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from typing import Any, Dict
from ..utils.crud_helpers import segment_route

logger = logging.getLogger(__name__)

# Module-level connection pool — created once on first import.
# minconn=1 keeps one connection warm; maxconn=5 handles burst traffic.
_pool: psycopg2.pool.SimpleConnectionPool = None


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        url = (settings.DATABASE_URL or "").strip()
        _pool = psycopg2.pool.SimpleConnectionPool(1, 5, url, sslmode="require")
    return _pool


def _get_conn():
    """Check out a connection from the pool, replacing it if Neon dropped it."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        # Lightweight check — if Neon closed the connection while idle this will fail
        conn.cursor().execute("SELECT 1")
    except psycopg2.OperationalError:
        # Connection is dead; close it, open a fresh one, and put that in the pool
        try:
            conn.close()
        except Exception:
            pass
        conn = psycopg2.connect((settings.DATABASE_URL or "").strip(), sslmode="require")
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
                    ON CONFLICT (leg_id, step_id) DO UPDATE SET coordinates = EXCLUDED.coordinates
                    """,
                    (auth_token, chat_id, leg_id, step_idx, json.dumps(coords)),
                )
                step["geometry"]["coordinates"] = leg_id
    return legs


def create_chat(
    auth_token: str, chat_id: str, chat_data: Dict[str, Any], chat_logs: Dict[str, Any]
):
    """Create a new chat instance in the database."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chats (user_id, chat_id, chat_data, chat_log)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                  SET chat_data = EXCLUDED.chat_data,
                      chat_log  = EXCLUDED.chat_log
                RETURNING *
                """,
                (auth_token, chat_id, json.dumps(chat_data), json.dumps(chat_logs)),
            )
            row = cur.fetchone()
        conn.commit()
        if row is None:
            logger.warning("create_chat INSERT RETURNING returned no row — chat_id=%s", chat_id)
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


def get_segments(route_id: str):
    """Get all segments associated with a single route_id."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM route_segments WHERE route_id = %s ORDER BY segment_id::int",
                (route_id,),
            )
            rows = cur.fetchall()
        segs = []
        for row in rows:
            segs.extend(row["coords"])
        return segs
    finally:
        _put_conn(conn)


def update_chat_component(auth_token: str, chat_id: str, chat_schema: BaseModel, prefix: str):
    """Update a component of a user's chat in the database."""
    comp_dict = chat_schema.model_dump()

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
                f"SELECT {col_name} FROM chats WHERE user_id = %s AND chat_id = %s",
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
                return None

            current_val = row[col_name] or {}
            empty_vals = [[], {}, None, False, ""]
            route_id = f"{auth_token}-{chat_id}"

            for key, value in comp_dict.items():
                route = None
                if value not in empty_vals:
                    if key == "initial":
                        route = value["geometry"]["coordinates"]
                        value["geometry"] = route_id
                        value["legs"] = _store_legs(
                            conn, auth_token, chat_id, route_id, value["legs"]
                        )
                    if key == "route":
                        route = value["geometry"]["coordinates"]
                        value["geometry"]["coordinates"] = route_id
                    if route:
                        segments = segment_route(route)
                        for seg_id, segment in enumerate(segments):
                            cur.execute(
                                """
                                INSERT INTO route_segments (user_id, chat_id, route_id, segment_id, coords)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (route_id, segment_id) DO UPDATE SET coords = EXCLUDED.coords
                                """,
                                (auth_token, chat_id, route_id, str(seg_id), json.dumps(segment)),
                            )
                    current_val[key] = value

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


def restore_legs(legs: list[Any]):
    """Restore the coordinates of all steps to their proper values."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            rest_legs = []
            for leg in legs:
                leg_id = leg["steps"][0]["geometry"]["coordinates"]
                cur.execute("SELECT * FROM steps WHERE leg_id = %s ORDER BY step_id", (leg_id,))
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
