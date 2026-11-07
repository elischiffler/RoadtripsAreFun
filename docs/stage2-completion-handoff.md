# Stage 2 completion candidate — November 7, 2026

This document tracks the local integration after reviewed PR67 head
`3a5494d5e7b1d7121982d86522e66045b2af3cb9`. Earlier verification and the four
original feature heads are recorded in `stage2-integrated-handoff.md`; that report
is a historical checkpoint, not evidence for the newer combined head.

Production remains held while final combined journey and hosted CI checks finish,
and until the migration and release acceptance boundaries below are resolved. No GitHub main merge, hosted database mutation, live provider/Mentro
trip or production deployment was performed by the integration work below.

## Reviewed histories retained

| Lane                                                       | Exact reviewed head                        | Local integration                |
| ---------------------------------------------------------- | ------------------------------------------ | -------------------------------- |
| Selected route-pin branding and themed authentication      | `f5f3ab33e68bf65f7f92ce564856f14cc7fea24f` | Retained from the parent's merge |
| Source-reviewed place context and credited local imagery   | `18fa070f3b8e911f833c5cf9a24227fe4c966266` | Retained from the parent's merge |
| Complete one-day candidate choice and daily rhythm backend | `befbefce61c089635c0cd7690ab8217c9a544bb4` | No-fast-forward merge `9fb1f42`  |
| Trip sharing and safe saved-mode display                   | `fa8c76e290605b4d9ad3f0012c9c72d2cda65591` | No-fast-forward merge `75d32af`  |
| Reconciled foreground arrival tracking                     | `cd41ae4aba7a1c5ca6fae7ca8407fc61fe0f6282` | No-fast-forward merge `cbaddaf`  |
| Onboarding, candidate map and daily rhythm controls        | `1c6b51749ff5abfd8a1f7d13eef66b6b879f5966` | No-fast-forward merge `d07f6f7`  |

The initially verified combined application checkpoint is
`d07f6f75fc3b099e73ad120ffbafdc57df5ba2b2`. The final native journey checkpoint is
`48204ece680feb2a10aff6f4692976717cf5a754`, adding the independently reviewed
sharing readiness prerequisite and shared-only Home entry. The latter preserves
owned-route priority, checks connected trips only after a verified empty owned
list, rejects stale account results and offers recovery on lookup failure. Its
reviewed two-file head `bd7015f8467727e63324600987a9a8c715a3f2f2` was merged without
conflicts; 15 owner and 10 independent focused tests passed.
The reconciled arrival merge retains both original implementation parents rather
than dropping either history. Original feature branches remain untouched.

## Implementation boundaries

The one-day backend verifies actual final roads, visits, published opening waits,
reserved meal breaks and local driving availability before offering eligibility.
The limit is strict aware UTC elapsed time below 12 hours. The road-only preview
is not proof. Explicit request registration, owner/input binding, bounded cache,
fixed error codes, idempotent reuse and cancellation prevent an uncertain response
or cache miss from silently repeating model work. One-day requires no hotel
provider or room occupancy; allowing overnights retains the existing room/provider
contract and does not force a hotel where none is needed.

Daily rhythm supports one cyclic driving block, one cyclic sleep block and rest
gaps. Night driving can cross midnight for a fully validated one-day candidate.
Unsupported hotel arrival/daytime sleep arrangements fail explicitly instead of
fabricating accommodation availability. Actual hotel idle time accounts for the
supported rest/sleep intervals. Full hotel meal breaks must fit awake intervals
and their meal windows; breakfast can move to an awake interval or defer to the
next drive without moving sleep or restart. Impossible combinations return a
meal-scheduling conflict. The legacy no-rhythm hotel clock remains unchanged.
A saved one-day route is revalidated on itinerary
rebuild and edit preview; copied proof metadata is never authority. See
`one-day-candidates-and-daily-rhythm.md` for exact endpoint, policy and limitation
contracts.

Place context is optional reviewed display data outside physical stop dictionaries.
It is attached after authoritative admission and timing, without changing source
facts, calendars, registry pins or persona ratings. Missing context has no model or
network fallback. See the place-context source registry and its review handoff.

Arrival assistance uses one foreground tracker and account/trip/session guards.
The reconciled flow retains strict dwell/accuracy/closest-target checks, handles
visibility and departure state, and shares explicit visit/Undo persistence with
scoped revision checks. No physical GPS or background tracking acceptance is
claimed. See `foreground-arrivals.md`.

Sharing uses its own reviewed minimal projection and member/owner boundaries.
Actual rest/sleep rows and literal trip mode can be shared; raw recurring policy,
proof, inferred preferences, chat history and private arrival state are omitted.
See `trip-sharing.md` and `trip-sharing-validation-20261107.md`.

The automatic merge preserved `Route.place_context`, `trip_mode` and proof fields,
both candidate and sharing routers, itinerary context refresh and mode validation.
No hand-written conflict resolution was needed for the backend/arrival merges.
The sole onboarding conflict combined the exact reviewed candidate and sharing
protected-request allowlists, preserving verifier classification, retry counts,
sharing/session return paths and safe return-path validation. Independent source
review approved this combined application checkpoint.
Compared with PR67 head `3a5494d`, the exact blobs for `catalog/hold_resolution.py`,
`catalog/admission.py` and the frozen evaluation scenario fixture remain unchanged;
no path under `backend/data` changed. The only additional catalog paths are the
reviewed optional place-context module and its display registry.

## Verification scope

- Backend one-day lane: 2,848 full tests passed, 151 skipped, 81.83% coverage.
  After one small independently reviewed shared-clock guard, 109 focused tests
  passed. Absent-rhythm serialization preserves the exact old policy fingerprint
  and frozen evaluation fixtures; only the new absent field is omitted.
- Sharing lane: 2,817 backend and 492 frontend tests passed, with focused tests on
  the final mode-label change and actual signed local PostgreSQL acceptance.
- Arrival lane: 523 frontend tests, final 69 focused frontend cases, 27 backend
  cases, formatting, lint, build and mocked browser acceptance passed.
- Onboarding lane: 495 full frontend tests passed before bounded final visual and
  recovery changes; 97 final focused tests, formatting, lint, build and two mocked
  browser journeys passed on the final reviewed head.
- Combined native browser/API/disposable-PostgreSQL journey passed on `d07f6f7`,
  including actual request registration, streamed complete candidate assessment,
  explicit one-day confirmation, save/edit/reload, visit CAS, profile/car settings,
  authentication recovery, responsive widths and expired-departure rejection.
  The real computed candidate elapsed time was 18,000 seconds including meals;
  assessment left SQL trip count zero and progress below completion. Cached
  assessment/confirmation and cancellation prevented model replay. Flexible-mode
  missing occupancy returned 422; valid zero-hotel confirmation reused the pool.
  Final fixture counters: solver 3, ratings 4, durations 2, gateway 6, hotels 0,
  stored trips 1; no prohibited network calls or unexpected errors.
- Frozen combined `d07f6f7` backend offline coverage: **2,891 passed, 163 skipped,
  81.62% coverage**, 109 seconds.
- Combined frontend: **591 tests passed across 75 files**, 92.65% lines, 87.68%
  branches and 89.47% functions; formatting, lint and production build passed.
  No frontend source changed during this run. Exact-head hosted CI remains
  pending.
- The subsequent bounded release-readiness delta passed 47 focused offline tests
  plus changed-file Ruff formatting/lint. It makes readiness depend on sharing
  prerequisites without changing liveness, authentication, migrations or data.
  Independent source review and **17 actual disposable PostgreSQL tests passed**:
  read-only endpoint connections, effective-role privileges, missing/malformed
  schema, closed connections and owned CRUD independence. Each of the eight
  privileges was revoked separately; a SELECT-only effective role was rejected
  despite privileged session_user. Temporary roles/schema changes were restored
  and all fixture resources removed. The PostgreSQL CI runner explicitly collects
  these cases after the existing active-catalog fixture.
- Final frozen `48204ece` complete native journey **passed**, including a second
  synthetic participant using the real Cognito SDK against local JWKS/token
  fixtures, actual sharing link/connect endpoints and PostgreSQL, shared-only
  Home entry and read-only rendering. Empty-account and saved-owner Home paths
  also passed. The participant acquired no owned trip, sharing left the owner
  trip unchanged and the entry checks added no model work. All primary candidate,
  cache, flexible-mode, CAS/edit, settings and expired-date assertions remained
  strict and passed. Temporary services and dependency link were removed.
- A final offline integration probe found breakfast scheduled during explicit
  hotel sleep. The bounded new-rhythm-only correction passed **116 focused tests**,
  including 42 frozen evaluation cases, actual hotel clocks, rebuild/edit previews,
  estimated hotel scheduling, feasible awake breakfast, post-restart deferral,
  impossible-window conflict and unchanged legacy timing. This application delta
  follows the successful `48204ece` native journey and needs final exact-head CI;
  the native zero-hotel fixture is not evidence for real hotel/provider behavior.
- Readiness app delta is committed as `3b313fc505b6a4eda15de5fb0753349031158a54`;
  the complete candidate journey gate is committed as `577a614`. The broad test results
  above predate the bounded readiness and shared-only Home follow-ups; the final
  native journey includes both. Final exact-head CI must cover the final tree.

The mandatory journey uses the actual registration → complete assessment →
explicit mode confirmation pipeline, with synthetic external provider leaves and
real local signed API, scheduling and PostgreSQL persistence. Eligibility comes
from the actual endpoints; no fixture proof is synthesized. Its temporary
services and dependency link were removed after the run. Multi-account
sharing/security remains covered by the actual disposable PostgreSQL lane.

## Release and preview boundary

The additive sharing migration is checked in with rollback and validation notes.
It has **not** been applied to production. The normal disposable schema includes
it for local/CI acceptance; successful local SQL does not establish hosted schema
readiness. The complete-release `/ready` guard requires both sharing tables,
11 required column names/types and each individual CRUD privilege through the
actual application role. It uses only read-only checks and fixed 503 responses;
it does not attest foreign keys, indexes, backup/recovery or account acceptance.
Keep the parent-coordinated backend/migration-before-frontend order.

A Vercel frontend preview can still point at production backend revision
`42d5068bb4c8804a8024df0e4463fb05e0a7e275`, which does not have the new candidate
or sharing APIs. Such a preview is not evidence of a working end-to-end release.
The actual combined local static/browser/API/PostgreSQL journey and four hosted
workflows on the final combined head remain required. No preview environment or
protection change, extra public service, direct main push or approval bypass is
part of this integration.

Real Cognito, physical-device arrival behavior and the separately approved single
post-deployment live Mentro/provider check remain distinct acceptance boundaries.
That live check is unused and requires an authorized application session after a
coordinated deployment. No previously denied Neon test is retried here.
