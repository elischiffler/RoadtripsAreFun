"""Contract 2 — Memory model (agent loop <-> persistence), design doc §4.

Stream A provides only the *interface* the agent loop depends on: the
:class:`MemoryStore` Protocol plus the :class:`MemoryFact` /
:class:`ConversationMemory` payload models. The real Postgres-backed
implementation lives in ``crud/memory_crud.py`` (Stream B); tests inject an
in-memory fake (see ``tests/agent/conftest.py``).

Memory has three tiers:
- **Facts** — durable, free-form, per ``user_id`` (cross-chat).
- **Conversation** — a rolling summary per ``(user_id, chat_id)``. The verbatim
  recent window is *not* duplicated here; it comes from the existing
  ``ChatLog.messages`` persisted by ``chat_crud.py``.
- **Trip profile** — the structured per-``(user_id, chat_id)`` trip data the
  agent fills in during a chat (start/destination/stops/budget/...). Stored as a
  single per-chat row; see :mod:`app.agent.trip_profile`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryFact(BaseModel):
    """A durable, cross-chat fact about the traveler.

    Written via upsert by ``(user_id, key)`` — newer/higher-confidence facts
    replace older ones. Examples: ``home_city="Boston, MA"``,
    ``pref.avoid="big cities"``, ``budget.style="frugal"``.

    ``updated_at`` defaults to "now" (a refinement over the doc's bare
    ``updated_at: datetime``) so callers can construct a fact without threading a
    timestamp; the persistence layer still overwrites it on write.
    """

    key: str
    value: str
    confidence: float = 1.0
    source_chat_id: str | None = None
    updated_at: datetime = Field(default_factory=_utcnow)


class ConversationMemory(BaseModel):
    """Rolling summary of turns older than the verbatim recent window."""

    chat_id: str
    summary: str = ""
    summary_turn_count: int = 0
    updated_at: datetime = Field(default_factory=_utcnow)


@runtime_checkable
class MemoryStore(Protocol):
    """What the agent loop needs from persistence.

    The real implementation is ``crud/memory_crud.py``; the loop only ever sees
    this interface, which is what makes ``run_turn`` unit-testable with a fake.
    """

    def load_facts(self, user_id: str) -> list[MemoryFact]: ...

    def upsert_facts(self, user_id: str, facts: list[MemoryFact]) -> None: ...

    def load_conversation(self, user_id: str, chat_id: str) -> ConversationMemory: ...

    def save_conversation(
        self, user_id: str, chat_id: str, mem: ConversationMemory
    ) -> None: ...

    def load_trip_profile(self, user_id: str, chat_id: str) -> str | None:
        """Return the stored trip-profile JSON string for a chat, or ``None``."""
        ...

    def save_trip_profile(self, user_id: str, chat_id: str, profile_json: str) -> None:
        """Persist the trip-profile JSON string for a chat (upsert)."""
        ...
