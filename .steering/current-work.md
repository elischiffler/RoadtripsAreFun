# Current release and acceptance

## Inspected source and delivery

October 5, 2026 (America/Los_Angeles): this refresh uses merged main
`56ac6dbd3eccbd03e105385cf5561582376c0b17`, fetched from the repository remote.
The original feature checkout is preserved; documentation changes use a separate
task branch based on main.

- [Release PR #34](https://github.com/elischiffler/RoadtripsAreFun/pull/34)
  merged as `c5ec69fe3d025d5dd4a3720a5f71dfe0a92bfd61`.
- [Deployment PR #38](https://github.com/elischiffler/RoadtripsAreFun/pull/38)
  merged as `56ac6dbd3eccbd03e105385cf5561582376c0b17`.
- The earlier shared draft [PR #26](https://github.com/elischiffler/RoadtripsAreFun/pull/26)
  is closed. Its former release blockers are not evidence that the current main
  release is still a draft.

`docs/release-consolidation.md` retains branch-integration history.
The previous dated context snapshots remain available in Git history; their
branch tips and pending-merge claims are superseded by this inspected main.

## Implemented capabilities

| Capability                                                                           | Authoritative owner / contract                                                                                                             |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Canonical CP-SAT default and backend-owned owner eligibility                         | `backend/app/routing/registry.py`, `selection.py`; `docs/owner-routing-settings.md`                                                        |
| Adaptive section discovery and bounded candidate pools                               | `backend/app/routing/discovery.py`, `sources/persona_candidates.py`; `docs/adaptive-planning.md`                                           |
| Profile contributions, measured detours, quality bound and actual solver diagnostics | `backend/app/routing/profiles.py`, `cp_sat_selection.py`, `planners/cp_sat.py`; `docs/cp-sat-explained.md`                                 |
| Separate local scheduling, dated room quotes and final road validation               | `backend/app/routing/cp_sat_scheduler.py`, `travel_timing.py`, `sources/google_hotels.py`; `docs/travelers-and-hotel-occupancy.md`         |
| Validated trip extraction, endpoint confirmation and completion/retry                | `backend/app/agent/extraction.py`, `trip_profile.py`, `location_confirmation.py`, `tool_dispatcher.py`                                     |
| Cognito session renewal and bounded verifier-rejection replay                        | `frontend/src/services/session.js`, `protectedRequest.js`; `docs/session-refresh.md`                                                       |
| Visitor Studio access independent of account authentication                          | `backend/app/routers/studio.py`, `frontend/src/services/studioSession.js`; `docs/studio-access.md`                                         |
| Live-only presets, streamed progress, stage data, safe failures and attempts         | `backend/app/routers/algorithm_lab.py`, `studio.py`, `backend/app/routing/runtime.py`; `docs/studio-progress.md`, `docs/studio-retries.md` |
| Scoped experiment history and saved route/itinerary results                          | `backend/app/crud/lab_runs.py`, `backend/sql/algorithm_lab_runs.sql`; `docs/algorithm-run-history.md`                                      |
| Checked main deployment, stale-run rejection and verified health response            | `.github/workflows/deploy-ec2.yml`, `scripts/check_deployment.py`, `scripts/request_deployment.py`; `docs/ec2-deployment.md`               |

Bare filenames in a table cell share the preceding module's parent directory.
The Studio UI remains in `frontend/src/pages/AlgorithmLab/`; the component's name
does not imply that `/algorithm` remains the current page or that visitors need
a Cognito account. New API runs accept only `mode: "live"`; the storage schema's
historical `replay` enum does not enable replay requests.

## Verified release evidence

[Deploy EC2 run 37411743425](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/37411743425)
succeeded after all four required main CI workflows passed. Fresh read-only host
inspection found a healthy `roadtrips-neon-api-1` with the exact main revision
label and matching recorded release. Public HTTPS checks passed for `/health`,
`/ready`, `/algorithms`, Studio anonymous rejection, session unlock,
session-authenticated presets/history and production frontend CORS.

Initial automatic startup failures rolled back to the prior healthy image.
The shared host's source-permission fix is merged in
[hosting-ops PR #13](https://github.com/elischiffler/hosting-ops/pull/13).
The successful retry demonstrates the corrected deployment path; it does not
prove every provider journey. The shared host's implementation and recovery
remain owned by its [runbook](https://github.com/elischiffler/hosting-ops/blob/main/docs/ec2-deployments.md).

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
