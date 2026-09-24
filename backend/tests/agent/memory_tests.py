"""Unit tests for the agent memory layer (design §4, Stream B).

These exercise the *pure* logic that doesn't need Postgres:
- MemoryFact / ConversationMemory round-trip via model_dump / model_validate
- MemoryCrudStore satisfies the runtime_checkable MemoryStore Protocol
- extract_facts_from_turn returns a list
- load / upsert / save semantics against the shared ``FakeMemory`` fake
  (defined in ``tests/agent/conftest.py`` by Stream A — reused here as the
  injectable in-memory MemoryStore)

The DB-touching functions in ``memory_crud`` (module-level ``load_facts`` /
``upsert_facts`` / ``load_conversation`` / ``save_conversation``) need Neon and
are not exercised at the unit level, but are structured so they'd work.
"""

from datetime import UTC, datetime, timedelta

from app.agent.memory import ConversationMemory, MemoryFact, MemoryStore
from app.crud.memory_crud import MemoryCrudStore, extract_facts_from_turn

from .conftest import FakeMemory


def _fact(key: str, value: str, confidence: float = 1.0, when: datetime = None) -> MemoryFact:
    """Build a MemoryFact — ``updated_at`` is required in the shared model."""
    return MemoryFact(
        key=key,
        value=value,
        confidence=confidence,
        updated_at=when or datetime.now(UTC),
    )


# --- Model round-trips ------------------------------------------------------


def test_memory_fact_round_trip():
    fact = MemoryFact(
        key="home_city",
        value="Boston, MA",
        confidence=0.9,
        source_chat_id="42",
        updated_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    restored = MemoryFact.model_validate(fact.model_dump())
    assert restored == fact


def test_memory_fact_json_round_trip():
    fact = _fact("pref.likes", "national parks")
    # mode="json" is how the CRUD layer serializes into JSONB
    restored = MemoryFact.model_validate(fact.model_dump(mode="json"))
    assert restored.key == "pref.likes"
    assert restored.value == "national parks"


def test_memory_fact_optional_defaults():
    fact = _fact("pref.likes", "national parks")
    assert fact.confidence == 1.0
    assert fact.source_chat_id is None


def test_conversation_memory_round_trip():
    mem = ConversationMemory(
        chat_id="42",
        summary="User wants a frugal national-parks trip.",
        summary_turn_count=6,
        updated_at=datetime(2025, 6, 1, tzinfo=UTC),
    )
    restored = ConversationMemory.model_validate(mem.model_dump())
    assert restored == mem


def test_conversation_memory_optional_defaults():
    mem = ConversationMemory(chat_id="7", updated_at=datetime.now(UTC))
    assert mem.summary == ""
    assert mem.summary_turn_count == 0


# --- Protocol conformance ---------------------------------------------------


def test_crud_store_satisfies_protocol():
    assert isinstance(MemoryCrudStore(), MemoryStore)


def test_fake_memory_satisfies_protocol():
    assert isinstance(FakeMemory(), MemoryStore)


# --- Fact extraction stub ---------------------------------------------------


def test_extract_facts_returns_list():
    result = extract_facts_from_turn("I live in Boston", "Got it, Boston noted.")
    assert isinstance(result, list)
    assert result == []


# --- FakeMemory store semantics ---------------------------------------------


def test_upsert_and_load_facts(fake_memory):
    assert fake_memory.load_facts("u1") == []
    fact = _fact("home_city", "Boston, MA")
    fake_memory.upsert_facts("u1", [fact])
    facts = fake_memory.load_facts("u1")
    assert any(f.value == "Boston, MA" for f in facts)


def test_facts_are_scoped_by_user(fake_memory):
    fake_memory.upsert_facts("u1", [_fact("home_city", "Boston, MA")])
    assert fake_memory.load_facts("u2") == []


def test_load_conversation_empty_default(fake_memory):
    mem = fake_memory.load_conversation("u1", "99")
    assert isinstance(mem, ConversationMemory)
    assert mem.chat_id == "99"
    assert mem.summary == ""


def test_save_and_load_conversation(fake_memory):
    mem = ConversationMemory(
        chat_id="42",
        summary="rolling summary",
        summary_turn_count=4,
        updated_at=datetime.now(UTC),
    )
    fake_memory.save_conversation("u1", "42", mem)
    loaded = fake_memory.load_conversation("u1", "42")
    assert loaded.summary == "rolling summary"
    assert loaded.summary_turn_count == 4


def test_conversation_scoped_by_chat(fake_memory):
    fake_memory.save_conversation(
        "u1",
        "42",
        ConversationMemory(chat_id="42", summary="a", updated_at=datetime.now(UTC)),
    )
    other = fake_memory.load_conversation("u1", "43")
    assert other.summary == ""


# Keep timedelta import meaningful for future ordering tests without over-asserting
def test_fact_timestamps_are_comparable():
    older = _fact("k", "v1", when=datetime(2025, 1, 1, tzinfo=UTC))
    newer = _fact("k", "v2", when=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=1))
    assert newer.updated_at > older.updated_at
