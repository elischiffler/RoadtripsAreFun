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

-- Additive migration. Apply explicitly to the approved database before deploying the Lab.
CREATE TABLE IF NOT EXISTS algorithm_lab_runs (
    id uuid PRIMARY KEY,
    user_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed')),
    mode text NOT NULL CHECK (mode IN ('live','replay')),
    preset_id text NOT NULL,
    run_type text NOT NULL CHECK (run_type IN ('interactive','benchmark')),
    batch_id uuid,
    repeat_index integer NOT NULL DEFAULT 1 CHECK (repeat_index BETWEEN 1 AND 10),
    input jsonb NOT NULL,
    metrics jsonb,
    error_code text,
    result jsonb
);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_owner_time ON algorithm_lab_runs (user_id, started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_batch ON algorithm_lab_runs (user_id, batch_id);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_comparison ON algorithm_lab_runs (user_id, (metrics->>'comparison_key'));
