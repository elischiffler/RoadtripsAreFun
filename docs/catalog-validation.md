# Catalog validation — October 14, 2026

Implementation evidence for issue #36; production rollout remains blocked.
All database tests and benchmarks used synthetic disposable local data.
No real Overture or Kaggle archive was imported; Neon remains unchanged.

## Fresh saved-environment recheck

At approximately 22:42 UTC on October 14, the saved checkout was recovered from
base `56ac6dbd3eccbd03e105385cf5561582376c0b17` onto the existing
`codex/neon-places-catalog` branch. GitHub and `git ls-remote` both confirmed
draft PR #40 at `23fd423c235e88229fa1aec6f5a31aa3a2a1f247`; all implementation
changes were preserved. `AGENTS.md` and its steering map were read. The workspace
`.agents` directory was empty; the repository had no `.agents` directory.

`KAGGLE_API_TOKEN` was present in the fresh process. A single Python urllib
request used that existing token in an Authorization header for the small pinned
candidate archive:

`https://www.kaggle.com/api/v1/datasets/download/paultimothymooney/trailstrailheadsandrockformationsinboulder?datasetVersionNumber=1`

The request had a 30-second timeout and a 5 MiB read ceiling. It failed with
`URLError: Tunnel connection failed: 403 Forbidden`, before contacting Kaggle.
No archive or dataset bytes were received; no credential value was printed or
written. Token validity, dataset availability, archive size and schema therefore
remain untested. No alternate host, proxy change, elevation, or alternate download
transport was used after the denial. This is a network blocker, not evidence of
bad Kaggle credentials. The pinned version is an attempted probe, not a verified
dataset release.

Independent checks:

- Catalog unit/extraction/combination tests: **60 passed, four PostgreSQL tests
  skipped** because `CATALOG_TEST_DATABASE_URL` was not configured. This recheck
  does not claim a new local PostgreSQL, container, or whole-suite run.
- GitHub Actions for the implementation commit above: [Backend CI](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/38647990169),
  [Frontend CI](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/38647990174),
  [Local containers](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/38647990157)
  and [Disposable PostgreSQL CRUD](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/38647990198)
  all completed successfully. Vercel and CodeRabbit statuses also reported success.
- Neon project metadata: PostgreSQL 18, Free plan, 1 GiB branch logical-size
  ceiling, production branch `br-noisy-forest-aqidrq92`, 46,145,536 logical bytes
  (44.01 MiB). Project-reported compute time was 306,256 seconds (85.07 CU-hours)
  for October 1–November 1 UTC. This is a consumption snapshot, not remaining
  capacity promised to the pilot.
- One read-only Neon query returned server version `180006`, database size
  22,134,784 bytes (21.11 MiB), and `NULL` for all three catalog table names.
  Branch logical storage and `pg_database_size` measure different things. No
  private application rows were read. No Neon schema, catalog, pointer, billing,
  credentials or deployment configuration was changed.

Authentic acquired/accepted/staged/activated places: **0 / 0 / 0 / 0**. Every
requested category and geography remains a coverage gap. No live chat, Studio,
route, evening, saved-history or browser-reload journey was validated against
Neon catalog data. The [pilot plan](catalog-pilot-plan.md) records the requested
variety and the remaining Kaggle adapter work; it is not a fabricated batch.

## Passed checks

- Backend: **813 tests, 88.12% coverage**, above the unchanged 63% floor.
- Backend Ruff format/lint pass from `backend/`; catalog/cloud scripts pass
  using the backend Ruff configuration.
- Frontend: 314 tests in 39 files, 90.21% line/statement and 83.67% branch
  coverage. Format, lint and production build pass. Vite's large-chunk warning
  remains; thresholds were not relaxed.
- Catalog subset: 64 tests including four real PostgreSQL tests. Coverage includes
  malformed coordinates, taxonomy, permissions evidence, checksums, import limits,
  generation conflicts, antimeridian lookup, complete-generation combination,
  rejected natural-area centroids, extraction bounds and activation rollback.
- Container preview smoke: 2/2 pass using offline-built images.
- Disposable PostgreSQL: CRUD/ownership, API restart, readiness loss/recovery,
  database recreation, backup/restore, populated-target refusal and catalog
  activation-pointer restoration pass. Earlier archive: 16,316 bytes. Volumes
  and backups retained; no production data used.

Normal online Docker dependency builds were blocked by nested DNS/proxy CA
behavior. Offline builds preserve verified HTTPS while preparing locked caches;
see [cloud workflow](cloud-development.md). A later container rerun initially
exhausted workspace disk; unused build cache/dangling image cleanup restored
9.8 GiB without deleting database volumes or backups. This is a disposable
workspace issue, not evidence about EC2 or Neon capacity.

## Synthetic capacity and recovery

50,000 synthetic records occupied 50,429,952 indexed bytes (48.1 MiB,
1,008.6 bytes/row); two equivalent retained generations project to 96.2 MiB.
A dense indexed query with 2,087 matches and a 60-row limit took 4.012 ms;
a sparse query took approximately 0.03 ms. These are not authentic-source
footprint, nationwide coverage or Neon latency measurements.

A 1,108,132-byte synthetic dump had SHA-256
`5bf46f5688115b52b0db476205812a72f5abd72fe176ae186a7faee696db12ee`.
A separate restore database matched all 50,000 rows, normalized-content digest
`15b8decf69935e59fa0d7fad13af6d79`, and the active pointer. The fixture,
benchmark scripts, query plans, logs and archive remain outside Git under
`/workspace/catalog-validation/`. Repeat recovery validation for authentic data;
this does not substitute for a pre-production backup.

## Outstanding gates

The cloud proxy returned CONNECT 403 for Overture STAC, public S3/Azure storage,
and Kaggle public API/archive URLs. An authorized elevated read still met that
restriction. No bypass or credential/network/billing change was attempted.
Direct PostgreSQL connection to Neon was unavailable; its read-only connector
worked. No production DDL or data mutation was attempted.

Permit ordinary public download access to `stac.overturemaps.org`,
`overturemaps-us-west-2.s3.us-west-2.amazonaws.com` and Kaggle's API plus its actual
public download redirect host, or supply original licensed archives with metadata
and license evidence in the workspace. The user handles authentication or explicit
terms acceptance if required. Kaggle rights and access-point quality still need
review; see [source assessment](catalog-source-review.md).

Then run an authentic bounded pilot, measure storage/compute, validate restore,
expand and quantify coverage, and test live chat/Studio/route journeys. Keep the
PR in draft until those gates and release coordination are complete. Follow the
[rollout/rollback runbook](neon-places-catalog.md); do not infer production
readiness from synthetic tests.
