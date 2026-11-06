-- Explicit additive migration. Estimated traits are separate from immutable source facts.
CREATE TABLE IF NOT EXISTS place_attribute_traits (
    cache_key text PRIMARY KEY CHECK (length(cache_key) = 64),
    source_id text NOT NULL,
    rating_version text NOT NULL,
    place_context jsonb NOT NULL,
    attribute_ratings jsonb NOT NULL CHECK (jsonb_typeof(attribute_ratings) = 'object'),
    provider text NOT NULL,
    rated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '90 days')
);
CREATE INDEX IF NOT EXISTS place_attribute_traits_source ON place_attribute_traits(source_id);
