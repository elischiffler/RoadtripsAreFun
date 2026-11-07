# Stage 2 integrated candidate (November 7, 2026)

This is a local integration candidate for review, based on freshly fetched develop
`8284b95543e28c810327e0367b11335515a31fff`. It preserves the focused production
planning fixes, owner authorization, date/error contracts, catalog pins and the
mandatory offline authenticated journey gate. It is not a production release.

## Integrated histories

All four reviewed feature histories are retained with local non-fast-forward merges:

| Feature                                                   | PR  | Exact integrated head                      |
| --------------------------------------------------------- | --- | ------------------------------------------ |
| Actual reserved meals and shared AmountControl            | #61 | `cb8600a6bfec2106818f0d2fd1249559670f1895` |
| Compact adaptive setup and optional comparisons           | #62 | `7c5fb5f7c8052dc3af74c4695683811e140cb788` |
| Saved-trip workspace and validated itinerary editing      | #63 | `17e7094747ca778d4d4a1f2355c094ed0ef9566d` |
| Settings, reusable profiles and trip-specific car editing | #65 | `18911f73a9a636a8ba4dd2953149cde46b8f2858` |

The combined merge checkpoint is `900b37e`; subsequent integration fixes and
verification are recorded in this branch history. Original PR handoffs describe
their historical isolated checks. This document owns the combined candidate's
scope and remaining acceptance boundaries.

## Conflict resolution and review fixes

- Streamed errors preserve both fixed departure guidance and the bounded typed
  meal-conflict explanation, only for their expected 422 status. Provider error
  details remain redacted.
- Trip setup retains percentage progress, compact responsive stages, optional
  comparisons, car-question removal, the shared precise AmountControl, explicit
  profile loading and the save-after-trip notice. Existing supplied car data and
  old drafts remain supported.
- The protected request allowlist combines route-edit, profiles and scoped car
  APIs. It preserves the existing bounded verifier-rejection retry policy.
- Reusable profile autosave stores only traveler-stated/manual interest weights.
  The comparison-derived vector remains private; actual trip generation keeps its
  existing 50/50 blend. Settings uses shared AmountControl for profile interests.
- Derived meal reservations are validated when admitting runtime catalog rows;
  original source facts, hashes, hold markers and pinned registries are unchanged.
  Itinerary rebuild recomputes reservations instead of trusting saved intervals.
- Repeated modern CREATE requests for the same planning UUID retain the existing
  durable trip and log. An exact retry succeeds; a changed saved version returns
  a distinct conflict, keeps the ID and asks the traveler to reload instead of
  blindly retrying or allocating a duplicate trip. Legacy null-ID creation retains
  its compatibility behavior.
- Route edits use a server-issued opaque revision of exact stored trip JSON,
  checked after an owner-scoped `SELECT ... FOR UPDATE` before segment writes.
  Route-only saves preserve car, unrelated trip fields and logs. Modern visit/undo
  writes use the same guard with presentation-only updates; a stale car/route
  snapshot returns 409 without overwrite. Successful saves refresh the revision.
  Each ChatData update rotates server metadata so coordinate-only segment writes
  also invalidate prior snapshots. Replacing a long route prunes only obsolete
  segments for that verified owner/chat/route; new final-route storage identities
  preserve legacy initial geometry. This is application concurrency control, not
  independent integrity verification of all segment tables.

`GET /chats` hashes stored JSON before hydrating coordinate references and returns
`savedRevision`. Creation preserves its response body and exposes revision in the
CORS-readable `X-Trip-Revision` header. Modern conditional PUTs accept
`ExpectedRevision` and `UpdateScope` (`route`, `presentation`, `full`) and return
`{savedRevision}`. Legacy unconditional clients retain their prior compatibility
contract and do not gain concurrency guarantees. No database schema change is
required. Route edits retain explicit save/discard and uncertain-write readback.

## Combined verification

Checks run sequentially to avoid resource-contention timeouts; thresholds are
unchanged. No live service or hosted database was used.

- Combined backend suite: 2,799 passed, 150 skipped, 81.32% coverage (63% required).
  Final bounded CAS/create/car/geometry changes then passed 55 focused API/schema/
  storage tests; final full Ruff formatting and lint pass (307 files). The full
  coverage run predates those last bounded fixes; exact-head CI remains required.
- Combined frontend suite: 469 tests / 61 files passed, 92.49% lines/statements,
  87.43% branches, 88.16% functions. Post-freeze persistence/page/profile checks:
  86 tests / 9 files passed. Final format, ESLint and production build pass.
- The 10,001-point to two-point route regression passes through the real schema,
  API and CRUD with a transactional cursor double, checking exact reloaded final
  geometry, preserved initial geometry, independent foreign rows and revision
  refresh. The separate actual disposable PostgreSQL regression also passed
  (one test, 0.23 seconds) on a fresh local standard-credential fixture. It verifies
  real stored/hydrated geometry, initial preservation, owner-scoped pruning and
  rollback after a partial segment insert encounters a foreign identity. Evidence:
  `/tmp/roadtrips-stage2-geometry-native.log`.
- Expanded offline signed browser/API/disposable-PostgreSQL journey passed against
  the combined application. The gate follows the actual compact setup to `/trip`,
  real reserved lunch accounting, no-reload visit/undo revision refresh, stale
  HTTP 409 with unchanged durable state, browse/edit preview/no-write/save/reload,
  profiles and separate car persistence. It retains expired-departure and
  non-owner research rejection, external-network refusal and 390px/1440px checks.
  Runtime used frozen application checkpoint `0e2d0f3` and exited zero; one trip
  and two profiles were created only in the disposable fixture, with no blocked
  external requests or browser errors. Evidence is in
  `tests/guidedjourney/.artifacts/result.json`, `happy-result.json` and adjacent
  screenshots; `/tmp/roadtrips-stage2-guided-native.log` records the native run.
  Both disposable projects and all fixture services were stopped afterward.
  See `tests/guidedjourney/VALIDATION.md` for the exact execution boundary.

Independent reviewers approved the shared control/profile privacy fix, the
catalog meal compatibility boundary, and the scoped save/create/geometry fixes.
Only `backend/app/catalog/hold_resolution.py` changes under catalog code/data;
all catalog pin and data files remain unchanged. All four original feature heads
and the fresh hotfix develop base are verified ancestors of the application
checkpoint `0e2d0f345597311f66eaa8058b2316966227536c`.

The normal four hosted workflows must pass on the final combined draft-PR head.
Native success does not replace the mandatory Local containers wrapper gate.

## Remaining product and acceptance boundaries

- The server-owned complete-candidate one-day/no-hotels mode is not implemented.
  Driving duration excludes stops, waits, meals and rest, and cannot authorize a
  client-only hotel skip. Existing room/hotel requirements remain authoritative.
- Logo asset commit `547a640c` referenced by the onboarding handoff is unavailable
  in the repository or GitHub; no replacement asset is fabricated here.
- Extraction from a single free-text trip description is not added.
- The early map shows a provider-confirmed initial driving estimate. Progressive
  map updates showing the actual candidate as planning proceeds are not added.
- Local browser/device emulation, mocked provider adapters and disposable local
  PostgreSQL do not establish real Cognito, live Mentro/provider-trip acceptance,
  physical-device acceptance or cross-device production persistence.
- The separately approved single post-deployment live test remains unused and
  blocked on an authorized application session/account. It must run only after a
  parent-coordinated deployment, within its approved scope. This candidate makes
  no live Mentro/provider requests or hosted database operations, and does not
  retry the previously denied Neon test.

No GitHub push/merge, deployment, production account change or hosted data change
is authorized by this handoff. The next deliverable is a reviewed draft integration
PR after the release owner approves a concrete commit.
