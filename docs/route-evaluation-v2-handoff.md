# Evaluation v2: catalog-owner exchange and readiness

PR41 owns evaluation code. Integration was inspected against catalog PR40 at
`b0ddee3b8321a8e135bbe2079bbfde46ac96812d`: `git merge-tree` combined it cleanly
without changing either branch or the checkout. This branch remains based on
`5ab14e0`; no silent rebase or catalog merge was performed. Catalog modules, SQL, ingestion, active pointers and
production activation remain unchanged. The exchange below is additive and local;
no new database-side adapter is assumed. Attempts to message the parent cloud
thread from this Mac returned “thread not found”; this file records the exact
interface for coordination without altering the catalog owner's work.

## Source boundary

The reported catalog checkpoint is 400 locally imported records, with 331
current-access reviews pending. Import count is not usable corridor coverage.
Never include pending, rejected, missing, expired or coordinate-mismatched reviews
in primary fixtures. No uncommitted expansion was recreated or consumed here.

The owner provides a local `catalog-export.json` matching
`backend/tests/fixtures/route_evaluation/v1/catalog-export.schema.json`: version 1,
`evidence_type: catalog_owner_export`, exact `catalog_generation`,
`catalog_release`, `attribution`, and `records` using existing provider facts
(`provider_id`, original name, [lat, lon], source release/attribution/provenance,
optional address/URL/categories/provider rank). For mixed generations, copy the
existing `source_catalogs` map (`source` → `{release, attribution}`) unchanged.
Global generation/release and rights approval bind the whole snapshot; records
retain their leaf source's release and attribution. Unknown or mismatched leaf
sources are rejected rather than flattened. Per-record duplicate-source credits
in `source_provenance[].source_attribution` are retained in the same combined
attribution order used by the current catalog adapter. This does not require production
activation. A reviewed versioned local export supports offline work only.

Provide separate `access_reviews.json` and `rights.json` using their committed
schemas. A review binds provider ID and exact arrival coordinates to generation
and release; it supplies `status: eligible`, `arrival_eligible: true`, an aware
`reviewed_at`, `valid_through`, named reviewer and nonempty `{uri, sha256}`
evidence references. Pending/ineligible records can remain in the source ledger
but are excluded by `export-reviewed`. Review validity must cover the requested
trip horizon and each observed attraction arrival. Rights evidence explicitly
approves evaluation use, with matching generation/release/attribution, reviewer,
aware review time and hashed license references. These are supplied attestations
and evidence references, not independent legal or availability verification.

## No-call preparation commands

Run from `backend/`; all inputs are local. Outputs must be new paths.

```sh
.venv/bin/python -m app.routing.evaluation export-reviewed --catalog catalog-export.json --reviews access_reviews.json --rights rights.json --clock 2026-10-16T00:00:00+00:00 --departure 2026-10-17T08:00:00-07:00 --output approved-export.json
.venv/bin/python -m app.routing.evaluation sample --export approved-export.json --baseline baseline-route.json --count 100 --seed 1729 --output medium-sample.json
.venv/bin/python -m app.routing.evaluation assemble --capture-directory existing-captures --sample medium-sample.json --output fixtures/medium-2d
.venv/bin/python -m app.routing.evaluation freeze-shortlists --fixture fixtures/medium-2d --output frozen-fixtures/medium-2d
```

`export-reviewed` filters access failures, retains explicit exclusion reasons and
hashes the owner's source, ledger and rights bytes. `sample` uses a measured
baseline, a declared five-mile corridor, deterministic section/category quotas
and seed-based ordering, without persona scoring. Fewer than 100 produce
`insufficient_real_fixture_coverage` and the actual count, never padding.
`assemble` selects already-existing captured evidence; it generates no ratings,
quotes, road measurements or approvals. `freeze-shortlists` runs actual adaptive
discovery and recorded solo-road checking against that immutable source, freezing
at most 60 IDs for each matching persona/density scenario in a new fixture.

## Real capture schema

`manifest.schema.json` now describes **real v2 manifests**. The root directory
remains named v1 for the original scenario matrix; it does not imply a v1 real
capture is accepted. `unit-manifest.schema.json` covers explicit synthetic tests.

Real manifests require schema version 2, one of:

- `catalog_selection_with_captured_measurements` + `selection_only`;
- `catalog_recorded_pipeline` + `recorded_pipeline`.

The manifest hashes `data.json`, `access_review_file`, `rights_evidence` and any
additional JSON evidence files. Every hashed file is parsed as strict finite
JSON. Raw license/PDF bytes should be referenced with their hashes inside rights
JSON; do not list binary/text license files as JSON manifest entries.

`rating_capture` and optional `hotel_rating_capture` are strict typed objects:
`capture_id`, `model`, `prompt_hash`, `configuration`, aware `captured_at`.
`routing_capture` requires `capture_id`, `provider`, `profile`, aware
`departure_context` and `captured_at`. Capture times cannot exceed the frozen
evaluation clock; routing departure context must equal the scenario departure.

`data.json` retains the original route/node/attraction contract, with these
required bindings for real data:

- Attraction `source_generation`, source release/attribution/provenance,
  `rating_capture_id`, nonempty typed `evidence_references`, all 14 fixed ratings,
  progress and measured solo detour. Original names can repeat: the offline
  ratings adapter resolves by stable internal IDs and restores original names.
- Every recorded road response references the manifest's road `capture_id`.
  Include the exact direct baseline request/response and every solo route.
  `route_key(request_coordinates)` hashes exact ordered [lat, lon] values; use
  floating-point coordinates consistently. Mapbox geometry remains [lon, lat].
  Actual final multi-waypoint responses, with one leg per adjacent request pair,
  are mandatory for pipeline results; matrices never replace reroutes.
- Hotels require complete fixed attribute ratings plus the hotel rating capture
  ID. Utility is recomputed per persona. Dated room allocations/individual USD
  quotes retain the existing production price scopes and taxes/fees evidence.
- Named node timezones and exact intermediate lookup positions are required.
  Missing real lookups fail; only explicitly synthetic tests can use a fixed zone.
- Optional paired duration/distance matrices remain directed, aligned to node
  order, with zero diagonals and corresponding unreachable nulls.

The selector's 100 records are usable real places before persona eligibility;
not every place must exceed utility 0.60. Threshold underfulfillment remains a
measured outcome. Production discovery/selection capacity stays at 60. All actual
Directions requests count hotels and endpoints toward 25 coordinates.

## Implemented versus blocked

Implemented: strict reviewed/provenance gates; read-only export/sample/assembly/
shortlist tools; per-persona hotel scoring; duplicate-name-safe frozen ratings;
successful/fulfilled/timing-valid quality conditioning; failure denominators;
visible and machine-readable figure provenance; parameter response plots,
paired physical deltas/ID changes and identical-model bounds; workload screening;
7/10-day coast diagnostic inputs; visit/overnight and resource measurements;
separately recorded warmups; page-scoped Lab comparison charts. No public replay,
fixture-run endpoint or experimental production algorithm was added.

Workload screening deliberately uses generous UTC active-window envelopes and a
provider driving estimate. It is not a proof of global infeasibility. The default
20-attraction limit leaves 21/30-stop diagnostic inputs unsupported; those rows
remain explicit rather than silently shrinking trips. The optional configured
limit can be raised only within the existing 30 hard ceiling; 25-coordinate
transport checks still apply.

Data-blocked: 100 reviewed eligible places in each of four distinct corridors;
frozen rights/review evidence; captured ratings/direct/solo/final roads, dated
hotels and timezone lookups; real calculated campaigns and primary figures.
Separate live acceptance requires approved provider/count/spending scope and
browser/history verification. No new paid calls or production writes were made.
No plan-scoped independent framework work is deliberately deferred; future
changes to the actual planner's trip-day/budget optimization remain a separate
product decision, as the approved plan specifies.
