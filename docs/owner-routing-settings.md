# Owner routing settings

`app/routing/selection.py` owns interactive algorithm eligibility and selection.
Only an authenticated account with a signed Cognito ID token containing the exact
owner email and boolean `email_verified=true` can select a registered algorithm.
The backend verifies RS256 signature, configured issuer, app-client audience,
expiry, issued-at, ID-token use, and matching access-token subject. Access-token
authentication remains mandatory. Missing or invalid ID evidence denies selection
without preventing normal authenticated CP-SAT planning.

The existing Cognito `USER_PASSWORD_AUTH` login returns both tokens. The frontend
attaches the ID token as `X-Cognito-Id-Token`; this path requires no new OAuth
scope, attribute lookup, IAM permission, or Cognito configuration change. The
pool/app client must already supply readable `email` and `email_verified` claims;
if they are absent, selection fails closed. AWS documents the token validation
requirements in [Verifying JSON web tokens](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html).

Authenticated `GET /routing-settings` returns only eligibility, registered names,
the registry default, and the ID-token expiration, with `Cache-Control: no-store`.
The frontend does not maintain an email allowlist. The routing gear menu has
been removed. The public Trip Planning Studio link uses a separate password
session and grants no account or algorithm-override privileges. Eligibility is bounded by both token expirations. Logout, login/account
changes, storage events, focus, and a one-second session check invalidate stale
state. Responses from previous credentials cannot restore access.

Selections stay in memory for the current session. Legacy `devRoutingAlgorithm`
storage is discarded and never read for authorization or selection. A reload or
account change resets the choice. Direct requests and agent context omit algorithm
overrides unless an eligible owner explicitly selects a registered name. No new
production algorithm is registered; `cp_sat` remains the sole available planner.

HTTP planning, local agent tools, and outbound remote routing use the shared
selection policy. Non-owner overrides are ignored, including unknown names.
Owners' unknown choices retain the existing 400 validation. `ROUTING_ALGORITHM`
does not change interactive defaults for either account class. Remote calls carry
the access and optional ID tokens so the receiving backend can enforce the same
policy independently. Live parity requires the receiving backend to include this
change.

## Verification

- PASS: frontend lockfile installation, format, lint, coverage tests, and build.
- PASS: Ruff 0.16.7 formatting/lint; pinned backend tests in Python 3.12 containers
  with the unchanged 63% coverage threshold.
- PASS: isolated preview container smoke checks and disposable real PostgreSQL
  CRUD, ownership, recreation, backup, restore, and populated-target refusal.
  Test volumes and backup are retained; no production data was used.
- Signed offline token tests cover owner/non-owner, forged identity, subject/client/
  issuer mismatch, missing claims, expiry, unavailable JWKS, and normal access
  rejection. Test-only alternate planners prove HTTP, agent/context/tool, remote,
  and environment override enforcement. Component tests cover eligibility failure,
  pending-response races, logout, account switching, expiry, tampered storage,
  and explicit owner selections through both frontend request paths.
- BLOCKED: live owner/non-owner Cognito browser acceptance and live remote-provider
  parity. No usable live sessions were supplied or exercised. Offline signatures,
  mocked UI tests, and disposable database checks do not establish these gates.

No schema, dependency, cloud configuration, or production deployment change is
required. Keep the feature PR draft until its existing live acceptance gates pass.
