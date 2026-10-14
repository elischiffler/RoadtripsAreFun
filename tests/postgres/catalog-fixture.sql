-- Explicit synthetic readiness fixture for the disposable CRUD/recovery gate only.
-- Not an import manifest or licensed source record. Never apply to production.
BEGIN;
INSERT INTO places_catalog_imports(generation, release, manifest, row_count)
VALUES ('disposable-synthetic', 'synthetic-test', '{"synthetic":true,"attribution":"Synthetic test data"}', 1);
INSERT INTO places_catalog(generation, source_id, name, latitude, longitude, region, categories, provenance)
VALUES ('disposable-synthetic', 'synthetic-museum', 'Synthetic Museum', 37.8, -122.4, 'CA', ARRAY['museum','culture','daytime'], '[{"dataset":"synthetic"}]');
INSERT INTO places_catalog_active(singleton, generation) VALUES (true, 'disposable-synthetic');
COMMIT;
