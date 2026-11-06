# Authenticated trip verification

This is a verification plan, not a record of a completed authenticated browser
journey. It covers the connected guided workflow and meal reservations. The
ordinary offline checks do not establish real Cognito, live provider, or hosted
database acceptance. No account access or live request was used to write this
plan.

## Existing evidence and its limits

| Check | What it exercises | Boundary it replaces |
| --- | --- | --- |
| `backend/tests/auth_tests.py` | Actual RS256/JWKS verification, access/ID claim matching, owner eligibility, invalid signatures and two subjects | JWKS retrieval uses a local public key; no Cognito login |
| `backend/tests/routing_api/guided_flow_tests.py` | Authenticated HTTP routing contracts, streamed progress/errors, owner selection and bounded alternatives | Injected auth/provider/catalog fixtures where specified by each test |
| `backend/tests/chat_persistence_tests.py` | Real request schemas and CRUD code, owner scope, idempotency conflicts and presentation retention | A transaction/storage double replaces PostgreSQL |
| Frontend session, stream, setup, saved-trip and visit tests | UI/service/session races, bounded refresh, no interrupted-stream replay, save/reload and legacy compatibility | SDK, HTTP and storage fixtures |
| `node tests/postgres/run.mjs` | Real disposable PostgreSQL CRUD, ownership, recreate, backup/restore and API readiness | Local synthetic rows and checked-in DDL; no hosted schema acceptance |
| `tests/ui-rework/browser-check.mjs` | Historical browser interaction/accessibility with intercepted structured responses | Unsigned client fixture claims, all API responses and storage; older navigation |
| `tests/studio-persistence/fixture.py` | Studio job/history lifecycle with memory-only run storage | Planning/provider execution and persistent storage; not the account guided flow |

The historical browser script must be updated before use with the current guided
flow. It does not send a browser request through the actual Cognito verifier or
CRUD API. Its historical Studio navigation also predates owner-only Settings
access. Do not point either browser fixture at production.

The existing disposable PostgreSQL Compose API sets `LOCAL_PREVIEW=true`.
`backend/app/main.py` intentionally returns 503 for business routes in that mode.
That stack proves readiness and CRUD separately; changing its URL does not turn
it into an authenticated planning fixture.

## Repeatable offline checks available now

From repository root, with dependencies already installed:

```sh
backend/.venv/bin/python scripts/run_offline_tests.py \
  tests/auth_tests.py tests/provider_route_auth_tests.py \
  tests/routing_api/guided_flow_tests.py tests/chat_persistence_tests.py

NODE_OPTIONS="--require=$(pwd)/scripts/offline_node_guard.cjs" \
  npm --prefix frontend test -- \
  src/tests/session.test.js src/tests/protectedRequest.test.js \
  src/tests/sessionRecovery.test.jsx src/tests/tripRouteStream.test.js \
  src/tests/TripSetupPage.test.jsx src/tests/savedTripCollision.test.js \
  src/tests/StoredTripReload.test.jsx src/tests/TripVisitProgress.test.jsx \
  src/tests/ResearchAccess.test.jsx
```

Run the meal scheduling, actual-leg timing and itinerary regression suites added
by the reservation change as well, then the full required suites without lowering
thresholds. `scripts/run_offline_tests.py` strips ambient credentials and dotenv
and blocks network connections. The Node guard likewise blocks real network
dispatch while allowing mocks. Neither should be disabled to make a test pass.

The existing PostgreSQL command is `node tests/postgres/run.mjs`. It creates an
isolated, randomly named local Compose project with synthetic rows and refuses a
populated initialization/restore target. Run it only in its documented disposable
local scope, after checking Docker and the cloud proxy/CA requirements. This is
independent of the previously denied hosted Neon operation, which must not be
retried or substituted as a test target.

## Proposed full offline browser-to-API fixture

This fixture is additional work; no command for it is claimed to exist yet. It
can establish the complete application path without live accounts or providers:

1. Use a dedicated test bootstrap and isolated runtime network. Permit only the
   local frontend, API, synthetic identity endpoint and disposable PostgreSQL.
   Disable dotenv loading; do not inherit production credentials. Keep provider
   stubs and bootstrap out of the production entry point. Bind any host ports to
   loopback. Keep production `LOCAL_PREVIEW` behavior unchanged.
2. Reuse the local RSA/JWK strategy in `backend/tests/conftest.py`: mint access
   and ID tokens for two distinct synthetic subjects, with the fixture issuer,
   app client, token uses, expiry and matching subject. Supply the fixture public
   JWK only from the test bootstrap. Exercise the actual production signature and
   claims verifier; do not replace it with a dependency returning a user ID.
3. Point the existing `VITE_COGNITO_ENDPOINT` test hook at a local Cognito protocol
   fixture. Exercise the real login form and SDK request shape, returning the
   locally signed token pair. Support a bounded refresh response and rejection.
   Synthetic passwords/tokens belong only to this disposable fixture and must
   never be accepted by the deployed API.
4. Inject deterministic location, route legs, hotel offers, reviewed catalog
   rows and estimated attributes at provider boundaries. Retain actual CP-SAT
   selection, meal scheduling, actual-leg validation, itinerary construction,
   request authentication and saved-trip CRUD. Use the checked-in disposable
   schema and real PostgreSQL for this lane. An unexpected provider/network
   request must fail the test rather than fall through to a live service.
5. Drive the current five stages, confirm locations and request a route with
   meal reservations. Assert one execution, actual progress before completion,
   successful itinerary and save, visit/undo persistence, route/itinerary reload,
   and the same saved result after API/database recreation. Verify the inferred
   preference vector stays absent from traveler-facing content.
6. Verify meal start/end instants and durations against every visit and driving
   leg, including driving interrupted by a meal if the contract permits it.
   Cover multi-day hotel restarts, local day/zone changes, DST, partial first/last
   days and a tight calendar conflict. An infeasible reservation must produce an
   actionable failure without 100% success or a falsely completed saved trip.
   Legacy trips without the opt-in must retain their original timings.
7. Switch between both synthetic subjects. Verify account-scoped saved trips,
   selection and drafts clear appropriately, an in-flight result cannot save to
   the new account, and cross-subject access is denied. Test exact verifier-401
   refresh once, arbitrary application-401 without replay, interrupted NDJSON
   without automatic rerun, and sign-out while work is active.
8. Test a fixture owner ID token with verified owner email and matching access
   subject, then a normal second subject, forged/mismatched identity and missing
   identity. Settings visibility must follow backend capability; direct Studio
   and research HTTP requests must enforce access. Do not start research jobs.
9. Capture only synthetic screenshots and request counts/statuses, plus console,
   accessibility and overflow results. Exclude Authorization headers, credential
   bodies and browser storage from artifacts. Label the report as local signed
   fixtures, not Cognito or live provider acceptance.

## Separate real-account acceptance

The least invasive first pass uses an already authorized user-controlled browser
session and read-only requests: sign in through the normal UI, open Settings,
load only that account's saved trips, and reload map/itinerary views without
editing or generating. Record statuses and visible results without exporting
browser authentication state or enabling credential-bearing traces. Map rendering
can contact the configured map provider; its presence is not proof of planning.

Owner restriction acceptance needs the existing verified
`eschiffler1122@gmail.com` account plus an authorized existing non-owner test
account. The owner must see the Settings entry and pass the backend capability;
the non-owner must lack that entry and receive 403 from protected research APIs.
Anonymous requests should receive 401. A client-edited email is not evidence of
owner access. Studio still has its separate scoped session boundary. Do not run
experiments as an incidental access check.

A complete generated-trip acceptance run needs a separately approved target and
scope: either an isolated staging API/database with controlled provider responses,
or explicit permission for live Mentro/provider use and creation/update of a new
test trip on a named account. The new reservation implementation must first pass
offline verification; do not deploy it merely to obtain this evidence. Keep old
trips untouched. Any cleanup must identify only records created by that run and
must not use a hosted rollback/restore operation.

For real renewal acceptance, use the normal session expiry/refresh path and
matching access/ID tokens. Do not change app-client rotation/device settings or
revoke unrelated sessions. Unit fixtures cover forced failures; real Cognito
configuration is a separate observation.

## Access and approval still needed

- User-controlled sign-in sessions for the owner and an existing non-owner
  account, including any interactive verification. Do not request passwords,
  refresh tokens, cookies or storage-state files in chat.
- If no non-owner account exists, obtain explicit approval for a dedicated test
  account and its email verification through the normal signup flow. Do not
  create an account or change an existing account's permissions implicitly.
- A named isolated acceptance environment if testing real Cognito with mocked
  planning, including its approved CORS/client configuration. Do not change the
  production app client or account permissions to make a test possible.
- Separate explicit approval for any live Mentro/provider trip and its bounded
  cost/data writes. Existing production deployment permission does not supply
  that separate provider-call approval.

Without those inputs, offline signed fixtures and disposable persistence can
verify application behavior, while real-account and live-provider acceptance
remain unverified. No hosted Neon retry, production mutation or authentication
bypass is required for the offline lane.
