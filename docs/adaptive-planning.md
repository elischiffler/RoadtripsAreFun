# Adaptive discovery and balanced route selection

October 5, 2026; release branch `codex/production-release`, draft PR #34.
This supersedes the old early-30-candidate and nearest-query-slot behavior.
Studio and ordinary chat share `cp_sat`; all new trips use live providers.

## Discovery budgets

For requested attraction count N, baseline driving hours T and road miles M:

| Capacity | Formula |
| --- | --- |
| Sections | clamp(ceil(T / 2), 1, 12) |
| Solver candidates | clamp(6N + 2 sections, 18, 60) |
| Initial nearby searches | min(36, max(2 sections, 3N, ceil(T))) |
| Maximum nearby searches | min(60, max(initial + sections, ceil(M / 10))) |
| Distinct AI-rated places | 2 × solver candidates |
| Raw pool | 3 × solver candidates |

N=0 skips discovery and selection. Initial points are evenly distributed within
equal driving-time sections and queued round-robin. Identity deduplication, the
five-mile radius and provider attraction verification remain authoritative.
Section quotas and available-category variety apply to raw and rating pools;
final quotas rank eligible matches and redistribute spare capacity. There is no
five-retained-results-per-query rule. Provider facts and AI ratings remain distinct.

Each nearby round finishes before its rating IDs are frozen. AI batches contain
at most five verified names. Once ratings finish, search the largest unsearched
interval midpoint in empty sections first, then the least populated sections.
Stop at 3N eligible places with every section represented, or exhausted budgets /
no distinct query coordinates. Retained JSON explains queries, rounds, source IDs,
sparse sections, remaining intervals and stop reasons. It does not claim continuous
coverage. [CP-SAT explanation](cp-sat-explained.md) defines the measured road costs,
quality bound, all K+1 gaps, solver statuses and scheduling limits.

## Dependency barriers and concurrency

The stream retains its private worker event loop. Process limits use threading
permits rather than global asyncio semaphores. Async/sync HTTP clients and
single-flight requests belong to one run and close after real work finishes.
There is no cross-run discovery cache. Completed results merge in frozen order.

| Provider leaf | Per run | Per process |
| --- | ---: | ---: |
| Nearby query | 4 | 8 |
| Mapbox route | 4 | 8 |
| AI rating batch | 2 | 4 |
| Google Hotels HTTP | 2 | 2 |
| Geocoding | 2 | 4 |
| Solver | 2 | 2 (one solver thread each) |

Independent endpoint geocoding finishes before the baseline request. Discovery
rounds finish before rating, ratings before refinement, and final shortlist road
checks before solving. Days remain sequential. Independent room allocations and
hotel details overlap only after their required date/location/listing exists;
room offers are intersected before scheduling continues. Final live road timing
validation precedes itinerary construction and persistence.

Permits apply to individual leaf attempts, not orchestration waiting for children.
Mapbox uses real async HTTP. Synchronous AI/geocoders/solver are offloaded to bounded
threads. Gateway login/refresh is synchronized. Transient operations have three
total attempts; Retry-After is honored and HTTP backoff releases capacity. A
cancelled awaiter does not free a still-running synchronous worker's permit.
Queued work and siblings cancel, late results are ignored, and client closure waits
for unavoidable real thread completion. This does not forcibly abort sync I/O.

Progress sequence numbers and provider counters are thread-safe. Studio shows
actual active/completed counts and “of up to” adaptive limits, plus query/section/
batch retry attribution. Existing safe top/failed-stage diagnostics, presets,
map, itinerary, history and session isolation remain available.

## Persistence and metrics

Existing experiment JSONB stores discovery, candidate road checks, input snapshots,
solver explanation, stage results and attempts; no DDL change is introduced.
`balanced-route-v3` separates average match, quality loss, spacing deviation,
estimated solo detour and actual final extra drive. Current objectives minimize
seconds; historical surplus scores remain historical. Reference comparisons require
identical candidate models and scoring versions. Cost excess supports zero optima;
percentage excess requires a positive optimum. Wall elapsed time, accumulated
provider duration, queue wait, peak calls, API attempts and distinct requests are
separate measurements. Gateway authentication attempts are counted.

## Validation ledger

Pinned Python 3.12.14, requirements and Ruff 0.16.7; Node 24.12.0 and `npm ci`.
Frontend format, lint, 309 tests (90.16% line coverage) and production build passed.
The existing large Vite chunk warning remains. Backend format/lint and 748 tests passed with 87.85% coverage (63% gate
unchanged). The final isolated Docker test image passed all 748 tests with 87.83% coverage,
no network and no hosted credentials. Final source is `c4ce3b6`; the guarded
preview built from that revision passed both smoke tests. Live outcomes appear below.

Controlled-delay acceptance compares identical 12-call provider workloads:
serial 0.573s, concurrent 0.211s (63.2% reduction), unchanged results and call count.
This supports the 30% provider-bound target; it is not a live-trip latency promise.
Tests also cover all six process limits across private loops, per-run caps,
single-flight scope, sibling cleanup, in-flight sync permit retention, synchronized
login/refresh and progress, Retry-After, deterministic out-of-order results,
budgets/quotas/refinement/sparsity, curves/crossings/repeats/zero durations,
quality bounds, endpoint gaps, detours and index-independent scheduling.

A host-only CORS test configuration initially failed because the developer dotenv
omitted the documented loopback origin. Validation supplies the documented five
origins to the test process only; application configuration and the user's running
servers are preserved. Isolated Docker validation supplies no hosted credentials.

Disposable PostgreSQL runs `b9e3b85b5f` and final `927de8999f` passed real CRUD, owner isolation, API/DB
recreation, loss/recovery, backup/restore and populated-target refusal, including
new discovery/selection JSONB records. Source and restore volumes and the private
backup are retained. This proves the disposable schema only; production schema
and migration history remain separate gates. Guarded container preview smoke
passed both tests. No main merge, production deployment or production migration
is included.

## Live preset observations

All nine presets were exercised with fresh live providers during this session.
Five completed; their actual maps and dated itineraries were checked, then opened
again from saved history after browser reload. Three stopped at required Terra
queries with HTTP 429. Sparse reached AI refinement, then Mentro read timeouts /
connection errors exhausted three attempts; its final database save could not be
confirmed. It remains unfinished, not a successful or zero-latency sample.
No mock/replay substituted for these outcomes. Local metric revisions were
`unversioned-local` or `adaptive-terra-fix`, rather than deployed image SHAs.

| Preset | Observed outcome | Delivered / requested | Days / hotels | Quoted USD | Wall seconds | Actual API attempts |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Coastal nature | Completed; saved viewer reloaded | 2 / 2 | 1 / 0 | 0 | 38.03 | 32 |
| Same corridor, culture | Completed; saved viewer reloaded | 2 / 2 | 1 / 0 | 0 | 34.61 | 31 |
| Overnight road trip | Completed; saved viewer reloaded | 0 / 3 | 1 / 0 | 0 | 71.86 | 47 |
| Short single-day | Completed; saved viewer reloaded | 2 / 2 | 1 / 0 | 0 | 57.55 | 31 |
| Medium two-day | Blocked: Terra HTTP 429 | Unassessed | Unassessed | — | 7.51 | 24 |
| Long multi-day | Blocked: Terra HTTP 429 | Unassessed | Unassessed | — | 9.18 | 63 |
| Dense corridor | Blocked: Terra HTTP 429 | Unassessed | Unassessed | — | 6.60 | 26 |
| Sparse corridor | Blocked: Mentro connection failure; final save unconfirmed | Unassessed | Unassessed | — | Unassessed | Unassessed |
| Tight hotel budget | Completed; saved viewer reloaded | 4 / 4 | 2 / 1 | 144 | 141.79 | 104 |

The overnight label did not establish an overnight: all four sections lacked
eligible matches after 21 searches / four rounds, and the rating budget was
exhausted. The empty solver status and 0/3 fulfillment remain visible. Tight
budget used 30 searches / four rounds, retained 23 road-checked candidates and
reported section index 4 sparse, with rating budget exhausted. It selected an
OPTIMAL modeled cost with average match 0.68375 versus best achievable 0.75:
6.625 percentage points of quality loss, within the ten-point bound. Estimated
solo detour was 20.86 minutes and spacing deviation 241.97 minutes, reported
separately from actual final driving. Its verified $144 room quote exceeds the
$60 nightly target by $84; the warning and America/Boise arrival remain visible.

Sparse retained three frozen rating rounds and 15 query observations before the
failure, including adaptive section/query identities. Its last batch had three
total attempts (two read timeouts followed by a connection error); earlier
transient Terra and gateway errors recovered. History subsequently recovered,
but recovery does not invent a missing final result. Interrupted attempts from
local reloads also remain unfinished in history and are excluded from success
claims. A separate local API with a stable session key was used without restarting
the user's development servers.

Observed peaks on successful runs were nearby 4, AI 2, Mapbox up to 4 and geocoding
2; tight-budget Google Hotels peaked at 2. No controlled performance claim is
inferred from these varying live workloads. Long-route distribution, the medium /
dense completed viewers and sparse final coverage still require successful live
reruns after the external blockers clear. All-corridor live acceptance remains
incomplete; PR #34 stays draft. Existing production gates also remain open.

Final edge checks confirm zero requested stops skip both discovery and solver
work, recovered retries retain query/section IDs, and cyclic exception causes
remain bounded. Temporary local live-validation servers are stopped after
acceptance; the user's original development servers and recovery volumes are
preserved. No failed or unfinished live history was removed.
