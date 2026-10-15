-- Additive only. No application/user tables are modified.
CREATE TABLE IF NOT EXISTS places_catalog_imports (
    generation text PRIMARY KEY,
    release text NOT NULL,
    manifest jsonb NOT NULL,
    row_count integer NOT NULL CHECK (row_count >= 0),
    imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS places_catalog (
    generation text NOT NULL REFERENCES places_catalog_imports(generation),
    source_id text NOT NULL,
    name text NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    region text NOT NULL,
    categories text[] NOT NULL,
    address text,
    url text,
    source_updated_at text,
    provenance jsonb NOT NULL,
    PRIMARY KEY (generation, source_id)
);
CREATE INDEX IF NOT EXISTS places_catalog_bbox ON places_catalog (generation, latitude, longitude);
CREATE INDEX IF NOT EXISTS places_catalog_categories ON places_catalog USING gin (categories);
CREATE TABLE IF NOT EXISTS places_catalog_active (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    generation text NOT NULL REFERENCES places_catalog_imports(generation)
);
