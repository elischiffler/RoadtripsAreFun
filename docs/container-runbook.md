# Local container preview

This is a partial, isolated preview. A separate disposable stack verifies the
checked-in local PostgreSQL schema and real CRUD; the primary browser preview
still has no database or isolated Auth/provider fixtures. It serves the
production frontend and FastAPI process without production keys.
Do not use it as a working trip planner yet. The original PostgreSQL TLS changes
remain in this PR; hosted connections still require TLS by default.

From repository root, PowerShell:

```powershell
$env:ROADTRIPS_REVISION = git rev-parse HEAD
docker compose up --build --detach --wait --wait-timeout 60
docker compose ps
node --test tests/container-smoke.test.mjs
docker compose logs --tail 100
docker compose stop
docker compose start --wait --wait-timeout 60
docker compose down
```

POSIX: `export ROADTRIPS_REVISION=$(git rev-parse HEAD)` before Compose.
Frontend <http://127.0.0.1:8082>; API <http://127.0.0.1:8002>. `/health` means
process liveness; `/ready` checks database connectivity and the four documented
table names with 5-second connect/query deadlines. It deliberately returns 503
in the primary preview because no database is attached there. The separate
database test stack returns 200 after initializing the four documented tables.
Table presence does not validate the live production schema or migration history.
Acceptance deadlines chosen before container runs:
startup/recovery60s, HTTP10s, APIstop15s (uvicorn10s), nginxstop10s.

Compose uses a private internal network plus a bridge for Docker Desktop's
loopback-published ingress. The bridge is not an outbound firewall. Local mode
rejects hosted DB/gateway/Auth destinations, routing-proxy overrides and provider
keys; the image excludes dotenv files. Until schema/provider fixtures are ready,
local mode returns 503 before dispatching business routes; only root, health,
readiness and local algorithm inventory remain available. This also blocks
keyless hardcoded provider URLs. Browser build points only at API8002 and a
nonrunning local Cognito endpoint8999. Sign-in is blocked until an isolated
Cognito service is supplied. No Mapbox token is supplied. Do not add real keys
to this diagnostic preview.

Protected chat and agent routes require `COGNITO_USER_POOL_ID` and
`COGNITO_APP_CLIENT_ID` in the API container. A request with a token returns
a fail-closed 503 if these are absent; an invalid access token with verifier
configuration returns 401. GET/DELETE chat calls require an Authorization
Bearer header; URL query tokens are not accepted. The verifier fetches the
pool's JWKS and checks RS256 signature,
issuer, expiry, token use and app client ID. Offline tests supply a locally
signed JWKS; no real Cognito integration is claimed. These variables must be
reviewed and supplied with isolated Cognito before an authenticated preview.

API: uid10001, read-only root, /tmp64MiB, RAM768MiB/1CPU/128PIDs. Static frontend:
uid101, read-only root, /tmp16MiB, RAM128MiB/0.5CPU/64PIDs. Both drop capabilities,
set no-new-privileges, and rotate three10MiB logs. Runtime excludes test source;
the Python runtime removes pytest/coverage. Pinned dependency versions and base
digests support repeatable builds. Build requirements pin the two formerly
floating transitive dependencies (botocore and coverage) to the resolved versions.

Backend isolated tests from root:

```sh
docker build --target test -f backend/Dockerfile -t roadtrips-tests-local .
docker run --rm --network none -e DATABASE_URL=postgresql://fixture:fixture@127.0.0.1:1/roadtrips -e DATABASE_SSLMODE=disable roadtrips-tests-local
```

Quality commands and runtime versions are in AGENTS.md. Public frontend build
configuration is fixed in Compose for preview; future actual Auth/Mapbox setup
requires reviewed build inputs and separate isolated acceptance evidence.

## Disposable PostgreSQL CRUD and recovery test

From repository root with Docker Desktop running and Node 24 installed:

```sh
node tests/postgres/run.mjs
```

The script assigns a unique `roadtrips-crud-<id>` Compose project. Its private
network has no published database port. The source and restore PostgreSQL 18.6
containers use distinct named volumes; both are separate from the primary
`roadtrips-local` preview and `hosting-ops` data stack. The source initializes
from [`tests/postgres/schema.sql`](../tests/postgres/schema.sql), an exact
transcription of README's three tables/indexes and `memory_crud.py`'s table.
This is a disposable **local test schema**, not evidence of the live database.

The runner builds the backend test and production API images, seeds records via
real `chat_crud` and `memory_crud`, and verifies two-owner reads, route/step
conflict rejection, geometry, memory and deletion. It recreates the API and
source database containers, checks `/ready`, and reads the same records from a
fresh Python process. It saves a private custom-format `pg_dump` under
`tests/postgres/.artifacts/`, starts an empty restore volume, uses the same
application-object count refusal rule and safe `pg_restore` flags as
`hosting-ops/postgres/restore.sh`, and verifies restored records. This is a
disposable test driver mirroring the safety checks, not a second production
recovery tool; the production procedure remains in `hosting-ops`. A second
restore attempt must refuse the populated target. The script stops containers
but **never deletes either volume or backup**. Startup/recovery waits are 60
seconds; individual probe/backup/restore calls are bounded at 120 seconds.

The final output names the source and restore volumes. To inspect or restart a
specific completed run, set `DB_TEST_RUN_ID` to its printed ID and use its
project name with `docker compose -f tests/postgres/compose.yaml -p
roadtrips-crud-<id> ps` or `start`. Do not rerun the `seed` driver against a
populated test volume. To remove stopped containers and network while keeping
evidence, run `docker compose -f tests/postgres/compose.yaml -p
roadtrips-crud-<id> --profile api --profile restore down`.
Only after the data and backup are no longer needed, explicitly remove the two
printed volumes with `docker volume rm <source-volume> <restore-volume>` and
the private dump file; routine recovery never uses `down -v`.

The [local schema proposal](local-schema-proposal.md) records unresolved
production identifier-scope/migration questions. The primary browser preview
still deliberately returns 503 for business routes. Actual isolated Cognito,
route/map/provider fixtures and representative UI/API journeys remain separate.

The Mentro server contract can be tested over its separate internal pilot
network once that gate passes; do not point at hosted Fly or a production Auth
project. A partial provider test cannot replace the full route/chat persistence
journey. Actual Cognito and map/provider evidence remains separate.

After starting the Mentro fixture stack, this PowerShell probe runs the actual
Roadtrips runtime image against the actual Mentro server image. It injects only
the disposable token into the provider's existing test seam, not the API auth
boundary. It verifies the streamed text-tool protocol without executing a
location/provider lookup. Expected dependency-failure deadline is 15 seconds;
recovery deadline is 60 seconds.

```powershell
$probeDir = (Resolve-Path tests).Path
docker run --rm --network mentro-server-local_pilot -e PYTHONPATH=/app --mount "type=bind,source=$probeDir,target=/checks,readonly" --entrypoint python "roadtrips-api-local:$env:ROADTRIPS_REVISION" /checks/mentro_container_probe.py
```

For the separate failure exercise stop only `mentro-server-local-mentro-server-1`,
repeat with `--expect-down`, restart that same container, and repeat the normal
probe. Leave it healthy; do not delete another stack's volumes or configuration.

Production host, DNS, data migration and cutover are deferred. Existing hosting
automation is unchanged. A future release needs approved merge, current main
checks, immutable images, serialized deployment, readiness and documented
database recovery. Image rollback does not undo database migrations.
