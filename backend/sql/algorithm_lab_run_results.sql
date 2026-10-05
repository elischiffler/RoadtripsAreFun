-- Additive migration for saved maps/itineraries. Apply after algorithm_lab_runs.sql.
-- Existing historical records remain readable without trip artifacts.
ALTER TABLE algorithm_lab_runs ADD COLUMN IF NOT EXISTS result jsonb;
