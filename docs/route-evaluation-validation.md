# Route evaluation validation

Validation performed in an isolated Mac checkout and task branch, based on
catalog PR40 `5ab14e01e0ababd3525093ff67fac7ac29d2bd6f`, re-fetched and verified
before PR creation. The original MyRoadtrip/catalog checkout and catalog branch
were not modified.

## Local checks

- Python 3.12.14; pinned backend requirements and Ruff 0.16.7. Ruff format and
  lint pass. Backend coverage: **899 passed, 4 skipped, coverage above 86%**, above the
  unchanged 63% threshold.
- Node 24.12.0; committed npm lockfile via `npm ci`. Frontend format, lint,
  coverage and Vite production build pass: **315 tests / 39 files**. Coverage
  exceeds all existing thresholds. The existing large-bundle build warning
  remains informational.
- Container smoke: **2 passed** against the guarded local preview in the unique
  `roadtrips-evaluation-preview` Docker project. Only this preview was removed
  afterward. No production keys or services were used.
- Disposable PostgreSQL runner passed schema parity, CRUD/ownership, API readiness,
  recreation/dependency loss, backup/restore and refusal to overwrite a populated
  target. Unique project `roadtrips-crud-5d5226ed38`; source and restore volumes
  remain preserved, with containers stopped, as the existing runner requires.
- Evaluation contracts exercise 30 deterministic scenarios, 10/11/15/20 stop
  boundaries, strict count rejection, 25-coordinate transport capacity, production
  defaults, 100-candidate offline selection, shared real discovery/scheduling/
  timing/itinerary, comparators, socket denial, immutable hashes, missing reroutes,
  final timing and itinerary failures, missing hotels, UNKNOWN, integer rounding,
  hand-calculated gaps/budget/utility, local terminal rows and synthetic plot exclusion.
- Existing public replay rejection, visitor/owner scope and Lab storage begin/
  finalization failure tests remain passing. No new replay endpoint or public
  experimental algorithm was added.

The public API's old zero-stop test was replaced with explicit 422-before-provider
validation. Algorithm/auth integration fakes now use valid positive trip inputs;
internal zero-stop planner/scheduler checks remain. Explicit JSX/JS source imports
resolve the catalog UI's case ambiguity on the Mac without changing attribution.

The first container CI exposed that the slim test image deliberately has no Git.
The evaluator now records a source snapshot hash and unavailable Git metadata
for archives/containers, preserving an explicitly supplied revision without
claiming a clean checkout. A regression test covers that environment; all 37
evaluation contract tests passed in the Linux test image with `--network none`.

## Exact-head CI

The draft PR targets `codex/neon-places-catalog`. GitHub's checks on the final
pushed head are the authoritative cross-platform/container evidence; their status
and final SHA are included in the task delivery. Local counts above describe the
same implementation, with no reduced coverage thresholds.

## Data and live gates

The machine-readable core matrix and manifest schema are committed. Campaign
outputs are local, ignored artifacts. The data-gate campaign records all 30
expected pipeline cells; absent corridor captures are blocked with NOT_RUN,
not omitted, infeasible or assigned utility zero. It emits no primary measured
figures. Solver unit graphs remain explicitly synthetic contract tests.

Real 100-place suites require sufficient usable imported corridor coverage and
immutable generation/rights/arrival evidence plus captured ratings, direct/solo/
final roads, dated room-night offers and timezone lookups. The last catalog
checkpoint's 12 local Boulder places do not satisfy these gates. No new capture,
paid live run, Neon activation, migration, credential change, merge or deployment
was performed. Five-day coast-to-coast and its 15-stop cells remain scenario
hypotheses until those measured pipeline results exist.
