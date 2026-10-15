# Route evaluation

The evaluator runs locally with frozen evidence. It makes no provider calls and
writes no database rows. The public Lab/Studio APIs remain live-only, with their
existing owner/visitor authentication and replay rejection.

Implemented against catalog PR 40 at `5ab14e01e0ababd3525093ff67fac7ac29d2bd6f`.
The approved Library plan was materialized on the Mac, verified readable at
67,165 bytes, SHA-256
`e014b9ddc9c509b77463710493056ae8f12f3218b7ec66d608ed2a196024b273`.

## Scenario and input contract

`backend/tests/fixtures/route_evaluation/v1/scenarios.json` contains 30 concrete
inputs: five trip types × nature/entertainment × one/two/three attractions per
requested day. Corridors are LA–San Diego (one day), SF–Boise (two), SF–Denver
(three), SF–New York (five), and the paired $60 SF–Boise trip. Medium/tight inputs
change only the nightly room target. Both personas include all 14 canonical keys.
Two adults share one room; evenings are empty. Dates and evaluation clock are
fixed, with origin-local departure at 08:00 on October 17, 2026. Scenario targets
remain evaluation fields, separate from `LabInputs`; the solver does not constrain
trip days or attractions per day.

`MAX_TRIP_ATTRACTIONS` defaults to 20 and must be an integer in 1–30. Chat,
updates, tool schemas, direct HTTP input, Lab and Studio share it. The UI consumes
the server-advertised limit. Public normal trips require at least one attraction;
internal `PlanOptions` tests still exercise zero-stop scheduling. Existing saved
valid trips remain readable. Changing the configured limit requires a process
restart and does not change the production candidate capacity of 60.

Directions permits 25 coordinates including both endpoints and every hotel and
attraction. Every call checks the actual count before provider work. Trips that
exceed this transport capacity receive an explicit 422; no silent truncation or
unverified stitching is performed. At 20 attractions, at most three hotel nodes
fit in one Directions request. The evaluation records this capability separately
from the attraction-count bound.

## Commands

From `backend/`, using the pinned Python 3.12 environment:

```sh
.venv/bin/python -m app.routing.evaluation scenarios --output tests/fixtures/route_evaluation/v1/scenarios.json
.venv/bin/python -m app.routing.evaluation validate --fixtures tests/fixtures/route_evaluation/v1
.venv/bin/python -m app.routing.evaluation run --track selection-100 --suite weekend-v1 --output ../results/route-evaluation/weekend-100
.venv/bin/python -m app.routing.evaluation run --track production-shortlist --suite core-v1 --output ../results/route-evaluation/parity
.venv/bin/python -m app.routing.evaluation run --track offline-pipeline --suite core-v1 --output ../results/route-evaluation/pipeline
.venv/bin/python -m app.routing.evaluation report --input ../results/route-evaluation/pipeline
```

Each output directory must be new/empty. Campaign manifests freeze all expected
rows before execution. Cells execute serially in separate Python processes with
a default 120-second whole-run deadline. Terminated workers receive a harness
failure and an unobserved solver status; timeout is never labeled infeasibility.
Result writes use fsync and atomic replacement. Output includes `manifest.json`,
`runs.jsonl`, `failures.jsonl`, `summary.csv`, `plot-data.json`, `report.md`, and
available route/itinerary JSON artifacts. Reports also show missing campaign rows.

Use `--scenario EXACT-ID` repeatedly for a selected slice. `weekend-v1` selects
the medium corridor at two attractions/day with both personas. `--sweep` runs one
factor at a time on a frozen selection pool:

- `quality_loss`: 0, 0.05, 0.10, 0.20.
- `utility_threshold`: 0.50, 0.60, 0.70.
- `detour_weight`: 0, 0.25, 1, 4, keeping spacing weight 1.
- `time_limit_seconds`: 0.25, 1, 5, 15.
- `persona_interpolation`: nature to entertainment at 0, 0.25, 0.50, 0.75, 1.
- `budget`: $60, $120, $180, $240, only in the medium full-pipeline track.

`--methods cp_sat utility_first spacing_first` compares offline methods under
the same count, eligibility, integer quality bound, source data, scheduler and
final road evidence. The spacing heuristic has a bounded deterministic utility
repair; failure to satisfy the bound is a method failure. Comparators use
`NOT_APPLICABLE` solver status and remain outside the production registry.

`--seed 0|1|2`, `--repeat 1..10`, `--workers 1..8`, and `--time-limit` (at most 60 seconds) support bounded search repeats and reference solves.

Selection uses the shared CP-SAT model. Production defaults remain 60 candidates,
0.60 eligibility, 0.10 average loss, spacing/detour coefficients 1/1, five seconds,
one worker and seed 0. Only the offline 100 track raises the candidate guard.
Rational coefficients retain their explicit integer conversion. The original
floor/ceiling utility rounding is preserved; diagnostics expose when the scaled
quality bound exceeds attainable utility, including the zero-tolerance artifact.
`UNKNOWN`, `INFEASIBLE`, `MODEL_INVALID`, `EMPTY`, and `NOT_RUN` stay distinct.

## Frozen fixture contract

Each corridor directory contains `manifest.json` and hashed `data.json`. Tight
budget reuses the medium directory. `Manifest.model_json_schema()` describes
manifest fields; `Fixture` is the authoritative byte/evidence validator.

The manifest records schema/fixture versions, evidence type and coverage,
SHA-256 hashes of every fixture file, attraction count, catalog generation/release,
attribution and rights-evidence reference, rating capture model/prompt hash/configuration/date and routing capture provider/profile/departure context/date,
exact offset-aware departure and evaluation clock, endpoint IDs, sampling seed,
tzdata version and limitations. These declarations document supplied evidence;
they do not establish independent legal or production-readiness acceptance.

`data.json` supplies:

- `attractions`: unique stable IDs/names, [lat, lon], complete frozen attribute
  ratings, baseline progress, measured nonnegative solo detour, section and source
  provenance/release, and `solo_route_key`.
- `baseline_route`: a validated Mapbox-shaped route with duration seconds,
  distance meters, geometry and legs. Leg sums must match totals.
- `nodes`: explicit ordered IDs, [lat, lon] and named IANA zones, including all
  attractions, endpoints and usable hotel nodes. `origin_id`/`destination_id`
  identify the endpoint nodes.
- `routes`: exact request-signature keyed records. Each includes
  `request_coordinates` in [lat, lon] order and a Mapbox-shaped `response`.
  Keys are SHA-256 via `route_key(request_coordinates)`. Solo evidence must match
  origin → candidate → destination and the recorded detour. Final selected/hotel
  routes must match their exact request, including leg count. No matrix sum is
  relabeled as a provider reroute.
- `production_shortlists`: scenario ID → frozen at-most-60 unique attraction IDs.
  Solver sweeps cannot silently regenerate or truncate a shortlist.
- Optional directed `travel_time_seconds` and `travel_distance_meters` matrices
  aligned to `nodes`, with zero diagonal and paired unreachable nulls. Both must
  be provided together. They are validated and hashed, without live fallback.
- `hotel_offers`: stable node identity/coordinates, dated explicit room allocation,
  independent `room_offers` prices, total, utility, `currency: USD`, and
  the existing production `price_scope`: `one_room_one_night_including_taxes_fees` or `independent_room_quotes_not_combined_inventory`.
  Missing/incomplete quotes remain missing, never invented as zero.
- `timezone_lookups`: captured coordinates and IANA zones for intermediate hotel
  search positions. Unknown positions block a real replay; no nearest-zone guess.

Real selection fixtures use
`catalog_selection_with_captured_measurements`/`selection_only`. Full pipeline
fixtures use `catalog_recorded_pipeline`/`recorded_pipeline`. Unit fixtures use
`synthetic_unit_only` and require explicit `--unit-only`; these are excluded from
primary figures. The only fixed-zone fallback is explicitly synthetic.

The offline pipeline uses actual adaptive `attraction_candidates` against the
immutable source subset, the same five-mile/60 nearby bound and frozen ratings.
It reuses the production planner, road checking, hotel scheduler, `apply_timing`
and `build_itinerary`. This is a catalog-subset simulation with recorded road
responses, not a live capture or proof of nationwide coverage. Missing evidence
blocks the cell, and never invokes a provider. Worker socket connection and DNS
operations are denied. Setup/imports cannot trigger a paid capture command;
there is no live/capture CLI mode.

## Measurements and comparisons

`balanced-route-v4` extends existing Lab metrics. Selected/delivered utility each
has count, sum, mean, minimum, maximum and median. Missing delivered scored IDs
make delivered utility unassessed. Unsolved utility is null. Gaps include all
baseline endpoint gaps, actual longest final driving leg with its distance,
and attraction-free driving through intervening hotels, excluding sleep/visits.
Signed added driving uses the same direct/final evidence; negative observations
remain visible. Hotels report complete room-night totals, utilization, excess,
over-target fractions and unused target. Zero-target and no-hotel ratios are
null. Fuel, food, admissions and a hard total-trip budget remain unassessed.

Scenario day/density adherence and schedule validity are separate assessments.
Failures retain raw statuses, nested stage attribution, partial route/itinerary
artifacts and assessed denominators. Persistence is explicitly local-files-only;
the existing Lab begin/finalize failure tests still cover live storage behavior.

Model keys include source/candidate hashes, baseline, K, configuration, revision,
patch and metrics. Time/seed/worker limits are search controls rather than model
changes. Never rank raw objectives across differing coefficients, thresholds,
quality bounds, persona weights or candidate pools. The 60-vs-100 comparison is
an input-pool experiment. Common physical metrics support fair method comparisons.

Reports plot only calculated real-evidence rows, faceted by trip type, persona,
density, evidence layer and track. SVG box plots show actual observations,
1.5×IQR whiskers and n; fewer than four observations use points only. Grouped
columns show raw solver counts, assessed pass rates, hotel excess, utilization
and over-target fraction. Missing measurements have empty states. Solver repeats
on a fixture measure search variation, not traveler-satisfaction samples.

## Remaining data gates

No real 100-place corridor capture was supplied for this implementation. The last
catalog checkpoint reported 12 Boulder places locally and no Neon activation;
that is insufficient evidence for these corridor suites. The catalog owner must
supply a versioned usable generation, attribution/rights evidence, arrival
eligibility and sufficient unique corridor coverage, followed by existing
captured ratings, exact road responses, hotel/occupancy dates and timezone
lookups. Do not pad with synthetic places or alter catalog query/ingestion guards.

The harness can record the expected 30 blocked cells now. Real calculated
comparisons and primary figures remain pending. Paid capture/live acceptance
requires its own approved provider/count/spending scope after catalog readiness.
No main merge, deployment, production database, credentials or source import is
part of this change.
