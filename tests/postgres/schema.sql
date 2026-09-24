-- Disposable local test schema: exact README chats/route_segments/steps DDL
-- plus backend/app/crud/memory_crud.py chat_memory DDL. Not a production migration.
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
    user_id     TEXT        NOT NULL,
    chat_id     TEXT        NOT NULL DEFAULT '',
    mem_type    TEXT        NOT NULL,
    mem_key     TEXT        NOT NULL,
    mem_value   JSONB       NOT NULL,
    confidence  REAL        DEFAULT 1.0,
    updated_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, chat_id, mem_type, mem_key)
);
