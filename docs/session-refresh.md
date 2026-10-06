# Session renewal and expiry recovery

`frontend/src/services/session.js` owns Cognito token publication, renewal,
logout, account identity and generation. JWT decoding only schedules client
renewal and isolates UI state; backend signature/expiry/issuer/client checks remain
authoritative. Tokens stay in sessionStorage. No AWS configuration is changed.

The pinned Cognito SDK exposes `GetTokensFromRefreshToken`, supporting both
rotation modes. Renewal replaces access and identity tokens together, retains an
omitted refresh token, accepts a rotated token and sends a stored device key.
Results must contain unexpired matching-owner access/ID tokens of the expected
token uses. A late response cannot restore credentials after logout or sign-in.
The SDK makes one attempt so it cannot blindly retry a rotated refresh token.
A shared 15-second AbortController deadline bounds hung renewal requests; timeout
retains credentials and uses the temporary-unavailability recovery flow.
See [Cognito refresh requirements](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-refresh-token.html).

Renewal runs within 30 seconds of expiry before protected requests, on protected
route restoration and on application foreground return. Missing access tokens
can recover using refresh credentials. Concurrent callers share one promise.
There is one application foreground watcher, with no per-component renewal timers.
`NotAuthorizedException` and `UserNotFoundException` require interactive sign-in.
Network, throttling, malformed results and client/device configuration failures
retain credentials and show an actionable temporary-unavailability message, with
a five-second retry cooldown. The client cannot resolve AWS configuration errors.

## Dispatch and replay contract

`protectedRequest.js` owns protected Axios dispatch. `agentProgress.js` uses the
same session snapshot builder for streamed fetch. Immediately before each attempt,
both authorization/identity headers and legacy `partitionKey`/`PartitionKey` body
fields come from one session. Old closure tokens cannot replace fresh credentials
or send old-account chat data under a new account. Responses and progress from an
invalidated generation are discarded; streamed work is cancelled on account changes.

Replay requires HTTP 401 **and** the exact verifier detail
`Invalid authentication token`. There is at most one refresh/replay per request;
late stale-token 401s reuse a session already renewed by another caller. A second
verifier rejection requires sign-in. Unknown endpoints, arbitrary 401s, 403s,
5xx, network failures and timeouts are not replayed. NDJSON error frames,
interrupted streams and started streams are never replayed. Existing 45-second
idle timeout, reader cancellation and progress behavior remain intact.

The replay allowlist was checked against these rejection boundaries:

| Requests | Rejection before work |
| --- | --- |
| Chat GET/DELETE | `chat_api.py` verifies the bearer before CRUD |
| Chat create/update | `chat_api.py` verifies `PartitionKey` before CRUD |
| Agent JSON | `run_turn` verifies `partitionKey` before memory loading, extraction or tools |
| Agent NDJSON | `agent_chat_stream` verifies before constructing StreamingResponse |
| Routing/settings/car/provider, owner Algorithm Lab and itinerary | Auth dependency runs before endpoint body |

Application/provider failures with different detail are terminal even if 401.
There is no idempotency guarantee for uncertain mutations or disconnected agent
work, so retrying those remains an explicit user action.

## UI continuity

Protected children wait for restoration. Definitive expiry produces one login
notice and an allowlisted local return path. The context keeps chat selection,
route/itinerary, agent conversation IDs and in-memory unsent drafts through
same-account renewal or interactive recovery. Drafts are never automatically sent.
The protected `/algorithm` return path and Lab requests use the same session contract.
Another account or explicit logout clears that state and account-scoped browser
hints. Drafts survive navigation in the mounted application, not closing/reloading
the tab. Renewed identity tokens revalidate server-owned routing eligibility while
retaining a still-registered same-owner algorithm selection. Created/pending chat
readiness remains account scoped and survives token renewal.

## Repeatable checks and browser fixtures

From `frontend/`, run `npm ci`, `npm run format:check`, `npm run lint`,
`npm run test:coverage`, `npm run build`. Focused suites are `session.test.js`,
`protectedRequest.test.js`, `sessionRecovery.test.jsx` and routing-settings tests.
Thresholds are unchanged. `node --test tests/dev-runner.test.mjs` runs from root.

For isolated browser checks, start `node tests/session-refresh/fixture.mjs` from
root, then start Vite from `frontend/` with:

```powershell
$env:VITE_BACKEND_SERVER='http://127.0.0.1:18090/'
$env:VITE_COGNITO_ENDPOINT='http://127.0.0.1:18090'
$env:VITE_CLIENT_ID='fixture'
$env:VITE_USERPOOL_ID='us-west-1_fixture'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Open `http://127.0.0.1:5175/login`. Any fixture credentials sign in as `user`;
an email beginning with `other` signs in as the separate fixture account. The
fixture is loopback-only and in-memory, accepts unsigned fixture JWTs, and never
contacts AWS, a provider or a database. It must never be a production auth target.
`POST /fixture/control` accepts `refreshMode` (`ready`, `revoked`, `outage`) and
`rejectStream` (boolean). `GET /fixture/status` reports counts and request paths
without tokens/passwords. Use browser instrumentation to expire fixture access/ID
claims or call session renewal; never alter real tokens for this test.

Validation on October 4, 2026 (America/Los_Angeles):

- PASS: frontend format/lint, 259 tests, coverage 88.12% lines/statements,
  85.96% branches and 79.57% functions; production build; development launcher tests.
- PASS: Edge browser through agent-browser, no page errors or Vite overlay.
  Three concurrent renewals plus foreground restoration yielded one refresh,
  preserving the unsent draft, selected chat and conversation ID.
- PASS: initial-stream 401 recovery yielded two HTTP attempts, one executed turn,
  one user message and one reply. Fixture header/body credential mismatches: zero.
- PASS: revoked refresh redirected to one actionable sign-in notice. Same-account
  sign-in returned to `/chat` with the draft, messages, selection and conversation
  intact. Other-account sign-in cleared the draft/history and changed conversation ID.
- NOT APPLICABLE locally: backend lint/test, container smoke and disposable
  PostgreSQL gates; this change does not modify backend/container/database behavior.
  Required shared PR CI still runs those gates.
- BLOCKED: real Cognito/browser acceptance. No live session is supplied. Verify the
  existing app client's rotation and device-remembering requirements, including
  any confirmed device key, with authorized owner and non-owner sign-in sessions.
  Existing browser sessions with device remembering but no stored key may need
  interactive sign-in. No client-secret or AWS setting changes are included.

PR #26 remains draft for its pre-existing live provider/model/Cognito acceptance
requirements. The fixture and unit checks do not establish live authentication,
production schema compatibility or deployment readiness.
