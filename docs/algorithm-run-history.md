# Algorithm Lab experiment history

Only owner-authorized `/algorithm-lab/run` requests are recorded. Ordinary chat
planning is excluded. The UI at `/algorithm` provides **Benchmark trips** and a
persistent **Run history** table, with inputs and measurements in each disclosure.
Six server-owned trip categories cover short, medium, long, dense, sparse and
tight hotel budget cases. Driving times and overnight counts are targets to
measure, not guarantees. The current candidate cap remains 30 even on long routes.

Select trips and 1, 3, 5 or 10 repeats. Requests execute sequentially with a shared
batch UUID and repeat index. Stop finishes the current request and skips future
ones. Closing the page stops the browser queue; it does not cancel work already
accepted by the server. There is no durable background queue or automatic retry.
Every new run calls live providers through the ordinary routing and itinerary
pipeline. There is no replay mode or candidate-fixture option in the main form,
benchmark dialog or run API. Hotel and evening discovery follow the trip needs.
Historical replay records remain labeled in history; they cannot be rerun.

## Record lifecycle and ownership

`backend/sql/algorithm_lab_runs.sql` is the authoritative additive DDL. It creates
an independent `algorithm_lab_runs` table with UUID, verified user ID, timestamps,
status, live/replay mode, interactive/benchmark run type, preset, batch/repeat,
input JSONB, versioned metrics JSONB and a sanitized error code. Owner/time,
batch and exact-comparison indexes support later analysis.

Accepted experiments insert `running` before any paid work; storage failure
returns 503 without starting the experiment. Finalization records `completed` or
`failed`. A failed final save is explicitly shown to the user and halts a batch.
Interrupted processes can leave `running` rows: these are unfinished, never
successes or zero-latency samples. Invalid/auth-rejected HTTP requests are not
experiments. Each explicit request creates a new run; no automatic deduplication
is claimed for manually repeated requests after a lost network response.

The backend derives identity from verified Cognito claims, never body fields.
Both listing and finalizing are constrained by user ID. History uses private
`no-store` responses, bounded limit (1–500), offset and stable timestamp/UUID order.
UI pages contain 50 rows; **statistics describe the current page**, not all-time
totals. Stored rows remain available through pagination and offline SQL analysis.
No auth tokens, LLM prompts, provider HTML or raw exception strings are recorded.
Retention is currently indefinite; no automatic purge or sampling is configured.
Treat stored trip dates, preferences and resolved city data as private account data.

## What the measurements mean

| Field | Meaning |
| --- | --- |
| Objective score | Exact CP-SAT integer attraction-selection objective, including deterministic tie preference. Not `score_trip`, enjoyment probability or a total-trip optimum. Null when no solver score exists. |
| Utility sum | Sum of selected trip/location dot products, retained alongside the integer objective. Candidate counts affect objective scaling, so cross-pool raw scores need care. |
| Feasibility | Pass/fail of provider identities, successful final driving/scheduling checks and every quoted room meeting the nightly target. Missing evidence/replay is unassessed. Over-target quotes fail this measurement even though the current planner may return them with warnings. |
| Full-trip budget | Unassessed: no hard total-trip budget constraint exists. Room inventory and booking availability are not guaranteed. |
| Latency | Monotonic wall time for execution, excluding DB writes and browser/network overhead. Gathering, selection, AI generation, final reroute/check stage and existing named stage timings are retained where reached. Nested stages overlap; do not sum them. |
| Calls | Actual backend outbound request attempts for TripAdvisor Terra, Mapbox, Mentro generation, Google Hotels and OpenCage. Includes failed attempts; excludes auth/JWKS, gateway-internal work and automatic HTTP redirects. |
| Provider events | Mentro empty-response retries and exhausted empty-response caps. These are separate from AI route-validation retries. |
| AI route validation | Null with a reason: pure-AI/custom route solvers and their retry/fallback loops are not active. No fabricated counts or fallback success. |
| Determinism | Empirical equality of canonical successful output hashes for at least two identical-input runs. Includes selected IDs, ordered stops, dates, costs and route duration. It is not a proof of future determinism. |

Inputs retain both submitted and effective normalized weights plus resolved trip
fields. Candidate identity, ratings, utility, slots and integer coefficients are
snapshotted. Stable SHA-256 hashes ignore provider timestamps and run UUIDs.
The input cohort groups matching inputs/mode/scoring version/revision, so changing
live discovery still contributes to observed spread. The narrower comparison key
also requires the same candidate model/query points. An `OPTIMAL` CP-SAT reference
with a positive score is required for quality percentages; zero optima or mismatched
models are unassessed. Quality percent = 100 × score/reference; gap percent =
100 − quality percent. Means, population standard deviations, min/max, sample
counts, assessed feasibility denominators and output repeat counts are calculated
in the backend. There is currently only one active approach, `cp_sat`.

Metrics use `selection-surplus-v1`. Docker embeds `ROADTRIPS_REVISION` from its
build SHA. Local development should set an explicit revision when collecting
comparisons; otherwise records say `unversioned-local`. Bump the metric version
when changing score/feasibility/hash semantics; never reinterpret older rows silently.

## Migration and recovery

Apply the additive SQL explicitly to the **approved database target before**
releasing the new backend. Runtime does not create tables. `/ready` now requires
the new table; Lab runs fail closed if it is absent. The Neon write gate remains
authoritative. This task applies the schema only to disposable local databases;
it does not migrate production or authorize a manual public deployment.

Use the existing database operator's transaction/migration workflow to execute
`backend/sql/algorithm_lab_runs.sql`. Back up and verify the target first per the
container/database runbooks. `IF NOT EXISTS` makes initial application repeatable,
but does not repair a pre-existing incompatible table. Check columns/indexes after
application. Backend image rollback can leave this additive table in place;
do not drop it or delete experiment data as part of rollback.

`node tests/postgres/run.mjs` validates that disposable schema matches this DDL
and checks real insert/finalize/read, cross-owner isolation, recreation, DB-loss
readiness, backup and restore. The fixture SQL includes this table in the full
dump; restoring into a populated target is refused. Production schema history
and public deployment still require separate verification.
