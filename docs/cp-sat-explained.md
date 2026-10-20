# Explain the adaptive CP-SAT pipeline

## Catalog discovery (October 15, 2026)

Daytime and optional evening discovery read the active, licensed mixed-source
catalog in Neon PostgreSQL. PR #40 deployed the first bounded release; this does
not establish nationwide coverage or complete live journey acceptance.
Missing coverage returns no places. Hotels, Mapbox road checks, geocoding and
model-estimated interest ratings remain separate dependencies. See
[rollout and rollback](neon-places-catalog.md) and the
[Tripadvisor integration removal audit](tripadvisor-removal.md).
Historical provider descriptions and measurements below retain their original
meaning; they are not instructions for the current discovery implementation.

Current develop contract: October 19, 2026. Studio (`/studio`) and direct route
requests use the same live planner. Historical surplus objectives remain
historical; the current metric version is `balanced-route-v5`. See
[visit-duration estimates](visit-duration-estimates.md) for the shared bounded
visit lengths and frozen offline capture contract.

Provider records establish place identities and coordinates. AI estimates the
14 canonical interest ratings, and the backend computes each place's match as
`sum(normalized_trip_weight × rating)`. A rating is an estimate, not a provider
fact. Account interests and trip overrides retain their existing precedence.

## Discovery and road measurements

The baseline Mapbox route supplies geometry and step driving durations. Equal
driving-time sections receive evenly spaced search points in round-robin order.
The catalog branch retains the five-mile radius with explicit daytime category
filtering. Catalog identity and coordinates are source facts; release and evidence
dates do not establish current business availability. Unknown opening hours remain
unknown. Sparse catalog results are reported without a live-provider fallback.
Raw, rating and solver capacities are balanced across sections, with unused
capacity redistributed. Available categories provide variety; absent categories
are not invented. See [adaptive planning](adaptive-planning.md) for the budgets.

Each round finishes its nearby calls before freezing a rating pool. Batches
contain at most five verified names. Refinement starts with sections having no
eligible places, then those with the fewest. It searches the midpoint of the
largest unsearched interval. Sparse sections and remaining intervals are reported;
this bounded sample cannot establish continuous corridor coverage.

Projection onto actual step geometry determines `route_progress_seconds`.
Step durations convert cumulative geometry progress to driving time. Crossing
ambiguities use the originating search point as a tie hint. Each shortlisted
candidate then receives a live origin–candidate–destination Mapbox route. Its
extra duration over baseline is retained raw and clamped to zero only for the
optimization estimate. Unusable individual road routes are excluded with reasons;
general provider failures fail the required stage.

## The selection model

Eligible candidates have positive utility and usable measured road routes.
Neutral or specialized places remain available when they are the best matches in
the catalog. Ratings keep their original values; the existing ten-point quality
bound compares the selected average with the best achievable average.
Let `K = min(requested_count, eligible_count)`. Select exactly K candidates. There
is no nearest-query-slot constraint. With zero requested stops discovery is
skipped; no eligible candidates produce the honest empty-selection status.

Let B be the average utility of the best K eligible candidates. Require selected
average utility to be at least `B − 0.10`. Thus a quality difference beyond ten
percentage points takes precedence over better spacing or shorter detours.
Utilities use conservative million-unit integer rounding for this constraint.

Sort candidates by measured baseline progress, then provider ID. The selected
path has K+1 gaps, including origin-to-first and last-to-destination. Minimize:

```text
sum(abs(gap_seconds − baseline_seconds / (K + 1)))
  + sum(candidate_solo_detour_seconds)
```

One minute of spacing deviation costs the same as one minute of estimated detour.
The solver uses rounded integer seconds, multiplying gap terms by K+1 to avoid
fractional coefficients. Displayed objective and bound divide this scale back
into seconds. Separate explanatory measurements retain their continuous values;
small rounding differences are expected. A DAG path model links selected places
in route order and enforces cardinality and the quality bound.

CP-SAT uses seed zero, one worker and a five-second limit. OPTIMAL proves the best
encoded cost for this bounded, verified candidate set. FEASIBLE is accepted with
its actual bound and status. Other statuses fail explicitly. Fixed inputs support
repeatability; fresh live discovery and AI estimates can change each run.

## Scheduling and final validation

The scheduler consumes measured progress and initially splits each estimated solo
detour half before and half after its validated visit estimate. Missing duration
metadata keeps the historical two-hour policy; invalid explicit metadata fails
validation. Optional AI estimates fall back to two hours on provider/format failure. Days and nights remain
sequential. Existing local daily windows, IANA timezones/DST, destination deadlines,
optional evenings, room occupancy and verified dated hotel quotes remain in force.
Hotel search/ranking and advisory per-room budgets are separate from the solve.
Independent room allocations are intersected after verification; separately quoted
rooms do not guarantee simultaneous booking inventory.

The final Mapbox route through all chosen stops supplies actual leg durations.
Shared timing validation finishes before itinerary construction and saving. Solo
detour estimates are not additive road guarantees: final extra driving is reported
separately and a final route can still fail timing validation. This is attraction
selection followed by scheduling, not joint hotel/total-budget optimization.

## Source guide and Studio explanation

`routing/discovery.py` owns typed plans/results; `geometry.py` owns projection;
`sources/persona_candidates.py` owns discovery/ratings; `planners/cp_sat.py` owns
road-check barriers; `cp_sat_selection.py` owns the exact model;
`cp_sat_scheduler.py` owns scheduling. `runtime.py` owns bounded provider leaves,
run-local clients and cancellation. `routing_api.py` owns final live verification.

Studio retains all nine complete-form presets, real streamed progress, safe
errors/attempts, saved history and map/itinerary viewing. Its **Trip stats** tab
shows compact figures and bars for estimated matches, counts, actual extra
driving, quotes, scheduling and planning times. Raw explanations and measurements
remain stored; the tab omits stage JSON and solver formulas. Historical objective
scores are never relabeled as current minimized costs. See [run history](algorithm-run-history.md).
