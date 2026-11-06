# Offline trip-creation release gate

Run this gate before every production push/release. It is part of the existing
required **Local containers** workflow, so the EC2 deployment's four-workflow
gate cannot pass if current guided trip creation fails. Live Mentro calls need
separate explicit approval; this test never makes one.

The browser signs in through the real current login form and Cognito SDK using
a local protocol fixture. The API uses its actual RS256 signature/issuer/client
and subject verification. It then executes actual HTTP planning, adaptive source
processing, AI-rating/visit-duration prompt construction and parsing, CP-SAT,
estimated scheduling, actual-leg timing validation, itinerary construction and
saved-trip CRUD. Storage is a new synthetic PostgreSQL instance in an internal
Docker network. Browser reload, visit/undo persistence, and opening the saved
itinerary must work. An expired departure must expose an actionable error and
must not save another trip or falsely complete planning.

Only external boundaries are synthetic: Cognito login/JWK delivery, catalog rows,
geocoding, road responses and a local Supabase/Mentro HTTP/SSE service. The real
gateway adapter, source parser, solver, timing, verifier and CRUD stay active.
The gateway fixture validates message/body limits and returns deterministic
ratings and durations. It is not the actual Mentro server or model, and does not
prove live provider behavior, current Cognito accounts, production data/schema,
or network availability.

## Run

The Local containers workflow already builds/starts the diagnostic web image and
builds the backend test image. For the same sequence locally, use a clean checkout
of the exact candidate, Docker/Compose, Node 24 and installed Chromium:

```sh
export ROADTRIPS_REVISION="$(git rev-parse HEAD)"
docker compose --env-file /dev/null -f compose.yaml -p roadtrips-local up --build --detach --wait --wait-timeout 60
docker build --target test --build-arg VCS_REF="$ROADTRIPS_REVISION" \
  -f backend/Dockerfile -t roadtrips-tests-local .
npm ci --prefix tests/guidedjourney --ignore-scripts --no-audit --no-fund
node tests/guidedjourney/run.mjs
docker compose --env-file /dev/null -f compose.yaml -p roadtrips-local down
```

Set `CHROMIUM_PATH` if Chromium is not `/usr/bin/google-chrome` or
`/usr/bin/chromium`. Images must carry the exact candidate revision. The runner
stops only the diagnostic local API, preserves the built real frontend, creates
a random isolated fixture project and removes that project's tmpfs database at
the end. It never accepts a hosted database target, account credential, general
Docker prune or production URL. Build dependencies with normal verified TLS;
use the managed environment's documented proxy CA mount when required.

The browser permits only the three loopback app/API/identity origins. PostgreSQL
uses only an internal network. The API additionally uses a local access bridge
with IP masquerading disabled for its loopback-published HTTP ports; its Python
DNS/connect/connect_ex guards reject external destinations, and any attempted
external connection fails the gate even if application fallback catches it.
The fixture has no production credentials, disables dotenv and optional
replication/cache execution, and rejects a nonlocal database URL at startup.
HTTP logs and artifacts contain synthetic data only; no authorization header or
browser authentication-state export is recorded. Screenshots/results are ignored
under `.artifacts/`; installed test dependencies are ignored under `node_modules/`.

These fixtures are mounted only into the test image by this runner. They are not
part of the production image or app configuration. Do not point the fixture
browser at production or disable authentication/network protections to pass.
