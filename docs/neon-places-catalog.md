# Neon places catalog: staged rollout

Status on October 14, 2026: implementation validated with synthetic local data;
**no real source downloaded, no production DDL applied, no Neon catalog loaded**.
Do not deploy this revision until the schema, activated catalog and real coverage
have passed the gates below. `/ready` requires a nonempty active generation.
This work keeps the database on Neon; EC2 migration is paused.

## Sources and coverage

Overture Places release `2026-09-23.1` is the pinned primary input. See the
[official places guide](https://docs.overturemaps.org/guides/places/) and
[attribution requirements](https://docs.overturemaps.org/attribution/).
The importer accepts documented upstream provenance: Meta, Microsoft, PinMeTo,
Krick, RenderSEO, DAC and BrightQuery under CDLA-Permissive-2.0; Foursquare under
Apache-2.0 with its full NOTICE; AllThePlaces under CC0-1.0. An Overture wrapper
alone does not establish upstream permission. Unknown sources are rejected.
License texts and the Foursquare notice are served at `/licenses/`, linked from
`/catalog-attribution.html`, and hashed into import manifests. Changes to source
licenses require review before updating the allowlist.

US records must have an explicit state/DC region and country, finite WGS84
coordinates, supported categories and usable provenance. Alaska and Hawaii are
included; territories and ambiguous jurisdictions are excluded. Current category
mapping uses `basic_category` and taxonomy, with legacy category compatibility.
Restaurants support evening suggestions; daytime uses attractions/culture.
Closed or uncertain operating-status records are excluded. Generic parks,
reserves, landmarks and natural features are excluded without a specific
visitor-center, trailhead, viewpoint or scenic-lookout category. These categories
still do not prove road access: validate practical arrival locations during
coverage review. Do not turn national-park centroids into driving stops.

No hours, ratings, live availability or entrance verification are invented.
Source evidence dates are not guarantees that a venue remains open. Attribution
and source/release metadata travel through the API, itineraries and Studio.
Historical itineraries without metadata remain readable. Hotel and travel-time
providers retain their existing roles.

Nationwide coverage remains a goal, not a result. Before rollout, record counts
by state/category, sampled coordinate/access accuracy, duplicates and omissions;
exercise urban, rural, interstate, Alaska and Hawaii routes and evening fallback.
A bounded city pilot is insufficient for nationwide activation. Kaggle is an
explicit additional requirement; see [source review](catalog-source-review.md).
The requested next step is a balanced initial batch of roughly 500 unique
destinations, not a national bulk import; see [pilot scope and acceptance](catalog-pilot-plan.md).

The current extractor, manifest validator, normalizer and discovery identity are
Overture-specific. They do **not** yet ingest arbitrary Kaggle CSVs. An authentic
Kaggle archive must first be inspected and cleared, then receive an explicit
reviewed adapter and provenance/identity handling. Do not relabel Kaggle records
as Overture, add a blanket Kaggle license allowlist, or bypass the existing
natural-area access-point guard to make a batch pass.

## Bounded extraction and isolated validation

Install optional extraction dependencies separately from the application:

```sh
/workspace/roadtrips-venv/bin/pip install -r scripts/requirements-catalog.txt
PYTHONPATH=backend /workspace/roadtrips-venv/bin/python scripts/extract_overture_places.py \
  --bbox=-122.52,37.70,-122.35,37.82 --region-label sf-pilot \
  --output /workspace/catalog-data/sf-pilot.jsonl
PYTHONPATH=backend /workspace/roadtrips-venv/bin/python scripts/catalog_import.py \
  --input /workspace/catalog-data/sf-pilot.jsonl \
  --manifest /workspace/catalog-data/sf-pilot.jsonl.manifest.json
```

The example is a pilot, not a selected rollout region. Default extraction limits
are 500 accepted records, 10,000 inspected records, 20 MiB decoded records and
120 seconds checked between records. Network calls have separate timeouts;
Parquet transfer overhead is not included in decoded-byte accounting. Bounding
boxes are at most four square degrees; split antimeridian areas explicitly.
Truncation is recorded and must not be reported as complete coverage. Output and
manifest publication refuses existing files. Preserve original artifacts and
checksums outside Git. Never commit data archives or credentials.

Using an explicitly injected disposable PostgreSQL 18 `DATABASE_URL`, run
`catalog_import.py --apply-schema`, then the same dry-run arguments with
`--stage`, then `--activate GENERATION` using the returned generation. The default
`--target local` rejects remote databases and `neondb`. `--target neon` is an
explicit separate target and requires existing Neon credentials, PostgreSQL 18
and verified TLS. Do not put credentials in shell arguments or logs.

Importer ceilings are 50,000 rows and 100 MiB per artifact; default CLI pilot
limits remain 500 rows/20 MiB. Staging uses batches of at most 500, validates
checksums and license evidence, rejects immutable-generation conflicts, and
checks indexed catalog size against 256 MiB and database size against 512 MiB.
These are admission guards, not Neon quota guarantees: failed transactions can
leave reclaimable disk pages and branch/history usage differs from database size.
Measure authentic pilot footprint and compute before enlarging an import.

To combine regional artifacts, include **every region to retain**:

```sh
PYTHONPATH=backend python scripts/catalog_combine.py \
  /workspace/catalog-data/region-a.jsonl /workspace/catalog-data/region-b.jsonl \
  --output /workspace/catalog-data/us-generation.jsonl
```

This creates a complete replacement generation, not an append. It requires
matching releases/schema, verifies each input, deduplicates exact normalized IDs
and rejects conflicts. Retain the combined manifest and original manifests.

## Production gates and rollback

1. Resolve ordinary source-download access, review Kaggle rights and actual
   schema, download the bounded authentic pilot and validate it locally. Record
   checksums, licenses, counts, rejects, footprint and route coverage.
2. Validate backup/restore on a separate local database, including source IDs,
   normalized content and active-generation pointer. Synthetic recovery evidence
   is recorded in [validation](catalog-validation.md); repeat for authentic data.
3. Coordinate release timing with the lead. Confirm current Neon storage and
   compute allowance, existing production recovery path and a tested pre-change
   backup with authorized access. No paid upgrades or credential changes are
   included. Copying private user data to any new destination requires its own
   authorization; catalog checks need only permitted public data.
4. Apply the additive `backend/sql/places_catalog.sql` explicitly to Neon using
   existing authorized access. Stage the verified generation without activation;
   verify exact counts, source-ID/content checks, indexes and measured footprint.
   No application request performs DDL or downloads source datasets.
5. Activate the generation atomically; retain the returned previous generation.
   Deploy only after approval and real coverage validation, then test readiness,
   chat, Studio, route maps, attribution, evening choices and failure behavior.
   Local fixture tests do not establish those live journeys.
6. On catalog regression, reactivate the recorded previous generation. For a
   first activation or application regression, roll back to the retained prior
   application release and its configuration. Keep original Neon user tables,
   previous catalog generations and source archives; do not drop the database or
   overwrite it with a whole-database restore. Plan retention cleanup separately.

At the October 14 metadata check, Neon had approximately 44 MiB branch logical
size and 84.82 of the supplied 100 monthly CU-hours consumed, ending November 1
UTC. These are historical observations, not capacity reservations. Background
readiness polling may consume compute; this catalog change does not establish
that polling has been addressed. No billing or infrastructure changes were made.
