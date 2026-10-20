# Current release and acceptance

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
