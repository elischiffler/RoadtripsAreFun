"""Account-scoped profiles in existing generic chat_memory rows; no runtime DDL.

These rows never participate in fact/persona extraction. Each operation uses the
verified Cognito subject, not a client-supplied account identifier.
"""

import json
from uuid import UUID

from psycopg2.extras import RealDictCursor

from app.crud import chat_crud
from app.schemas.preference_profiles import PreferenceProfile, PreferenceProfileInput

_KIND = "preference_profile"
MAX_PROFILES = 100


class ProfileLimitReached(Exception):
    pass


def list_profiles(user_id: str) -> list[PreferenceProfile]:
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT mem_key, mem_value FROM chat_memory
                WHERE user_id = %s AND chat_id = '' AND mem_type = %s
                ORDER BY updated_at DESC, mem_key LIMIT %s""",
                (user_id, _KIND, MAX_PROFILES),
            )
            return [
                PreferenceProfile.model_validate({**row["mem_value"], "id": row["mem_key"]})
                for row in cur.fetchall()
            ]
    finally:
        chat_crud._put_conn(conn)


def save_profile(user_id: str, profile_id: UUID, value: PreferenceProfileInput):
    conn = chat_crud._get_conn()
    try:
        with conn.cursor() as cur:
            # Serialize first writes and enforce the bounded account collection.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"profiles:{user_id}",))
            cur.execute(
                """SELECT count(*), count(*) FILTER (WHERE mem_key = %s)
                FROM chat_memory WHERE user_id = %s AND chat_id = '' AND mem_type = %s""",
                (str(profile_id), user_id, _KIND),
            )
            count, existing = cur.fetchone()
            if count >= MAX_PROFILES and not existing:
                raise ProfileLimitReached
            cur.execute(
                """INSERT INTO chat_memory (user_id, chat_id, mem_type, mem_key, mem_value)
                VALUES (%s, '', %s, %s, %s::jsonb)
                ON CONFLICT (user_id, chat_id, mem_type, mem_key) DO UPDATE
                SET mem_value = EXCLUDED.mem_value, updated_at = now()""",
                (user_id, _KIND, str(profile_id), json.dumps(value.model_dump(mode="json"))),
            )
        conn.commit()
        return PreferenceProfile(id=profile_id, **value.model_dump())
    except Exception:
        conn.rollback()
        raise
    finally:
        chat_crud._put_conn(conn)


def delete_profile(user_id: str, profile_id: UUID):
    conn = chat_crud._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM chat_memory
                WHERE user_id = %s AND chat_id = '' AND mem_type = %s AND mem_key = %s""",
                (user_id, _KIND, str(profile_id)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        chat_crud._put_conn(conn)
