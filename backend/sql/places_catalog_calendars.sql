-- Additive companion migration. Apply before the enrichment-aware API release.
-- Separately attributed facts: original source rows/provenance stay immutable.
CREATE TABLE IF NOT EXISTS places_catalog_calendars (
    generation text NOT NULL,
    source_id text NOT NULL,
    entry jsonb NOT NULL CHECK (jsonb_typeof(entry) = 'object'),
    PRIMARY KEY (generation, source_id),
    FOREIGN KEY (generation, source_id) REFERENCES places_catalog(generation, source_id),
    CHECK (entry->>'source_id' IS NOT NULL AND entry->>'source_id' = source_id),
    CHECK (entry->'source_visit_calendar'->>'schema_version' IS NOT NULL AND entry->'source_visit_calendar'->>'schema_version' = 'roadtrips-source-visit-calendar/1')
);
