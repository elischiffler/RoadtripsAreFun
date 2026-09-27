"""Postgres-backed MemoryStore implementation (chat-agent design §4).

This is the concrete persistence for the agent's memory layer. It reuses the
connection-pool helpers from ``chat_crud`` (``_get_conn`` / ``_put_conn``) rather
than opening a second pool, takes ``auth_token`` (the decoded ``user_id``) as the
first argument, reads through ``RealDictCursor``, and commits / rolls back on
writes — mirroring the ``chat_crud`` conventions exactly.

All memory rows live in one ``chat_memory`` table with a ``mem_type``
discriminator (``'fact'`` | ``'summary'``). Facts are cross-chat and use the
empty-string sentinel ``chat_id = ''`` (``_CROSS_CHAT``) — NOT NULL, so it works
as a composite-PK / ON CONFLICT target; the summary is per ``(user_id, chat_id)``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import psycopg2.extras
from pydantic import ValidationError

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.schemas import LLMMessage

# Reuse the single module-level pool from chat_crud — do NOT open a second pool.
from . import chat_crud
from .chat_crud import _get_conn, _put_conn

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now for row timestamps / empty-memory defaults."""
    return datetime.now(UTC)


def _empty_conversation(chat_id: str) -> ConversationMemory:
    """An empty ConversationMemory for a chat with no summary row yet.

    ``ConversationMemory.updated_at`` is a required field (owned by Stream A in
    ``app/agent/memory.py``), so we supply a fresh timestamp here.
    """
    return ConversationMemory(chat_id=chat_id, updated_at=_utcnow())


# psycopg2 uses NULL, not None, in a PRIMARY KEY — but a NULL column can't be part
# of a usable UPSERT conflict target, so cross-chat facts use this sentinel for
# chat_id. It keeps the composite PK deterministic while still meaning "no chat".
_CROSS_CHAT = ""

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_memory (
    user_id     TEXT        NOT NULL,
    chat_id     TEXT        NOT NULL DEFAULT '',
    mem_type    TEXT        NOT NULL,
    mem_key     TEXT        NOT NULL,
    mem_value   JSONB       NOT NULL,
    confidence  REAL        DEFAULT 1.0,
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, chat_id, mem_type, mem_key)
)
"""

# Warm-once guard so the DDL doesn't run on every call.
_table_ready = False


def ensure_memory_table() -> None:
    """Create the ``chat_memory`` table if it doesn't exist (idempotent).

    Safe to call lazily on first write or eagerly from a startup lifespan hook.
    Runs ``CREATE TABLE IF NOT EXISTS`` and caches success so repeated calls are
    cheap no-ops.
    """
    global _table_ready
    if _table_ready:
        return
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()
        _table_ready = True
    except Exception as exc:
        logger.error("ensure_memory_table DB error: %s", exc)
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def load_facts(auth_token: str) -> list[MemoryFact]:
    """Load all durable cross-chat facts for a user.

    Returns a list of :class:`MemoryFact`, newest first. Rows whose JSONB payload
    fails validation are skipped with a warning rather than failing the load.
    """
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT mem_value FROM chat_memory
                WHERE user_id = %s AND mem_type = 'fact'
                ORDER BY updated_at DESC
                """,
                (auth_token,),
            )
            rows = cur.fetchall()
        facts: list[MemoryFact] = []
        for row in rows:
            payload = row["mem_value"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            try:
                facts.append(MemoryFact.model_validate(payload))
            except ValidationError as exc:
                logger.warning("load_facts: skipping invalid fact payload: %s", exc)
        return facts
    finally:
        _put_conn(conn)


def upsert_facts(auth_token: str, facts: list[MemoryFact]) -> None:
    """Upsert cross-chat facts, keyed by ``(user_id, mem_key)``.

    Facts are stored with ``chat_id = ''`` (cross-chat); any ``source_chat_id`` is
    preserved as metadata inside the JSONB payload. On conflict we keep the
    newer / higher-confidence write via ``ON CONFLICT ... DO UPDATE``.
    """
    if not facts:
        return
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            for fact in facts:
                cur.execute(
                    """
                    INSERT INTO chat_memory
                        (user_id, chat_id, mem_type, mem_key, mem_value, confidence, updated_at)
                    VALUES (%s, %s, 'fact', %s, %s, %s, %s)
                    ON CONFLICT (user_id, chat_id, mem_type, mem_key) DO UPDATE
                        SET mem_value  = EXCLUDED.mem_value,
                            confidence = EXCLUDED.confidence,
                            updated_at = EXCLUDED.updated_at
                        WHERE EXCLUDED.confidence >= chat_memory.confidence
                           OR EXCLUDED.updated_at >= chat_memory.updated_at
                    """,
                    (
                        auth_token,
                        _CROSS_CHAT,
                        fact.key,
                        json.dumps(fact.model_dump(mode="json")),
                        fact.confidence,
                        fact.updated_at,
                    ),
                )
        conn.commit()
    except Exception as exc:
        logger.error("upsert_facts DB error user_id=%s: %s", auth_token, exc)
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def load_conversation(auth_token: str, chat_id: str) -> ConversationMemory:
    """Load the rolling conversation summary for a ``(user_id, chat_id)``.

    Returns an empty :class:`ConversationMemory` for ``chat_id`` when no summary
    row exists yet.
    """
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT mem_value FROM chat_memory
                WHERE user_id = %s AND chat_id = %s
                  AND mem_type = 'summary' AND mem_key = 'summary'
                """,
                (auth_token, chat_id),
            )
            row = cur.fetchone()
        if not row:
            return _empty_conversation(chat_id)
        payload = row["mem_value"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            return ConversationMemory.model_validate(payload)
        except ValidationError as exc:
            logger.warning(
                "load_conversation: invalid summary payload chat_id=%s: %s", chat_id, exc
            )
            return _empty_conversation(chat_id)
    finally:
        _put_conn(conn)


def save_conversation(auth_token: str, chat_id: str, mem: ConversationMemory) -> None:
    """Upsert the single rolling-summary row for a ``(user_id, chat_id)``."""
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_memory
                    (user_id, chat_id, mem_type, mem_key, mem_value, confidence, updated_at)
                VALUES (%s, %s, 'summary', 'summary', %s, 1.0, %s)
                ON CONFLICT (user_id, chat_id, mem_type, mem_key) DO UPDATE
                    SET mem_value  = EXCLUDED.mem_value,
                        updated_at = EXCLUDED.updated_at
                """,
                (
                    auth_token,
                    chat_id,
                    json.dumps(mem.model_dump(mode="json")),
                    mem.updated_at,
                ),
            )
        conn.commit()
    except Exception as exc:
        logger.error(
            "save_conversation DB error user_id=%s chat_id=%s: %s", auth_token, chat_id, exc
        )
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def load_trip_profile(auth_token: str, chat_id: str) -> str | None:
    """Load the per-chat trip-profile JSON string for a ``(user_id, chat_id)``.

    Returns the stored JSON string (the whole :class:`TripProfile`) or ``None``
    when no trip-profile row exists yet. The single per-chat row uses
    ``mem_type='trip'`` / ``mem_key='trip'``.
    """
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT mem_value FROM chat_memory
                WHERE user_id = %s AND chat_id = %s
                  AND mem_type = 'trip' AND mem_key = 'trip'
                """,
                (auth_token, chat_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        payload = row["mem_value"]
        # mem_value is JSONB; the trip profile is stored AS a JSON string value,
        # so a str comes back directly, while a dict is re-serialized.
        if isinstance(payload, str):
            return payload
        return json.dumps(payload)
    finally:
        _put_conn(conn)


def save_trip_profile(auth_token: str, chat_id: str, profile_json: str) -> None:
    """Upsert the single per-chat trip-profile row for a ``(user_id, chat_id)``."""
    ensure_memory_table()
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_memory
                    (user_id, chat_id, mem_type, mem_key, mem_value, confidence, updated_at)
                VALUES (%s, %s, 'trip', 'trip', %s, 1.0, %s)
                ON CONFLICT (user_id, chat_id, mem_type, mem_key) DO UPDATE
                    SET mem_value  = EXCLUDED.mem_value,
                        updated_at = EXCLUDED.updated_at
                """,
                (
                    auth_token,
                    chat_id,
                    json.dumps(profile_json),
                    _utcnow(),
                ),
            )
        conn.commit()
    except Exception as exc:
        logger.error(
            "save_trip_profile DB error user_id=%s chat_id=%s: %s", auth_token, chat_id, exc
        )
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def load_recent_turns(auth_token: str, chat_id: str, limit: int = 10) -> list[LLMMessage]:
    """Best-effort verbatim short-term window from the existing ``ChatLog``.

    The verbatim recent turns are NOT stored in ``chat_memory`` — the frontend
    already persists the full ``ChatLog`` (messages) to ``chats.chat_log`` via
    ``chat_crud``. We only READ it here and must never re-write it (the frontend
    owns that write).

    Reads ``get_chat(user_id, chat_id)["chat_log"]["messages"]``, keeps the last
    ``limit`` messages that carry real text, and maps the frontend ``sender`` to
    an LLM ``role``: ``'user'`` -> ``'user'``, anything else (``'bot'``) ->
    ``'assistant'``. Loading placeholders, empty text, and button-only messages
    are skipped.

    This is best-effort context: any failure (missing chat, malformed payload,
    DB error) is swallowed and yields ``[]`` so it can never break a turn.
    """
    if limit <= 0:
        return []
    try:
        chat = chat_crud.get_chat(auth_token, chat_id)
        if not chat:
            return []
        chat_log = chat.get("chat_log")
        if isinstance(chat_log, str):
            chat_log = json.loads(chat_log)
        if not isinstance(chat_log, dict):
            return []
        messages = chat_log.get("messages")
        if not isinstance(messages, list):
            return []

        turns: list[LLMMessage] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            text = msg.get("text")
            if not isinstance(text, str) or not text.strip():
                # Skip empty / loading placeholders.
                continue
            if text == "loading":
                continue
            sender = msg.get("sender")
            role = "user" if sender == "user" else "assistant"
            turns.append(LLMMessage(role=role, content=text))

        return turns[-limit:]
    except Exception as exc:  # best-effort: never raise out of context loading
        logger.warning("load_recent_turns: skipping short-term memory chat_id=%s: %s", chat_id, exc)
        return []


class MemoryCrudStore:
    """Postgres-backed :class:`~app.agent.memory.MemoryStore` implementation.

    A thin class wrapper over the module-level functions so the agent loop can be
    injected with a single object that satisfies the ``MemoryStore`` Protocol.
    """

    def load_facts(self, user_id: str) -> list[MemoryFact]:
        return load_facts(user_id)

    def upsert_facts(self, user_id: str, facts: list[MemoryFact]) -> None:
        upsert_facts(user_id, facts)

    def load_conversation(self, user_id: str, chat_id: str) -> ConversationMemory:
        return load_conversation(user_id, chat_id)

    def save_conversation(self, user_id: str, chat_id: str, mem: ConversationMemory) -> None:
        save_conversation(user_id, chat_id, mem)

    def load_trip_profile(self, user_id: str, chat_id: str) -> str | None:
        return load_trip_profile(user_id, chat_id)

    def save_trip_profile(self, user_id: str, chat_id: str, profile_json: str) -> None:
        save_trip_profile(user_id, chat_id, profile_json)

    def load_recent_turns(self, user_id: str, chat_id: str, limit: int = 10) -> list[LLMMessage]:
        return load_recent_turns(user_id, chat_id, limit)


def extract_facts_from_turn(user_message: str, assistant_reply: str) -> list[MemoryFact]:
    """Deprecated: durable-fact capture is now TOOL-DRIVEN, not extracted.

    The agent persists trip/preference data by calling the ``update_trip_profile``
    / ``remember_fact`` tools during its normal turn (see
    ``app/agent/tool_dispatcher.py``), so there is no separate LLM extraction
    pass — which also avoids a second gateway call per turn. This function is
    retained as a no-op for backward compatibility and always returns ``[]``.
    """
    return []
