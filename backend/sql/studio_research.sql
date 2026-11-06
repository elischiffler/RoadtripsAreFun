-- Additive research-results mirror. Apply explicitly; application startup never runs DDL.
-- Local SQLite remains the execution queue. No visitor identity or control keys are copied.
CREATE TABLE IF NOT EXISTS studio_research_studies (
    id uuid PRIMARY KEY,
    snapshot jsonb NOT NULL,
    protocol jsonb NOT NULL,
    synced_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS studio_research_runs (
    study_id uuid NOT NULL REFERENCES studio_research_studies(id),
    case_id integer NOT NULL,
    state text NOT NULL,
    spec jsonb NOT NULL,
    result jsonb,
    solver_status text,
    revision bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (study_id, case_id)
);
CREATE INDEX IF NOT EXISTS studio_research_runs_changes
    ON studio_research_runs (study_id, revision);
CREATE INDEX IF NOT EXISTS studio_research_runs_outcomes
    ON studio_research_runs (study_id, solver_status);
