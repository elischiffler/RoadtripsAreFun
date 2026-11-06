# Studio research

The **Research** link in Studio opens `/studio/research`. This dashboard shows one saved study version at a time and supports pause,
resume and exports. A compact solve-limit version switch opens the current or previous matching matrix. There is no study creation form. Runs continue without an open
browser. CSV and JSON exports retain the underlying observations and protocol.

## Requested design

The October 20 rerun schedules **6,300 CP-SAT trials only**, with a fixed
**15-second solve limit** and **no full trip planning runs**. The original October
19 design scheduled 6,300 solver trials followed by 300 live pipeline runs; its
results remain historical and separate.

| Trip                 | Route                  | Target days | Requested attractions at 1 / 2 / 3 per target day |
| -------------------- | ---------------------- | ----------- | ------------------------------------------------- |
| Short single day     | Los Angeles–San Diego  | 1           | 1 / 2 / 3                                         |
| Medium two-day       | San Francisco–Boise    | 2           | 2 / 4 / 6                                         |
| Long three-day       | San Francisco–Denver   | 3           | 3 / 6 / 9                                         |
| Coast to coast       | San Francisco–New York | 5           | 5 / 10 / 15                                       |
| Tight budget two-day | San Francisco–Boise    | 2           | 2 / 4 / 6                                         |

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
The baseline configuration allows an average utility score loss of ten percentage
points, spacing weight 1 and detour weight 1. The study changes one factor at a
time:

| Condition     | Allowed utility score loss        | Detour weight |
| ------------- | --------------------------------- | ------------- |
| Baseline      | 10 percentage points              | 1             |
| Quality sweep | 0 / 5 / 15 / 20 percentage points | 1             |
| Detour sweep  | 10 percentage points              | 0.5 / 2       |

The baseline is counted once. Each condition uses the same candidate set, stop
count, persona and repeat seed. Seeds are repeat index minus one. Trial order is
shuffled within repeat blocks using the declared study seed. Solver trials run
serially, with one OR-Tools worker. The initial October 19 campaign uses its frozen
five-second solve cap. From October 20, new plans inherit the shared fifteen-second
CP-SAT default for every condition. Candidate capacity is explicitly 100 for this
experiment; interactive discovery retains its existing maximum of 60.

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

- Heatmaps show means of per-run values by trip, persona and stop rate. Utility score
  mean/minimum/median/maximum are retained per run, with full precision in exports.
- Utility score summaries pool the actual assessed attraction values. Repeat box plots
  show per-run average utility score; the box is the middle 50%, its line the median,
  and whiskers the observed minimum and maximum, not confidence intervals.
- Outcome columns retain complete, partial, failed and interrupted attempts.
  Raw OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, EMPTY and NOT_RUN
  statuses remain distinct. UNKNOWN is not relabeled infeasible.
- Row comparisons cover extra distance/driving, longest driving gap, room-target
  utilization/excess, fulfillment, actual days and runtime. Missing values remain
  missing; hotel-free trips do not receive a fabricated zero budget deviation.
- The selection-setting filter selects the condition shown in the remaining charts.
  The settings comparison section and parameter-response lines are removed;
  recorded conditions and their measurements remain available in exports.
- The live scatter plot compares actual added driving with delivered utility scores.

Quality plots assess only complete, fully delivered, timing-valid outputs.
Over-target hotel quotes and trips exceeding the target days are **not** removed
from this group. Fulfillment, actual-days and runtime plots retain assessed partial
or failed attempts as appropriate. Every metric has its own assessed n; pending
runs are not failures or zeros. Utility scores are model estimates, not visitor
ratings.

The live longest-gap metric is actual driving between attractions, including
endpoint gaps; overnight downtime is excluded. The controlled solver uses baseline
progress gaps, not actual itinerary legs. Room-target metrics cover quoted
room-nights only, not food, fuel, total-trip cost or booking guarantees. Objective
and bound values remain in records/exports for diagnosis within an unchanged
condition; they are not pooled as a trip-quality score.

Selection time uses adaptive display units: ms below one second, s below one
minute, then min or h. Values, ranges, axes and tooltips carry their units.
Raw exported fields ending in `_seconds` retain seconds. Distances ending in `_meters` retain meters. Planning
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

The dashboard consistently uses **utility score**, while exported metric
keys retain `utility_mean`, `utility_min`, `utility_median` and `utility_max`.
Counts say “runs scored” or “runs measured”; missing and excluded measurements
are identified with an explicit denominator. Heatmap cells show the observed
run-to-run range, or indicate when all scored results are identical. These ranges
are descriptive extrema, not confidence intervals. Summary cards show remaining
runs, success share, incomplete-outcome counts and the middle half of measured
planning times. CP-SAT outcomes use one 100% stacked bar for filtered runs,
with percentage labels and counts in the color-matched legend. Hovering or focusing
a segment subtly highlights its legend item. Raw solver status codes remain in
exports. The settings comparison chart and paired-change summary are removed.

The attraction utility score histogram uses the same pooled utility scores as the four
summary values, in fixed five-point bins over 0–100%. Internal boundaries belong to the
higher bin; 100% belongs to the final 95–100% bin. Bar heights count scored
attractions and their hover labels include the share of all plotted scores.
Reference lines show the average and median, and the middle-half range shows the
25th–75th percentiles. Failed, missing, non-finite and out-of-range scores do not
contribute. Repeated attractions across runs remain repeated observations, not
unique attractions or independent samples.

Data marks support a compact, header-free inspection tooltip: one key value and
an optional short supporting line. Info icons use brief chart explanations; the
full measurement definitions remain documented here. Heatmap cells expose
the difference from the displayed average; histogram bars show their share of plotted scores. Native hover titles are removed from
those marks to avoid duplicate popups. Hover waits briefly for pointer intent;
focus and taps open immediately. Tab enters a chart, arrow keys move between its
marks, and Escape dismisses the tooltip. Scrolling dismisses detached overlays.
Motion is limited to short opacity/shadow transitions and respects reduced-motion
preferences; incoming measurements do not replay chart animations.

The trip comparison names the selected measure in its title. Each row uses one horizontal
range: thin line for observed minimum–maximum, thick line for the middle 50%,
a tick for the median and an amber dot for the mean. Mean and median values
are printed below; inspection gives only the range and middle-half values.
Utility scores use shared observed-range bounds, padded to five-point steps
and limited to 0–100%; the axis labels show those bounds. Other measures include
the observed range and zero. The separate consistency box plot is removed to avoid repeating these data.
These are per-run distributions, distinct from the attraction-level histogram.

Dashboard terminology is shared across filters, charts, tooltips and accessible
labels: mean, median, middle 50%, finished runs, complete runs, stops per day,
and added driving. Complete runs describe delivered trips;
finished runs also include partial, failed and interrupted runs. Attraction-level
utility scores remain distinct from per-run summary measures. Export field names
and stored measurement definitions are unchanged.

## Standard solve limit (October 20, 2026)

New interactive solves and newly created Studio research plans use one fixed
15-second CP-SAT limit. An optimal solve can finish earlier; a feasible selection
is still accepted when the limit is reached. This is a per-solve cap, not a
whole-trip deadline. Existing studies execute their saved configuration and keep
their original results and source identity. The initial five-second campaign has
not been rewritten or selectively retried. A consistent fifteen-second dataset
requires a fresh complete set of controlled trials; retrying only timeouts would
create a different protocol. The October 20 replacement reruns stop selection only: 6,300 controlled trials
and no live pipeline cases. Historical five-second results are retained, not
overwritten or pooled into the replacement.
The separate offline evaluation harness retains its explicit historical sweep
limits and recorded protocol; these are not ordinary application defaults.

**Rerun stop selection** creates the largest saved matrix as a new solver-only
batch, with the same candidate seed and verified dataset hash, and all original
trip/persona/stop-count conditions and repeats. The server requires execution
opt-in and rejects reruns while a batch is active or pausing. Saved configurations
are immutable; the new batch records the previous ID and current source identity.
The browser archives historical capabilities locally and switches to only the
new batch before starting it. A failed start leaves Resume available. A failed
creation leaves the current dashboard intact. The solve limit is shown from the
saved protocol rather than inferred from today's default. Full trip planning is
not scheduled by this action, and zero-count modes are hidden.

The **Study version** switch shows the saved solve limits (currently 5 s and
15 s). It opens one matching full matrix at a time; the small pilot is excluded
from the historical version. Charts and exports follow the selected version,
while the current worker continues independently. Historical views are read-only.
The tab remembers the selected version across reloads without changing the saved
current batch or its capability. Switching versions never starts, pauses or
reruns work. Metadata requests use the incremental cursor to avoid downloading
all historical run records before the version is opened.

Dashboard time labels use **s** for seconds, including version switches and solve
limits. Selection-time display conversion leaves stored observations, chart
positions, statistics and CSV/JSON measurements unchanged.

## PostgreSQL results and cross-browser access (October 20, 2026)

Research results now have an additive PostgreSQL mirror using the application's
existing database connection and write gate. Explicitly apply
`backend/sql/studio_research.sql` before setting backend-only
`STUDIO_RESEARCH_DATABASE=true`. Startup never creates database tables. The local
development database migration and backfill were performed under the owner's
request; this does not deploy main or enable any production application setting.

The API lifespan synchronizes the private SQLite queue every five seconds. It
backfills every declared case, then transfers newly finished cases through the
existing monotonic event cursor. Each study update and its result rows commit in
one PostgreSQL transaction. Repeated syncs do not duplicate observations; late
low-ID cases are retained. Frozen inputs, candidate data, source identities,
protocols, measurements and raw CP-SAT outcomes remain unchanged. Different source
identities, protocols or a cursor moving backward fail closed instead of replacing
the saved results. No existing catalog or account tables are changed.

SQLite remains the execution queue for the already-running worker. If the API or
database is unavailable, the worker continues saving locally; synchronization
catches up when the API and database return. Keep the private SQLite directory
and original source archives for pause/resume and recovery. PostgreSQL results
are independently readable after backfill, without a browser's local study keys.
The pre-change queue backup and exact backend source are retained locally as
`before-database-sync.sqlite3` and `source-before-database-sync.tar` inside the
ignored research artifacts directory. Source-change guards still apply to worker
restarts; ongoing loaded workers continue their frozen protocol.

With database access explicitly enabled, `/studio/research/saved` and its
per-study snapshot/export endpoints require a valid Studio session. Research
results in these tables are shared read-only with holders of the existing Studio
password, independently of the random visitor identity. This sharing covers only
research studies; account trips and visitor trip history retain their ownership
rules. Visitor identities and study control capabilities are never copied to
PostgreSQL or returned through the saved-results endpoints. The database view
cannot start, pause or rerun work. Browsers that already hold a private control
capability retain their existing controls.

A fresh browser asks for Studio access and discovers saved study versions from
PostgreSQL. The current full matrix opens first; the matching historical version
remains available through the solve-limit switch. CSV and JSON exports use the
selected saved version. Without database opt-in, existing private capability
access continues to work. Authentication expiry returns database viewers to the
Studio password form.

Loaded research libraries, chart labels and study snapshots are cached in the
browser tab's session, scoped to the backend, Studio session and study capability.
Returning to Research or reloading the page restores the previously loaded rows.
Completed studies need no repeat download; active studies display cached rows
immediately and request changes after their saved cursor. Switching study versions
keeps each snapshot separate. Session clearing and successful study control/rerun
actions invalidate the relevant cache. Large snapshots use gzip when supported;
if browser storage is unavailable or full, an in-memory fallback still avoids
repeat downloads during navigation. This cache creates no local database and
does not persist across a closed browser tab.

The **CP-SAT outcomes** card shows each recorded status and its share of filtered
finished runs. Optimal means the lowest objective was proven; Feasible means a
valid selection was found without proving it best. Infeasible means the encoded
constraints cannot be met. Unknown means the solver stopped without a selection
or an infeasibility proof. These are distinct from complete/failed trip outcomes,
and pending cases are excluded from the outcome percentages.

Verification includes disposable real PostgreSQL migration reapplication,
backfill, idempotent sync, late-case cursors, preserved measurements, conflicting
source rollback, write gates, session-required reads, exports and denied controls.
The disposable PostgreSQL runner exercises these checks before its backup and
restore stages. Unit tests disable background hosted synchronization regardless
of a developer's local opt-in.

October 20 validation: backend Ruff formatting/lint, 2,011 tests passed (130
skipped) with 80.34% coverage, using the disposable research-test database;
frontend formatting/lint, 282 tests with 92.44% line coverage, and production
build passed. The disposable PostgreSQL CRUD/recreation/backup/restore workflow
passed, including the three new real research-persistence checks. Arc was tested
with no study capabilities: Studio password access, reload, both study versions
and live CP-SAT counts all worked. All 12,907 declared cases across three studies
were backfilled, and copied observations/protocols were compared with their
original records. The fifteen-second worker remained running. These checks do
not claim that its 6,300 trials have finished or that main was deployed.
