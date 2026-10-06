# Explain the adaptive CP-SAT pipeline

Current contract: October 5, 2026, `codex/production-release`. Studio (`/studio`)
and ordinary chat use the same live planner. Historical surplus objectives remain
historical; the current metric version is `balanced-route-v3`.

Provider records establish place identities and coordinates. AI estimates the
14 canonical interest ratings, and the backend computes each place's match as
`sum(normalized_trip_weight × rating)`. A rating is an estimate, not a provider
fact. Account interests and trip overrides retain their existing precedence.

## Discovery and road measurements

The baseline Mapbox route supplies geometry and step driving durations. Equal
driving-time sections receive evenly spaced search points in round-robin order.
Nearby Terra searches retain the five-mile radius and verified attraction filter.
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

Eligible candidates have utility at least `0.60` and usable measured road routes.
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
detour half before and half after its two-hour visit. Days and nights remain
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
errors/attempts, stage JSON, saved history and map/itinerary viewing. It reports
average match, quality loss, spacing deviation, estimated detour and actual final
extra driving separately. Historical objective scores are never relabeled as
current minimized costs. See [run history](algorithm-run-history.md).
