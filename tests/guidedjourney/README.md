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
Docker network. Browser reload and the saved `/trip` workspace must work. Sequential visit/undo
writes must refresh modern snapshot revisions without a reload, and an actual
stale-revision write must return 409 without changing stored state. A route
alternative must be browsed, recalculated, previewed without persistence, then
saved and reloaded. The dated short trip reserves a real 45-minute lunch, with
no attraction overlap and elapsed arrival time including that reservation.
Settings must persist and reload reusable profiles and a separate trip car;
loading a profile must populate the guided draft. Settings must hide research
tools for the verified non-owner, and the actual research API must return 403.
The edited trip must still reload after Settings; phone/desktop widths must not
overflow.
An expired departure must expose an actionable error and
must not save another trip or falsely complete planning.

Only external boundaries are synthetic: Cognito login/JWK delivery, catalog rows,
geocoding, road responses and a local Supabase/Mentro HTTP/SSE service. The real
gateway adapter, source parser, solver, timing, verifier and CRUD stay active.
The gateway fixture validates message/body limits and returns deterministic
ratings and durations. It is not the actual Mentro server or model, and does not
prove live provider behavior, current Cognito accounts, production data/schema,
or network availability.

Location text search/confirmation, the initial driving estimate, along-route
alternative search, route-edit preview and saved-route update execute through
actual HTTP APIs. Frozen synthetic source facts are supplied at the repository
read boundary for browse/current-place refresh; source validation, rerouting,
meal timing and itinerary logic remain active. Mapbox rendering is not verified:
the normal token-absent preview/list works without enabling a different map
build mode. No actual catalog SQL parity or live source freshness is claimed.

| Area | Evidence | Boundary |
| --- | --- | --- |
| Create, meals and saved edits | This signed browser/API/CP-SAT/timing/CRUD/PostgreSQL gate; actual route preview/save/reload; sequential visit revisions and stale 409 | Catalog and remote provider responses are synthetic; the short fixture exercises lunch, not every multi-day meal/window conflict |
| Errors, auth and Settings | Strict expired-date and non-owner checks; real profile create/edit/reload/reuse and trip car persistence | Most outage/account-switch tests use fixtures; no real Cognito acceptance; additional CAS races remain API/unit regressions |
| Search and maps | Browser location confirmation/driving estimate, along-route alternatives and an explicit attraction replacement; existing map/API suites | No live Mapbox rendering, geocoding or roads; not every edit/overnight/infeasibility path is exercised |
| Responsive layout | Browser 390px and 1440px overflow checks | Not physical-device or manual screen-reader acceptance |
| Recovery and ownership | Separate Disposable PostgreSQL CRUD workflow | Real CRUD/recovery there complements this browser lane |
| Catalog safeguards | Full offline admission/hold/tamper/refresh suites; unchanged 133 holds, 170 exact versions and seven parking decisions | Optional catalog PostgreSQL SQL-parity tests need their dedicated disposable database; readiness is not that test |

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

Initialization uses the existing disposable schema and
`tests/postgres/catalog-fixture.sql`: one explicitly synthetic catalog import,
one place and its active pointer. This lets the actual `/ready` dependency check
pass without overriding readiness or using a production catalog. The synthetic
generation's declared row count and actual place count are both one.

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
