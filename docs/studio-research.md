# Studio research

The **Research** link in Studio opens `/studio/research`. This dashboard combines locally saved results in one view and supports pause,
resume and exports. It has no study creation form or study selector. Runs continue without an open
browser. CSV and JSON exports retain the underlying observations and protocol.

## Requested design

The default study prioritizes CP-SAT: **6,300 solver trials**, followed by
**300 live pipeline runs**, for **6,600 total**.

| Trip | Route | Target days | Requested attractions at 1 / 2 / 3 per target day |
| --- | --- | --- | --- |
| Short single day | Los Angeles–San Diego | 1 | 1 / 2 / 3 |
| Medium two-day | San Francisco–Boise | 2 | 2 / 4 / 6 |
| Long three-day | San Francisco–Denver | 3 | 3 / 6 / 9 |
| Coast to coast | San Francisco–New York | 5 | 5 / 10 / 15 |
| Tight budget two-day | San Francisco–Boise | 2 | 2 / 4 / 6 |

Five trip types × two personas (nature, entertainment) × three stop rates gives
30 combinations. Live trips repeat each combination ten times. Solver trials
repeat each combination thirty times under seven conditions. The backend design stores live and solver repeat counts independently; the
solver design supports up to 100 seed repeats.

The personas reuse the canonical evaluation weights in
`backend/app/routing/evaluation/scenarios.py`. Every live case has two adults,
one room, 08:00 origin-local departure, no car contribution and no optional
evening suggestions. The nightly room target is $180, or $60 for the tight-budget
case. Departure defaults to seven days after the current Los Angeles date.
Target days set requested stop count, rather than imposing a new scheduling
constraint. Actual days and delivery remain measured outcomes.

## Controlled CP-SAT study

A seeded generator freezes exactly **100 synthetic candidates** once per study.
Their canonical attribute ratings, progress fractions and solo-detour inputs are
hashed and exported. These are controlled test data, not real attractions,
verified entrances, published opening hours or measured road journeys.

The actual shared `select_attractions` implementation runs on this set. Baseline
driving inputs are simulated 3 / 12 / 24 / 45 / 12 hours for the five trip types.
The baseline configuration allows an average utility loss of ten percentage
points, spacing weight 1 and detour weight 1. The study changes one factor at a
time:

| Condition | Allowed utility loss | Detour weight |
| --- | --- | --- |
| Baseline | 10 percentage points | 1 |
| Quality sweep | 0 / 5 / 15 / 20 percentage points | 1 |
| Detour sweep | 10 percentage points | 0.5 / 2 |

The baseline is counted once. Each condition uses the same candidate set, stop
count, persona and repeat seed. Seeds are repeat index minus one. Trial order is
shuffled within repeat blocks using the declared study seed. Solver trials run
serially, with one OR-Tools worker and a five-second solve cap. Candidate capacity
is explicitly 100 for this experiment; interactive production discovery retains
its existing maximum of 60. No production solver defaults change.

The repeats assess solver variation on **one fixed dataset**, not 30 independent
real-world candidate samples. Budget is not an input to attraction selection;
the medium and tight-budget selection workloads are otherwise identical. The
nightly-target effect belongs to the live pipeline study. Zero-loss cells retain
integer quality-bound diagnostics, including an unattainable scaled bound; an
infeasible integer model does not establish a real-world shortage of attractions.

## Live pipeline study

After solver trials finish, two live cases run at a time through the existing
`algorithm_lab.recorded_run` pipeline. The same backend validation, catalog and
calendar checks, ratings, road checks, CP-SAT selection, hotels, final routing,
itinerary and scoped history storage remain authoritative. Each case has a
deterministic UUID under the study UUID and a twenty-minute whole-run deadline.
The 300 runs can make many more than 300 external requests and use paid providers.

Fresh candidate sets, model estimates, catalog generations and provider conditions
can vary between live repeats. Candidate hashes and observed catalog generations
are retained. Live repetitions do not isolate a solver parameter effect; their
results remain separate from the controlled study. Source validation and unknown
hours are never bypassed to produce a completed trip.

## Measurements and plots

- Heatmaps show means of per-run values by trip, persona and stop rate. Utility
  mean/minimum/median/maximum are retained per run, with full precision in exports.
- Utility summaries pool the actual assessed attraction values. Repeat box plots
  show per-run average utility; the box is the middle 50%, its line the median,
  and whiskers the observed minimum and maximum, not confidence intervals.
- Outcome columns retain complete, partial, failed and interrupted attempts.
  Raw OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, EMPTY and NOT_RUN
  statuses remain distinct. UNKNOWN is not relabeled infeasible.
- Row comparisons cover extra distance/driving, longest driving gap, room-target
  utilization/excess, fulfillment, actual days and runtime. Missing values remain
  missing; hotel-free trips do not receive a fabricated zero budget deviation.
- Parameter-response lines keep trip and stop rate fixed, with separate persona
  series and per-point sample sizes. The paired utility comparison matches the
  same persona, stop rate, trip and seed. It makes no significance claim.
- The live scatter plot compares actual added driving with delivered utility.

Quality plots assess only complete, fully delivered, timing-valid outputs.
Over-target hotel quotes and trips exceeding the target days are **not** removed
from this group. Fulfillment, actual-days and runtime plots retain assessed partial
or failed attempts as appropriate. Every metric has its own assessed n; pending
runs are not failures or zeros. Utility values are model estimates, not visitor
ratings.

The live longest-gap metric is actual driving between attractions, including
endpoint gaps; overnight downtime is excluded. The controlled solver uses baseline
progress gaps, not actual itinerary legs. Room-target metrics cover quoted
room-nights only, not food, fuel, total-trip cost or booking guarantees. Objective
and bound values remain in records/exports for diagnosis within an unchanged
condition; they are not pooled as a trip-quality score.

Selection time is displayed in milliseconds; raw exported fields ending in
`_seconds` retain seconds. Distances ending in `_meters` retain meters. Planning
time uses the existing core pipeline timer or controlled model-and-solve timer;
failed pre-pipeline attempts retain measured time until failure. Attempt-start
and result-recording timestamps are UTC.

## Persistence, execution and access

Batch execution requires backend-only `STUDIO_RESEARCH_ENABLED=true`; deployments
default to disabled. The requested local development environment enables it.
The private SQLite store defaults to `.artifacts/studio-research/`, or an explicit
`STUDIO_RESEARCH_DIR`. A deployment would need a writable durable mount and an
explicit execution opt-in; this work adds no production mount or database DDL.

Creating a study requires a valid Studio session. A random, study-scoped capability
then permits reading, exporting, pausing and resuming that immutable study. The
browser retains this key locally and sends it in a header, never a URL. This lets
an already-authorized long study remain inspectable after the eight-hour Studio
session expires. Capabilities and owner identities are excluded from exports.

The API launches a detached Python worker. On macOS, a scoped `caffeinate -i`
wrapper prevents idle system sleep for the worker's lifetime; display sleep is
unaffected. The machine must remain running. This is a single-machine runner,
not a distributed scheduler. One study may execute at a time per research store.

Pause finishes the current solver trial or in-flight live cases and leaves the
remainder pending. Resume never repeats finished cases. After a worker crash,
unfinished solver work can be recomputed; live work is reconciled against its
original persisted UUID. An unfinalized paid run is marked interrupted rather
than silently repeated. Three consecutive storage/authorization failures pause
unstarted work. Resuming after backend source changes is refused so revisions
are not mixed. Each study records Git identity, source hash and software/hardware
versions; live metrics retain that study revision.

Results and input cases are transactional local records. Incremental cursors
follow completion events rather than case IDs, so later live runs with lower
predeclared IDs cannot be missed. CSV includes pending cases with blank outcomes;
JSON includes the declared protocol, frozen candidates and observations. Full live
envelopes are retained privately at `STUDIO_RESEARCH_DIR/<study UUID>/<run UUID>.json`
and through the existing scoped Lab storage. No synthetic results enter live Lab
history, and no production catalog generation is changed.

## Verification

A separate seven-trial browser check completed all seven real CP-SAT calls on the
controlled synthetic dataset, with no provider calls. It verifies the detached
worker, persistence, incremental result display and seven condition definitions;
it is separate from the requested 6,600-run batch, but its seven observations
are now included in the combined dashboard. Controlled tests cover exact
counts, one-factor changes, same-input pairing, key/owner isolation, duplicate
start rejection, pause/resume, interrupted paid-work reconciliation, source-change
refusal, storage-failure pausing, missing/partial metrics and late low-ID results.
Application checks and CI are recorded separately from the still-running study;
passing tests do not establish empirical findings or completed live trips.

Local checks on October 19, 2026 passed: backend Ruff formatting/lint and
2,005 tests (130 skipped), with 80.28% coverage; frontend formatting/lint,
264 tests with 90.77% line coverage, and the production build. Existing coverage
thresholds remain unchanged.

## Combined dashboard

All locally saved study capabilities load automatically into one dashboard.
Original runs, input protocols, datasets and revision records remain intact;
CSV retains its study-id column, and JSON includes each original protocol.
Source case IDs are namespaced before rendering. Parameter comparisons match
within each original study so shared solver seed numbers never create cross-study
pairs. The earlier seven-trial verification batch remains identifiable in exports;
its observations are now included in the combined descriptive charts. Repeated
seeds across batches are not independent samples. Source failures remain visible
and are retried without cancelling the detached worker.

## Dashboard labels and supporting measurements

The dashboard calls utility an **interest match score**, while exported metric
keys retain `utility_mean`, `utility_min`, `utility_median` and `utility_max`.
Counts say “runs scored” or “runs measured”; missing and excluded measurements
are identified with an explicit denominator. Heatmap cells show the observed
run-to-run range, or indicate when all scored results are identical. These ranges
are descriptive extrema, not confidence intervals. Summary cards show remaining
runs, success share, incomplete-outcome counts and the middle half of measured
planning times. Selection results use plain labels and show each outcome's share
of filtered runs; raw solver status codes remain in exports. Matched setting
comparisons show the number of comparisons and observed range of changes.
