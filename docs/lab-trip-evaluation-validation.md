# Algorithm Lab trip evaluation validation

Date: October 5, 2026 (America/Los_Angeles). Code changes are on
`codex/lab-trip-evaluation`, based on `codex/algorithm-live-only`.
No public application deployment or merge was performed.

## Neon migration — PASS

Authenticated Neon MCP endpoint inventory matched the backend's configured pooled
host `ep-silent-firefly-aqma935w-pooler.c-8.us-east-1.aws.neon.tech` to project
`misty-mouse-24917066`, production branch `br-noisy-forest-aqidrq92`, database
`neondb`. The table was absent before migration.

Recovery snapshot `snap-broad-glade-aq2jkk4y`, named
`pre-algorithm-lab-runs-2026-10-05`, was created at 16:25:02 UTC and verified through
snapshot inventory before production migration. No restore into production was
performed; the snapshot remains available for recovery.

The exact checked-in additive SQL was prepared through Neon MCP on temporary
branch `br-wispy-lab-aqhfqnem`. Verified 13 columns, primary key and three indexes,
check constraints and the configured application's SELECT/INSERT/UPDATE
privileges. A temporary insert/finalize/owner-scoped read transaction passed and
was rolled back. The prepared migration was applied to the verified parent
through MCP, and MCP deleted its temporary branch afterward.

Production metadata verification repeated successfully. The local running API's
`GET /ready` returned `{"status":"ready"}` after migration. Existing tables were
not altered, and no synthetic test rows were written to production.

## Application and disposable validation — PASS

- Python 3.12.14, pinned requirements installed; Ruff 0.16.7 format and lint pass.
- Backend suite: 668 tests pass; coverage exceeds the unchanged 63% gate.
- Frontend: Node 24, `npm ci`, format check, lint, coverage suite and Vite build pass.
- Container preview build/start and `node --test tests/container-smoke.test.mjs` pass.
- `node tests/postgres/run.mjs` passes real insert/finalize/history, ownership,
  pagination, repeat-count constraint, restart/database loss, backup/restore and
  populated-target refusal. Production data was not used for these gates.
- Disposable volumes `roadtrips-crud-b4b197cb41_source-data` and
  `roadtrips-crud-b4b197cb41_restore-data`, and their ignored dump, are retained.

The inherited local `.env` excludes `http://127.0.0.1:5173`, causing the unchanged
preflight test to fail in the initial backend run (666 passed, one failed).
The complete suite passed with `CORS_ORIGINS` explicitly set for the test process
to the repository defaults: both development origins, loopback preview origin,
and the two existing public origins. No environment file or CORS implementation
was changed, and the initial environment failure is preserved here.

## Live owner acceptance — BLOCKED

Browser sign-in reached `/algorithm`, but the current account was refused with
“Owner access required.” The backend requires verified owner email
`eschiffler1122@gmail.com`; owner sign-in is needed to verify history loading,
one live provider trip and persistence of its v2 metrics after browser reload.
Do not treat synthetic authentication or disposable database tests as this gate.
The PR must remain draft pending that acceptance and its upstream release gates.
