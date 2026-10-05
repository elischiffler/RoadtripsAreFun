# Algorithm Lab experiment history

Studio visitor and owner-authorized `/algorithm-lab/run` requests are recorded
in their isolated identity scopes. Ordinary chat planning is excluded. The UI at `/studio` provides **Trip presets** and a
persistent **Run history** table, with inputs and measurements in each disclosure.
The nine presets include coastal nature, culture, overnight, short, medium, long,
dense, sparse and tight hotel budget trips. Driving times and overnight counts
are targets to measure, not guarantees. Adaptive solver capacity ranges from 18 to 60 across trip sizes.

The **Trip presets** button opens a modal. Selecting a card replaces the whole
editable form and closes the modal without starting a run. Profiles vary departure
time, travelers/children, rooms, interests, vehicle and evening schedule. Dates
default to tomorrow when the catalog loads. Reset restores the selected profile.
The former benchmark batch button and repeat modal have been removed; run a
selected preset with **Run live route**. Every new run calls live providers through
the ordinary routing and itinerary pipeline. Hotel and evening discovery follow
the trip needs. There is no replay or candidate-fixture option. Historical replay
and benchmark records remain labeled in history.

Successful saved routes have a **View map and itinerary** button. It loads the
stored route geometry and itinerary in a modal without making another provider
run. Older records saved before route persistence have no viewer button.

## Record lifecycle and ownership

`backend/sql/algorithm_lab_runs.sql` is the authoritative additive DDL. It creates
an independent `algorithm_lab_runs` table with UUID, verified user ID, timestamps,
status, live/replay mode, interactive/benchmark run type, preset, batch/repeat,
input JSONB, versioned metrics JSONB, route/itinerary/discovery/selection explanation result JSONB and a sanitized error code. Owner/time,
batch and exact-comparison indexes support later analysis.

Accepted experiments insert `running` before any paid work; storage failure
returns 503 without starting the experiment. Finalization records `completed` or
`failed`. A failed final save is explicitly shown to the user.
Interrupted processes can leave `running` rows: these are unfinished, never
successes or zero-latency samples. Invalid/auth-rejected HTTP requests are not
experiments. Each explicit request creates a new run; no automatic deduplication
is claimed for manually repeated requests after a lost network response.

The backend derives owner identity from verified Cognito claims and visitor identity
from the signed Studio session, never body fields.
Listing, finalizing and loading saved results are constrained by user ID. History uses private
`no-store` responses, bounded limit (1–500), offset and stable timestamp/UUID order.
UI pages contain 50 rows; **statistics describe the current page**, not all-time
totals. Stored rows remain available through pagination and offline SQL analysis.
No auth tokens, LLM prompts, provider HTML or raw exception strings are recorded.
Retention is currently indefinite; no automatic purge or sampling is configured.
Treat stored trip dates, preferences and resolved city data as private account data.

## What the measurements mean

| Field | Meaning |
| --- | --- |
| Objective | Current minimized spacing-plus-detour cost and bound in seconds. Historical maximized surplus scores keep their original units. Neither measures whole-trip optimality. |
| Utility sum | Sum of selected trip/location dot products, retained alongside the integer objective. Candidate counts affect objective scaling, so cross-pool raw scores need care. |
| Feasibility | Pass/fail of provider identities, successful final driving/scheduling checks and every quoted room meeting the nightly target. Missing evidence/replay is unassessed. Over-target quotes fail this measurement even though the current planner may return them with warnings. |
| Full-trip budget | Unassessed: no hard total-trip budget constraint exists. Room inventory and booking availability are not guaranteed. |
| Latency | Monotonic wall time for execution, excluding DB writes and browser/network overhead. Gathering, selection, AI generation, final reroute/check stage and existing named stage timings are retained where reached. Nested stages overlap; do not sum them. |
| Calls | Actual backend outbound request attempts for TripAdvisor Terra, Mapbox, Mentro generation, Google Hotels and OpenCage. Includes failed attempts; includes gateway authentication; excludes Cognito/JWKS, gateway-internal work and automatic HTTP redirects. |
| Provider events | Mentro empty-response retries and exhausted empty-response caps. These are separate from AI route-validation retries. |
| AI route validation | Null with a reason: pure-AI/custom route solvers and their retry/fallback loops are not active. No fabricated counts or fallback success. |
| Determinism | Empirical equality of canonical successful output hashes for at least two identical-input runs. Includes selected IDs, ordered stops, dates, costs and route duration. It is not a proof of future determinism. |

Inputs retain both submitted and effective normalized weights plus resolved trip
fields. Candidate identity, ratings, utility, measured progress, source queries, sections, detour provenance and selection constraints are
snapshotted. Stable SHA-256 hashes ignore provider timestamps and run UUIDs.
The input cohort groups matching inputs/mode/scoring version/revision, so changing
live discovery still contributes to observed spread. The narrower comparison key
also requires the same candidate model/query points. An `OPTIMAL` reference must use the identical candidate model and scoring version.
For `balanced-route-v3`, report extra selection cost over that reference in seconds
(including a zero optimum); percentage excess is assessed only for a positive
reference. Do not use `100 × score/reference` as match quality for minimized costs.
Historical surplus versions retain their maximized-score ratios. Match quality
and the ten-point loss bound are separate selection measurements. Means, population
standard deviations, assessed denominators and repeat counts are backend-owned.

New metrics use `balanced-route-v3`; historical `selection-surplus-v1/v2` keep
their original meanings. Provider measurements separate wall elapsed time,
accumulated call duration, queue wait, active/peak calls, actual API attempts and
within-run distinct requests. Parallel/nested durations must not be summed as wall
time. Discovery and road-check explanations persist in existing result JSONB;
this change requires no DDL. Docker embeds `ROADTRIPS_REVISION` from its
build SHA. Local development should set an explicit revision when collecting
comparisons; otherwise records say `unversioned-local`. Bump the metric version
when changing score/feasibility/hash semantics; never reinterpret older rows silently.

## Migration and recovery

Apply the additive SQL explicitly to the **approved database target before**
releasing the new backend. Runtime does not create tables. `/ready` now requires
the new table; Lab runs fail closed if it is absent. The Neon write gate remains
authoritative. The original table migration was validated in disposable local databases. On
October 5, the additive result-column migration was tested twice against a
disposable PostgreSQL instance, then applied to the user-connected Neon database
for the requested live preset validation. No public backend deployment is included.

Use the existing database operator's transaction/migration workflow to execute
`backend/sql/algorithm_lab_runs.sql` for a new table, or
`backend/sql/algorithm_lab_run_results.sql` to add saved results to an existing
compatible table. Back up and verify the target first per the
container/database runbooks. `IF NOT EXISTS` makes initial application repeatable,
but does not repair a pre-existing incompatible table. Check columns/indexes after
application. Backend image rollback can leave this additive table in place;
do not drop it or delete experiment data as part of rollback.

`node tests/postgres/run.mjs` validates that disposable schema matches this DDL
and checks real insert/finalize/read, cross-owner isolation, recreation, DB-loss
readiness, backup and restore. The fixture SQL includes this table in the full
dump; restoring into a populated target is refused. Production schema history
and public deployment still require separate verification.

## Trip evaluation (v2)

`metrics.trip_evaluation` retains measurements when a route succeeds but itinerary
construction fails. Driving records the direct Mapbox baseline, final driving,
and signed differences in meters/seconds and percentages. Missing/zero baselines
leave percentages unassessed. Stop fulfillment compares delivered `stop` attractions
with the requested cap, separately from solver selection; hotels, destination and
optional evenings are excluded.

Schedule records itinerary days, overnights, final arrival/timezone and UTC elapsed
trip seconds. Deadline slack uses the backend's recorded deadlines: attraction
visit departure, hotel/destination arrival. Missing timestamps leave overall
compliance unassessed, with the count of stops that could be checked.

Hotel totals sum the verified USD room offers at each overnight, not the legacy
route cost field. Each room offer represents one room-night. A missing room offer,
invalid price, or mismatch with requested room count makes totals unassessed.
No-hotel routes have zero quoted hotel cost. Over-target counts and dollar amounts
compare each room-night against the nightly per-room target; they exclude food,
fuel, admission and booking guarantees.

Warnings, stage statuses and the first failed stage explain incomplete outcomes.
Stage detail strings and raw exceptions are not stored in these metrics. Storage
errors log operation, exception class and SQLSTATE without raw database errors.

History includes a current-page completion summary over finalized rows; unfinished
rows are counted separately. Comparable cohorts show distributions with assessed
sample counts for detour distance/time, stop fulfillment and hotel quotes. Version
and revision separation preserves historical comparisons. Older and unfinished
records remain readable without v2 fields.
