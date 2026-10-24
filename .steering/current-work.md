# Current release and acceptance

## October 24 permanent ratings restoration

At the user's direction, all 36 re-rated places were restored exactly to their
original attribute profiles and provenance; three new reserves retain their first
ratings. Stored place profiles are now permanent by source identity, independent
of persona, metadata, prompt/model version and legacy expiry. Database failures
and corrupt stored ratings stop estimation rather than regenerate ratings. The
v3-only nature study below is withdrawn; its historical exports remain intact.
Replacement `cffa789a-bd7c-4ec0-8be0-8223e1cff9bc` completes 24 captures and
5,040 OPTIMAL trials with zero AI rating calls. All twelve Entertainment baseline
means match the original corridor study. See the [current study](../docs/research/2026-10-24-restored/README.md)
and [rating persistence](../docs/place-trait-cache.md).

## October 24 nature coverage and rating-audit replacement

The active catalog now has 611 places and 192 calendars, adding three reviewed
CDFW coastal reserve trail arrivals while preserving every parent row. The
destination-specific v3 rubric refreshes all 39 captured place ratings via the
configured gateway, with actual model provenance persisted. Replacement study
`d0aee85d-bd6a-49c3-a74a-c5b5630549bf` completes 24 captures and 5,040 trials
with the unchanged bell corridor, 15-second limit and 30 seeds. All 720 baseline
trials are OPTIMAL; mean utility rises from 0.255999 to 0.409306 (+15.3307 points).
Short nature selections now use the reserve trails (three-stop mean 0.69). Across
all settings, 4,740 trials are OPTIMAL and 300 zero-loss trials are INFEASIBLE
because conservative integer rounding makes their exact bound unattainable.
Retain those outcomes in the paper. The earlier corridor study below is superseded.
See the [replacement evidence packet](../docs/research/2026-10-24-nature/README.md).

## October 24 bell-shaped research corridor

The user replaced sampled route discovery with deterministic, uncapped catalog
membership. Research now checks every admitted daytime place against the initial
route's full polyline. A normalized Gaussian gives 5-mile endpoint widths and a
25-mile midpoint width by default; widths and sigma are frozen in schema-v4
protocols. The same route pool, persisted traits and measured solo detours are
reused across personas, requested stop counts and all solver settings/seeds.
Ordinary app discovery retains its existing behavior. The new campaign
`514e8250-12c7-4a22-bd2d-e550523fc7dc` is complete: all 5,040 trials are OPTIMAL,
using 10–23 eligible places per route and 36 distinct captured identities.
Baseline mean utility rises from 0.403435 to 0.529637 (+12.6202 points); all
requested counts are fulfilled. See the [current audited packet](../docs/research/2026-10-24-corridor/README.md).
The previous schema-v3 results below are superseded for the paper and must not be
combined with the revised protocol.

## October 24 real-data selection research

At the user's revised scope, research performs attraction selection only. The
full-trip campaign was stopped and removed from active stores after a recovery
copy. The new protocol collects 24 real pre-selection pools without hotels,
scheduling, itinerary construction or final routing, then runs 5,040 controlled
CP-SAT trials (15 seconds, cap 60, 30 seeds, seven paper sweep settings). Research
financial fields and the tight-budget scenario are removed. Candidate-pool versus
selected utility and percentage-point change are recorded and plotted.

Mentro PR #6 was merged with owner authorization after CI and its checked-main
deployment passed. The gateway returns valid responses with
`mentro:Groq/openai/gpt-oss-120b` provenance. Traits retain actual upstream model IDs
under a new cache contract. Frozen offline providers explicitly disable the live
trait cache; six older fixture entries were backed up and removed. The three
historical studies were also removed after verified recovery copies.

See [selection protocol](../docs/studio-research.md) and
[validation](../docs/container-validation.md). Planned counts are not empirical
completion claims. The revised capture path passed a real four-candidate preflight
without full planning, plus frontend/backend checks; the new study freezes that
verified implementation.

Selection-only study `05fc366d-4623-4467-ba06-a93911147993` is complete and verified
in PostgreSQL: 24 captures and 5,040 OPTIMAL solver trials. Actual pools contain
4–8 eligible candidates, 20 distinct places overall. Default mean utility changes
from 0.417234 to 0.479866 (+6.2632 percentage points); ten scenarios have fewer
eligible places than requested. These small-pool results do not establish
60-candidate scaling or full-trip feasibility. See the [audited results and paper
packet](../docs/research/2026-10-24-selection/README.md).

## October 22 cloud catalog reconciliation

The reconciled develop tree preserves the Mac research/session-cache work and
all twelve exported cloud commits through `5e139b5`. Historical research contains
221 T2 browse identities, with 133 retrospective acquisition holds now enforced
by pinned code/data across replay, browse/routing reads, staging, activation and
recovery targets. The other 88 are not blanket cleared; zero new T3 conversions
or live imports are claimed. Earlier 93 USFS records remain outside this audit.
Private typed-replay originals and current live-parent reconciliation are still
required for data release. The app continues using its configured Neon database.
See [integration boundaries and counts](../docs/catalog-cloud-integration-20261022.md).

## October 19 automated attraction imports

Develop now includes command-driven NPS/USFS acquisition, automatic test-route
capture, offline replay and conservative native-identity calendar bindings.
The imports add five source-backed visitor arrivals along SF–Boise and
SF–Chicago, plus missing hours for 35 existing places nationally: 608 places,
189 calendar companions. All 603 parent rows and 149 prior companions are
preserved. Existing calendars, including expired or held records, are not renewed.
See [commands, source rules, measured coverage and release boundary](../docs/catalog-automated-import.md).
The final 608-place generation is active after the release owner confirmed the recent
verified off-host backup in this chat. That recovery confirmation is owner
attestation, not an independent host inspection. The prior 603/607-place generations
and frozen rollback receipts are preserved. This work does not release main or
deploy an application.

## October 20 reusable attraction traits

Live attraction discovery can reuse per-place estimated attribute JSON from
PostgreSQL across trips and restarts. It rates only misses and recalculates
utility for the current persona. Context/version changes invalidate entries;
estimates expire after 90 days. Source facts and live eligibility remain
separate. The additive local migration and opt-in are enabled; deployments stay
disabled by default. See [trait persistence](../docs/place-trait-cache.md).

## October 20 research database persistence

Research studies now mirror from the private local SQLite execution queue into
additive PostgreSQL study/run tables. The local configured Neon database has the
explicit migration and backfill; API startup sync is a separate opt-in, default
off for deployments. Fresh browsers can open saved results after Studio access,
without private per-study keys. Shared reads grant no run controls. CP-SAT outcomes
show Optimal, Feasible, Infeasible and Unknown. The running worker and frozen
protocols remain intact; SQLite and exact source archives are retained for
recovery. See [persistence and access](../docs/studio-research.md#postgresql-results-and-cross-browser-access-october-20-2026).

## October 20 standard solve limit

The shared CP-SAT default is now fifteen seconds for new interactive runs and new
Studio research plans. Existing studies keep their frozen five-second plans and
results. The October 20 rerun is a new 6,300-case solver-only batch at fifteen
seconds, covering the full matrix without repeating live pipeline calls. A local archive
of the original backend source matches the active campaign's source hash and is
preserved for recovery. See [research protocol](../docs/studio-research.md#standard-solve-limit-october-20-2026).

## October 19 develop integration

Studio's **Research** page now defines 30 trip/persona/stop-rate combinations,
prioritizes 6,300 controlled CP-SAT trials and then runs 300 fresh live trips.
The hundred-candidate solver dataset is explicitly synthetic and remains separate
from provider-trip results. Durable local campaigns, source identities, per-run
records, incremental charts and CSV/JSON exports are described in
[the research protocol](../docs/studio-research.md). Batch execution is an explicit
backend opt-in; no production mount, schema migration or release is added.

PRs #56 (chat retirement), #55 (standalone guided planning) and #51 (visit
estimates and arrival/leaving timing) are integrated into develop at their exact
latest CI-validated heads. Combined local checks pass; this is integration
verification, not an independent production release approval. Saved trips remain
at `/trips`; `/chat` redirects there. `/plan` uses retained structured APIs rather
than the removed chat dispatcher. Studio's third results tab is **Trip stats**:
compact measurements and bars replace raw stage JSON and solver explanations.

Studio History now opens a popup and restores saved trips into the workspace.
Tab-scoped inputs/results/selected tabs survive reload and navigation; active
visitor jobs continue in the single API process and reconnect by UUID without
repeating provider work. API restarts interrupt active runs. See
[workspace lifecycle and limits](../docs/studio-access.md#workspace-and-history-popup-october-19-2026).
Place cards and map popups omit Sources links, visit-estimate tags and repeated
place-type labels. Numbered route-list dots match the map's attraction/stay colors.
Arrival/leaving use two compact clock columns with short dates and time zones;
overnight dates and DST offsets remain distinguishable, with full timestamps
available to assistive technology and on hover.
Generation shows one animated current activity; detailed progress remains recorded.
Trip stats keeps attraction counts, match estimates, driving comparisons, longest
driving gap and planning/selection time. Source metadata and research measurements
remain stored; the public attribution page and map-provider attribution remain.

See [integration heads, compatibility fix and validation](../docs/studio-stats-integration.md)
and [visit estimates](../docs/visit-duration-estimates.md). Shared AI, source
calendar holds, frozen offline itinerary facts and historical metric meanings
remain. Current measurements use `balanced-route-v5`; live provider/estimate
quality and production acceptance remain separate.

## Earlier inspected source and delivery

October 16, 2026 (UTC): isolated task checkout based on main
`e9129a7551ef8c07405a9bf7552f6303765365af`. This update preserves the earlier
PR #39 history and incorporates current main without changing application code.

Studio/release PR #34 and deployment PR #38 are merged; old draft PR #26 is
closed. Main also contains catalog PRs #40, #42, #46, #47, #48 and #49, the
Tripadvisor removal in #43, and positive attraction eligibility in #45.
The exact head of old [PR #44](https://github.com/elischiffler/RoadtripsAreFun/pull/44),
`5f17b994f719b9e9d342bd0d17f1bde9e339ffa6`, is an ancestor of main through #46,
including its portable evidence filenames. It is closed as superseded.

[PR #41](https://github.com/elischiffler/RoadtripsAreFun/pull/41) remains a separate
draft for offline evaluation and shared attraction limits. Its current-main
integration preserves calendar-aware discovery and final-route retries. Code
readiness does not supply its missing real-corridor captures or benchmark results.
The separately assigned AI visit-duration/timing display work is outside #41.

Catalog corrections, independent review and release-owner coordination remain
pending before any further main merge. This document records source state, not
independent approval or a claim about the running catalog/revision. Re-fetch
before integration; active release work can advance main.

## Implemented capabilities

| Capability                                                                           | Authoritative owner / contract                                                                                                             |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Canonical CP-SAT default and backend-owned owner eligibility                         | `backend/app/routing/registry.py`, `selection.py`; `docs/owner-routing-settings.md`                                                        |
| Adaptive section discovery and bounded candidate pools                               | `backend/app/routing/discovery.py`, `sources/persona_candidates.py`; `docs/adaptive-planning.md`                                           |
| Profile contributions, measured detours, quality bound and actual solver diagnostics | `backend/app/routing/profiles.py`, `cp_sat_selection.py`, `planners/cp_sat.py`; `docs/cp-sat-explained.md`                                 |
| Separate local scheduling, dated room quotes and final road validation               | `backend/app/routing/cp_sat_scheduler.py`, `travel_timing.py`, `sources/google_hotels.py`; `docs/travelers-and-hotel-occupancy.md`         |
| Shared preference extraction and validated trip models | `backend/app/agent/extraction.py`, `trip_profile.py`; conversational orchestration retired |
| Cognito session renewal and bounded verifier-rejection replay                        | `frontend/src/services/session.js`, `protectedRequest.js`; `docs/session-refresh.md`                                                       |
| Visitor Studio access independent of account authentication                          | `backend/app/routers/studio.py`, `frontend/src/services/studioSession.js`; `docs/studio-access.md`                                         |
| Live-only presets, streamed progress, trip statistics, safe failures and attempts         | `backend/app/routers/algorithm_lab.py`, `studio.py`, `backend/app/routing/runtime.py`; `docs/studio-progress.md`, `docs/studio-retries.md` |
| Scoped experiment history and saved route/itinerary results                          | `backend/app/crud/lab_runs.py`, `backend/sql/algorithm_lab_runs.sql`; `docs/algorithm-run-history.md`                                      |
| Checked main deployment, stale-run rejection and verified health response            | `.github/workflows/deploy-ec2.yml`, `scripts/check_deployment.py`, `scripts/request_deployment.py`; `docs/ec2-deployment.md`               |

Bare filenames in a table cell share the preceding module's parent directory.
The Studio UI remains in `frontend/src/pages/AlgorithmLab/`; the component's name
does not imply that `/algorithm` remains the current page or that visitors need
a Cognito account. New API runs accept only `mode: "live"`; the storage schema's
historical `replay` enum does not enable replay requests.

## Dated release evidence

The original October 5 refresh recorded
[Deploy EC2 run 37411743425](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/37411743425)
and host/public checks against then-main `56ac6db`. The original scope remains in
Git at `c00cc1c6ca828fdcb8ab1c163d84667c770aa3d1`; it is not fresh evidence of
current runtime state. Maintained catalog release reports are in
[the catalog contract](../docs/neon-places-catalog.md) and
[October 16 source growth](../docs/catalog-growth-20261016.md).

This refresh verifies source paths, links, patch scope and repository APIs only.
It did not connect to production databases, change catalogs, inspect secrets,
run provider trips, perform browser acceptance or deploy. Successful CI status
must be checked on the exact eventual merge candidate.

## Remaining evidence boundaries

This refresh did not run a new complete provider trip or itinerary, a two-account
Cognito journey, a browser reload/persistence rehearsal, an off-host backup restore,
or verify the currently served frontend's exact revision. Earlier live preset and
recovery reports retain their recorded code/target/date scope. Database readiness
checks table presence, not every column or migration history.

A joint attraction/time/budget/hotel optimization model remains a separate product
change. Current CP-SAT selection must not be described as that joint model.
Future schema changes need an approved target, reviewed migration and recovery
plan; merging a deployment workflow does not authorize arbitrary data migrations.
