# Route evaluation validation

## October 16 current-main integration

The readiness branch preserves evaluation head
`2270815513f71a4a1fc58323898854f3bc1ae9c3` and incorporates main
`e9129a7551ef8c07405a9bf7552f6303765365af` without rewriting either history.
Conflicts in selection, metrics, final routing and API tests retain current
positive-match eligibility, source calendars, calendar retries and explicit
invalid-rating errors, together with evaluation instrumentation and shared limits.

The frozen provider filters requested-trip calendars before its 60-place quota.
Frozen selection tracks apply the same trip-date eligibility. The recorded full
pipeline retries selection after actual-road calendar conflicts with the same
request-local caches and exclusions as production. Regression controls cover a
low positive match, zero utility, unknown calendars, 60 expired venues ahead of
a usable destination, final-road reselection and all three selection methods.
These controls are synthetic unit evidence, not measured trip-quality results.

Current commands and exact pushed-head CI are recorded in PR #41. Local full
suites use the pinned backend requirements and Node 24 with the committed lockfile;
coverage thresholds are unchanged. Historical results below retain their original
source and platform scope and do not establish current-head Windows/browser or
live-provider acceptance.

The actual nine Studio preset inputs are read from `preset_catalog()`, preserving
all dates, occupancy, interests and optional evening fields. This checkout has no
real route-evaluation capture manifests. Preset input validation can pass while
all nine provider evaluations remain blocked before solver work. The 30-scenario
core campaign separately records every blocked cell. No teaching fixture is
substituted for those trips. Full real-data evaluation needs reviewed captures of
ratings, exact roads, room-night hotels and timezones, plus generation-aligned
rights/access evidence. Live provider calls require approved execution/spending
scope; none were made in this preparation. Saved trips and production data are
untouched. Later catalog totals do not supply these missing captures.

## Historical validation

Validation performed in an isolated Mac checkout and task branch, based on
catalog PR40 `5ab14e01e0ababd3525093ff67fac7ac29d2bd6f`, re-fetched and verified
before PR creation. The original MyRoadtrip/catalog checkout and catalog branch
were not modified.

## Completion update

The remaining v2 changes were preserved in commit `b233454` after the Mac
reconnected. The outage-era Linux test image passed 919 tests with four skips;
the Mac run's only failure was a worker deadline during the transport outage.
The timeout was kept as a harness failure, never solver infeasibility. Fresh
verification after reconnecting supersedes that interrupted run: **922 backend
tests passed, 4 skipped, 86.11% coverage**; **320 frontend tests passed** with
format/lint/build checks. Exact-head CI and final Linux/container evidence are
recorded in the delivery.

Reviewed access/provenance, per-persona hotels, preparation tools, paired reports,
workload/extended-day diagnostics, resource/dwell measurements and method-separated
Lab charts are implemented. The schemas and exact exchange are documented in
[the v2 handoff](route-evaluation-v2-handoff.md).

The updated catalog base `b0ddee3b8321a8e135bbe2079bbfde46ac96812d` was fetched
after saving local work. A non-checkout `git merge-tree` succeeded without
conflicts. No catalog branch or original checkout was modified; no rebase/merge
was performed. The evaluation exchange honors the existing mixed source metadata.

## Original milestone local checks (992bf56)

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
final roads, dated room-night offers and timezone lookups. The current reported 400-place mixed local checkpoint has 331 pending access reviews and does not establish 100 usable places per required corridor. No new capture,
paid live run, Neon activation, migration, credential change, merge or deployment
was performed. Five-day coast-to-coast and its 15-stop cells remain scenario
hypotheses until those measured pipeline results exist.
