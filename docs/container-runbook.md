# Local container preview

This is a partial, isolated preview pending a reviewed complete database schema.
It serves the production frontend and FastAPI process without production keys.
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
while database/schema prerequisites are missing. Table presence is not complete
schema/migration validation. Acceptance deadlines chosen before container runs:
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

## Persistence and recovery prerequisites

No PostgreSQL volume is created or guessed schema installed. README DDL covers
three tables and chat-agent-design covers another, but neither is a reviewed
complete schema. Obtain an authoritative reviewed export, initialize a disposable
volume, and complete API persistence and recovery checks before enabling a DB.
The [local schema proposal](local-schema-proposal.md) records the exact checked-in
DDL and unresolved identifier-scope questions; it has not been applied.
Reuse `hosting-ops` PostgreSQL backup/restore tooling and its restore refusal
checks. Never restore over production or delete volumes during routine restart.

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
