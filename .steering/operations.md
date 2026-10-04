# Runtime, CI and operational boundaries

## Configured repository behavior

All four workflows run on every PR and pushes to main, without service path
filters or production credentials:

| Workflow | Checks |
| --- | --- |
| `.github/workflows/backend-ci.yml` | Python 3.12, pinned Ruff format/lint, pytest coverage >=63% |
| `.github/workflows/frontend-ci.yml` | Node 24, npm ci, format/lint/Vitest coverage and separate Vite build |
| `.github/workflows/container-ci.yml` | Guarded Compose preview, container smoke and isolated Python test image |
| `.github/workflows/disposable-postgres-ci.yml` | Real disposable CRUD/ownership, recreation, loss recovery, backup/restore |

Repository settings and required-check enforcement were not inspected in this
refresh. No production deployment job exists in these workflows. The intended
automatic deployment after an approved merge still needs a verified release
pipeline; do not infer it from green CI or Vercel previews.

`backend/Dockerfile` and `frontend/Dockerfile` use digest-pinned bases and locked
dependencies. Runtime images carry commit-revision labels, omit dotenv files
and run as non-root users. Backend runtime removes test packages/source; frontend
serves a Vite build through nginx. `compose.yaml` provides read-only roots, tmpfs,
resource caps, bounded logs and healthchecks. API is 768 MiB/1 CPU; web is
128 MiB/0.5 CPU. These caps are configuration, not shared-host capacity evidence.

`/health` is process liveness. `/ready` tests connection and presence of the four
expected application tables with bounded database operations; it does not verify
their columns, migration history or a complete authenticated trip.
`LOCAL_PREVIEW=true` validates isolated configuration and blocks business routes.

## Deployment documentation versus live state

README and `docs/aws-api-readiness.md` record AWS API with external Neon and Vercel
frontend targets; the Render service is retired. No live host/provider inventory,
DNS, runtime commit or production credentials were inspected during this refresh.
Treat recorded host state and historical validation as dated evidence.

`compose.neon.yaml` is an API-only Neon template with loopback publishing, egress,
verified TLS and an explicit write gate. `compose.prod.yaml` is the proposed
same-host PostgreSQL topology, depending on a separately owned external database
network. Neither creates the production database nor configures automatic release.
`backend/app/core/config.py` owns fail-closed target/TLS/preview configuration.
`docs/self-hosted-postgres.md` owns TLS semantics; use weaker local TLS only on
the explicitly isolated network, never as a hosted test workaround.

## Persistence and recovery

The checked-in local DDL and memory CRUD support disposable tests, not a claim
about production schema compatibility. `tests/postgres/run.mjs` and
`tests/journey/run.py` use unique test stacks, distinct source/restore volumes,
backup verification and populated-target refusal. Retain recovery data; never
use volume deletion as deployment or cleanup procedure.

`docs/container-runbook.md` owns container commands, shutdown/recreation and
recovery. `docs/off-host-neon-recovery.md` and `docs/aws-api-readiness.md` own the
hosted recovery proposal and release gates. Backup schedules/results mentioned
there need live re-verification before operational use. An image rollback does
not undo data writes or incompatible schema changes.

Feature PR #26 remains draft pending full live Cognito owner/non-owner, provider,
model, browser persistence/reload and recovery acceptance. `docs/hotel-prices.md`
records a limited live hotel lookup, not a complete booking or full trip. Offline
signatures, mocked model/geocoder tests, local journeys and disposable real
PostgreSQL have distinct evidence scopes. Preserve those distinctions when
reporting PASS/BLOCKED; use `docs/container-validation.md` as historical evidence,
not the current feature's complete validation ledger.
