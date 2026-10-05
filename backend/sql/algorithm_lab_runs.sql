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
    error_code text
);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_owner_time ON algorithm_lab_runs (user_id, started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_batch ON algorithm_lab_runs (user_id, batch_id);
CREATE INDEX IF NOT EXISTS algorithm_lab_runs_comparison ON algorithm_lab_runs (user_id, (metrics->>'comparison_key'));
