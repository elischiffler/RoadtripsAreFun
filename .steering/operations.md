# Runtime, CI and operational boundaries

## CI and automatic deployment

Four validation workflows run on PRs and pushes to main without production
credentials or service path filters:

| Workflow                                       | Checks                                                                               |
| ---------------------------------------------- | ------------------------------------------------------------------------------------ |
| `.github/workflows/backend-ci.yml`             | Python 3.12, Ruff 0.16.7 format/lint, pytest coverage >=63%                          |
| `.github/workflows/frontend-ci.yml`            | Node 24, npm ci, launcher tests, format/lint/Vitest coverage and separate Vite build |
| `.github/workflows/container-ci.yml`           | Guarded Compose preview, container smoke and isolated Python test image              |
| `.github/workflows/disposable-postgres-ci.yml` | Disposable real CRUD/ownership, recreation, connection recovery, backup/restore      |

`.github/workflows/deploy-ec2.yml` runs after successful main-push CI completion
or manual dispatch on main. `scripts/check_deployment.py` waits for the latest
successful execution of every required workflow on the exact current main SHA.
PR/fork events, stale commits and failed required checks cannot authorize a release.
The job uses the production environment, a 90-minute timeout and non-cancelling
`ec2-production` concurrency. Multiple completed checks can trigger runs; a retry
of the already healthy revision does not recreate the API container.

`scripts/request_deployment.py` posts the checked SHA to the authenticated HTTPS
deployment endpoint and requires an exact healthy response for that app/revision.
The shared host independently verifies current main and CI before and after the
build, serializes releases across applications, checks container revision labels,
waits for health/readiness and restores the previous release on failure. It deploys
only this API, without running migrations or deleting volumes.

[EC2 deployment](../docs/ec2-deployment.md) owns application configuration;
the shared [host runbook](https://github.com/elischiffler/hosting-ops/blob/main/docs/ec2-deployments.md)
owns the listener, protected files, release directories, rollback and token rotation.
Do not duplicate host scripts in this repository.

## Verified repository and runtime state

October 5, 2026 (America/Los_Angeles), inspected main
`56ac6dbd3eccbd03e105385cf5561582376c0b17`:

- Repository variable `EC2_DEPLOY_ENABLED=true` is configured.
- The production environment has `EC2_DEPLOY_URL=https://ops.elischiffler.dev`,
  an `EC2_DEPLOY_TOKEN` secret entry and a deployment policy permitting main only.
  Secret contents were not printed. No SSH or AWS key is stored by this workflow.
- The classic main branch-protection API returned 404 (not protected). Repository
  ruleset enforcement was not audited. Successful CI gating in the deployment
  scripts is verified separately from GitHub merge enforcement.
- [Successful Actions deployment](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/37411743425)
  and fresh host inspection confirmed healthy container `roadtrips-neon-api-1`,
  image tag `roadtrips-api:56ac6dbd3eccbd03e105385cf5561582376c0b17`, matching OCI
  revision label and recorded release metadata.
- Public `https://api.roadtrips.elischiffler.dev` health/readiness, algorithms,
  Studio session/presets/history, anonymous rejection and production CORS passed.
  These checks do not establish a new complete trip or live Cognito acceptance.

The backend runs on shared EC2 with external Neon using `compose.neon.yaml`:
API-only, host-loopback port 8002, egress networking, verified database TLS,
explicit write gate, non-root image, read-only root, tmpfs, bounded logs and
768 MiB/1 CPU limits. Runtime secrets stay in protected host files.
The frontend is a separate Vercel boundary; this workflow does not deploy it.
The retired Render target is not a rollback destination (`README.md`).

## Container and readiness boundaries

`backend/Dockerfile` and `frontend/Dockerfile` use digest-pinned bases and locked
dependencies, revision labels and non-root runtime users. The diagnostic
`compose.yaml` preview publishes web8082/API8002 on loopback and sets
`LOCAL_PREVIEW=true`, blocking business routes. It is not the production topology.
`compose.prod.yaml` describes a separate same-host PostgreSQL alternative; the
current deployment uses the external-Neon stack, not a database migration.

`backend/app/main.py` defines `/health` process liveness and `/ready` database
readiness. Readiness checks connection and presence of `chats`, `route_segments`,
`steps`, `chat_memory` and `algorithm_lab_runs` with bounded operations. It does
not verify all columns, ownership rules or migration history. `backend/app/core/config.py`
owns fail-closed target/TLS/preview configuration; `docs/self-hosted-postgres.md`
owns TLS semantics. Weaker local TLS is limited to disposable isolated networks.

## Persistence and recovery

`backend/app/crud/chat_crud.py` and `memory_crud.py` own chat and memory storage.
`lab_runs.py` shares their pool for subject-scoped experiment history/results.
`backend/sql/algorithm_lab_runs.sql` owns the explicitly applied Lab migration;
ordinary chat runs are not recorded as Lab experiments. The historical replay
storage enum does not change the live-only request contract.

`tests/postgres/schema.sql` and the memory DDL support disposable tests.
`tests/postgres/run.mjs` and `tests/journey/run.py` use isolated stacks and recovery
fixtures; those results do not establish production schema compatibility.
`docs/container-runbook.md` owns local recreation and recovery commands.
`docs/off-host-neon-recovery.md` and `docs/aws-api-readiness.md` contain dated hosted
recovery plans/evidence. Backup schedules and an off-host restore were not verified
in this refresh. Never delete production volumes as a deployment step; image
rollback does not undo database writes or incompatible migrations.

Studio requires stable backend-only `STUDIO_SESSION_SECRET` across deployed workers
to retain signed sessions through restarts (`docs/studio-access.md`). It grants
visitor-scoped experiment access independently of Cognito, not account access.
Complete provider/model trips, browser persistence and two-account authorization
require separate live evidence. Keep local, fixture, CI and live results distinct.
