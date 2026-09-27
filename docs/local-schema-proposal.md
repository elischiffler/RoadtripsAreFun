# Roadtrips local PostgreSQL schema proposal

**Status: applied only to disposable local test volumes; not a production migration.** This is the schema supported by the checked-in code. It is not a claim about the live Neon database, which was not inspected or contacted. Do not apply this to production or an existing persistent application volume until the table definitions, existing data, and migration path are reviewed.

The first three tables and indexes come from the repository's [Database Schema](../README.md#database-schema). Their columns and conflict keys match the SQL in [`chat_crud.py`](../backend/app/crud/chat_crud.py). `chat_memory` comes from the exact lazy-create SQL and upsert conflict key in [`memory_crud.py`](../backend/app/crud/memory_crud.py).

```sql
CREATE TABLE IF NOT EXISTS chats (
  user_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  chat_data JSONB,
  chat_log JSONB,
  PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS route_segments (
  user_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  route_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  coords JSONB,
  PRIMARY KEY (route_id, segment_id)
);

CREATE TABLE IF NOT EXISTS steps (
  user_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  leg_id TEXT NOT NULL,
  step_id INTEGER NOT NULL,
  coordinates JSONB,
  PRIMARY KEY (leg_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_route_segments_route_id ON route_segments(route_id);
CREATE INDEX IF NOT EXISTS idx_steps_leg_id ON steps(leg_id);

CREATE TABLE IF NOT EXISTS chat_memory (
  user_id TEXT NOT NULL,
  chat_id TEXT NOT NULL DEFAULT '',
  mem_type TEXT NOT NULL,
  mem_key TEXT NOT NULL,
  mem_value JSONB NOT NULL,
  confidence REAL DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, chat_id, mem_type, mem_key)
);
```

The code uses `chats(user_id, chat_id)`, `route_segments(route_id, segment_id)`, `steps(leg_id, step_id)`, and `chat_memory(user_id, chat_id, mem_type, mem_key)` as `ON CONFLICT` targets. `memory_crud.py` creates its table lazily; the other tables have no checked-in migration. `chat_memory` stores cross-chat facts under the empty-string `chat_id` sentinel, and per-chat summary/trip rows under their actual chat ID. [`tests/postgres/schema.sql`](../tests/postgres/schema.sql) is the executable transcription used solely by the isolated local test stack. Its successful CRUD test establishes that these definitions support checked-in queries; it does not establish live-schema compatibility.

Before production provisioning, review the route and leg identifier scope: `chat_crud.py` derives `route_id` from user and chat IDs. This branch adds verified user/chat predicates to segment and step reads and rejects conflicting writes owned by another chat, but the proposed primary keys still omit those owner columns. The repository has no foreign keys or cleanup of route segments, steps, and memory when a chat is deleted. Those schema and lifecycle decisions need a separate migration/design review before changing keys or adding constraints. A clean local database tests this proposal; it cannot validate the shape or contents of production data.
