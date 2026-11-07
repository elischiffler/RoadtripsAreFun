# Sharing worker handoff — November 7, 2026

Base: exact integrated Stage 2 `3a5494d5e7b1d7121982d86522e66045b2af3cb9`.
Branch: `task/stage2-sharing-20261107`; isolated checkout
`/workspace/roadtrips-stage2-sharing`. No push, hosted database change, account
permission change, invitation/message, provider/AI call or deployment occurred.

## Delivered

- Owner management: current-revision create/rotate of a 30-day opaque link,
  Stop link versus Stop all sharing, individual connection removal that also
  disables the known link, stale sharing/member identity conflict and refresh.
- Anonymous read-only capability page, ephemeral/stripped token fragment and
  token-free in-app sign-in return; no external map SDK or owner write controls.
- Verified Cognito account connection, distinct Shared with me list, current-owner
  snapshot reads, self leave, independent member revocation and delete cascade.
- Explicit minimal public projection, private-data omission, public-only content
  digest and one coherent repeatable-read snapshot for JSON/segmented coordinates.
- Two additive SQL tables and reviewed destructive metadata-only rollback file;
  no runtime DDL or global readiness change. Concrete target/backup/apply/rollback
  and old-backup revocation boundaries are in [trip-sharing.md](trip-sharing.md).

## Source inventory

Backend: new `crud/trip_sharing.py`, `routers/trip_sharing.py`,
`schemas/trip_sharing.py`, router registration only in `app/main.py`,
`sql/trip_sharing.sql`, `sql/trip_sharing.rollback.sql`, offline sharing tests and
real PostgreSQL sharing tests. Existing chat CRUD/auth/planning/catalog source is
unchanged.

Frontend: new `ShareTripPanel`, `SharedTripPage`/`SharedTripsPage` and token-based
sharing service. Small integrations add public/shared routes, owner sharing panel,
Shared with me entry, narrow safe sign-in return paths and audited pre-dispatch
verifier retry patterns. The shared page reuses the pure `PlaceTiming` presenter;
no `TripVisitProgress`, arrival assistance, route editor, car editor or owner
workspace is mounted there. Controls/styles reuse the master design variables.

Disposable verification: `tests/postgres/schema.sql` includes the additive SQL;
`tests/postgres/run.mjs` checks all authoritative DDL including sharing and runs
its actual PostgreSQL tests. `backend/tests/db_integration_probe.py` additionally
seeds and verifies a synthetic link/member through the existing restart/backup/
restore lane without retaining a plaintext token. Existing ownership/geometry/
memory/conflict assertions are preserved.

## Completed checks

- Backend full offline coverage: **2,817 passed, 163 skipped, 81.16% coverage**,
  125.10 seconds. Optional/disposable lanes stay skipped unless explicitly
  selected. Sharing's PostgreSQL lane is run independently below.
- Ruff full format/check: pass. Existing thresholds unchanged.
- Frontend full single-worker coverage: **492 passed, 63 files, 92.49% lines**.
  Format, lint and production build pass. Existing bundle-size advisory remains.
- Own fresh marked/empty, fixed-credential, loopback-only disposable PostgreSQL:
  **12 passed**, 2.13 seconds. Actual signed JWT verification, HTTP APIs, CRUD,
  JSON/geometry and transactions; no provider requests. Reapplication of the
  migration against the expected schema also passes.
- Independent reviewer: **13 actual PostgreSQL cases passed**, including its
  original stale-member leave/reconnect reproduction. The original code falsely
  returned success for the obsolete membership UUID; final code returns 409,
  rolls back and requires reload. Fresh removal disables the known link and
  revokes the current membership. No remaining source blocker reported.
- Actual fresh PostgreSQL seed, separate-process verify, restart, custom-format
  backup, empty independent restore and verify: pass. Synthetic sharing/member
  data survives, with existing owner/geometry/recovery checks retained.
- Disposable schema canonical comparison against README/memory/Lab/catalog/
  sharing DDL: pass. Whitespace checks: pass. All own random projects,
  containers, volumes and networks removed; the temporary dependency symlink is
  removed before committing.

Ignored evidence is in `.artifacts/sharing/`: backend/frontend raw logs,
`postgres-authorization.log`, `postgres-recovery.log` and a private synthetic
backup. The independent review record is
`/tmp/trip-sharing-independent-review-20261107.md`. Temporary native helpers were
local verification machinery, not application/deployment entry points.

## Boundaries and next integration

This is code/local verification, not live Cognito/provider, physical-device,
screen-reader, production-schema or deployed release acceptance. No complete
browser→sharing API→database journey was run; frontend component/transport tests
and actual signed-auth API/PostgreSQL acceptance cover those boundaries
separately. Existing mandatory guided browser gate remains part of final combined
CI. No migration/production enablement is claimed.

Production remains held for an explicitly approved database target/schema/backup
and application of the prepared migration. The release owner coordinates this
as a separate concrete approval. At this standalone lane checkpoint, `/ready`
did not check sharing prerequisites and sharing endpoints returned fixed 503 if
they were absent. The later complete Stage2 integration adds a bounded read-only
readiness check for both tables, 11 required column names/types and each individual
CRUD privilege of the application role. This release gate does not replace the
explicit constraint/index, recovery or live-account migration verification.

A separate bounded integration delta follows this fully reviewed checkpoint after
reading one-day schema `b945c827`. It allowlists only saved `trip_mode` literals as
a plan label and preserves actual scheduled rest/sleep rows through existing
safe itinerary fields. It omits the entire recurring `daily_schedule`/policy,
profile, cached tokens and `one_day_proof`; no proof is trusted or recomputed by
a read. Unknown/malformed modes are omitted. Focused backend projection and
frontend read-only rendering tests verify the delta; final combined full suites
remain the integrator's gate while the one-day worker owns the heavy-test slot.


Integration delta verification: **14 focused backend cases and 13 frontend
sharing/transport cases pass**. Changed-file Ruff, ESLint, Prettier and whitespace
checks pass. The full-suite figures above pin the reviewed core sharing checkpoint
`8094f4fb45b0d49360e177a15dd9ecea6f5e954a`; no additional full suites were run during
the one-day worker's exclusive slot. The final combined candidate must run them.
