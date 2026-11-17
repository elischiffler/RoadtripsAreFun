# Native mobile readiness

November 17, 2026. RoadtripsAreFun has reusable authenticated planning and
saved-trip APIs. A native release still needs evidence for public-client
sign-in, account continuity, compatibility with installed app versions, safe
recovery from interrupted generation and shared-host capacity. Framework
selection remains open.

This assessment inspected `origin/main`
(`42d5068bb4c8804a8024df0e4463fb05e0a7e275`) and `origin/develop`
(`8284b95543e28c810327e0367b11335515a31fff`). These are source revisions.
The primary checkout also contains in-progress browser OAuth, cookie session
and offline-preview work. Those branches and fixtures are useful design inputs.
Native-device sign-in, production identity settings and load remain unverified.

## Authentication and account continuity

The merged web sign-in uses Cognito's password flow and stores tokens in browser session storage.
The API accepts a Cognito
access token for the configured issuer and single `COGNITO_APP_CLIENT_ID`, then
uses the verified `sub` for account ownership. Some owner features can also
check an ID token against the same client's audience and the access-token
subject. A new native client ID therefore needs explicit API support. Keep the
web client accepted and validate tokens by issuer, signature, expiry, token use
and explicitly allowed client. Match any optional ID token to the same subject
and client. Use the same pool where appropriate and verify that an existing web
account sees its own trips after native sign-in, including with any supported
federated identity. [Verifier](../backend/app/utils/auth.py) ·
[Web sign-in](../frontend/src/services/authService.ts)

Evaluate a separate Cognito public app client with authorization code and PKCE
S256. Use the system browser session and exact registered redirect URIs. Prefer
claimed HTTPS Universal Links and Android App Links if the intended domains
and app identities can support them. Verify app/domain association and browser
fallback, cold and warm launches, cancel and denied consent, and return after
process death. Bind the callback to the pending transaction with state, a
one-time verifier and OIDC nonce validation when an ID token is used. Keep any
post-login navigation target within approved app routes. Test browser and
native sessions independently. [Cognito app clients](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html) ·
[Cognito PKCE](https://docs.aws.amazon.com/cognito/latest/developerguide/using-pkce-in-authorization-code.html) ·
[OAuth for native apps](https://www.rfc-editor.org/rfc/rfc8252)

Keep refresh credentials in Keychain on iOS and storage protected by Android
Keystore on Android. Serialize refresh per account and atomically store a
rotated token before releasing waiting requests. Test expired and revoked
refresh tokens, concurrent requests on foreground, a lost refresh response,
logout and account switching during planning. Clear the device session on
logout and verify revocation and managed-login logout behavior independently.
The current API verifies JWTs locally, so measure how long an already-issued
access token remains usable after revocation and set the expected exposure
window. [Cognito refresh and revocation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-refresh-token.html)

## API compatibility and retry safety

- Capture the existing route, itinerary and saved-trip contracts in fixtures
  exercised by the current web client and candidate native clients. Include
  saved trips from older versions, additive response fields, unknown values
  and error envelopes. Some legacy chat writes carry the access token in
  `PartitionKey` in the JSON body. Introduce any header-only replacement
  additively and keep established clients working through rollout and rollback.
  Set a supported client-version window and exercise the oldest supported build
  against each candidate backend. [Saved trips API](../backend/app/routers/chat_api.py) ·
  [Web request adapter](../frontend/src/services/protectedRequest.js)
- Keep transport, auth and business retries distinct. The web client retries
  an allowlisted request once after the exact verifier rejection
  `401 Invalid authentication token`, before work has begun. Use bounded
  backoff with jitter for safe transient reads and respect `Retry-After`
  when present. An ambiguous timeout can follow a committed save or provider
  call. Reconcile before repeating writes or starting a second generation.
  [Web retry behavior](../frontend/src/services/protectedRequest.js) ·
  [Trip stream client](../frontend/src/services/tripRouteStream.js)
- Current trip creation uses a client-selected trip number and a separate
  `agentChatId`. The create upsert allows the same planning ID and rejects a
  different ID for the same trip number. That protects against overwriting
  another operation's trip. Provider calls occur before save, and a same-ID
  payload can still overwrite a newer version of the row. Verify retry-after-commit, concurrent devices, conflicting
  payloads and account switching. For a resumable contract, evaluate a
  server-owned operation identity or stable client key, scoped to the verified
  account and bound to its inputs. [Create semantics](../backend/app/crud/chat_crud.py)

## Interrupted generation

The account route endpoint streams NDJSON progress, heartbeats and a terminal
result or error. The current worker runs in-process. Disconnect requests
cancellation at an async boundary and bounded synchronous work can finish
first. The client then requests itinerary generation and separately saves
the trip. The route stream provides no resumable job or durable result lookup.
An interrupted stream, an interrupted itinerary request and a lost save
response require different recovery actions. [Route API](../backend/app/routers/routing_api.py) ·
[Progress worker](../backend/app/agent/progress_stream.py) ·
[Trip creation sequence](../frontend/src/pages/TripSetup/TripSetupPage.jsx)

For an initial release, preserve the local draft, show the interrupted state
and reconcile any save against account-owned trips before allowing an explicit
restart. To promise background completion or cross-device resume, first prove
an authenticated operation-status/result contract that survives deploys and
process restarts, has bounded retention and makes a repeated start safe.
Exercise lock-screen backgrounding, offline entry, app termination, Wi-Fi to
cellular handoff, duplicate submits and deploy during generation. Verify
provider call counts, ownership, saved result count and final UI state.

## Capacity evidence

The November 17 EC2 inspection found the API healthy at the inspected main
revision and confirmed the configured 1 CPU and 768 MiB cap. The shared
`t3a.medium` had 2 vCPUs, 3.8 GiB usable memory and 2.1 GiB available at the
time of inspection, with swap disabled. Roadtrips uses external Neon.
Backend source defines per-run and process-wide limits for provider and solver
work and a five-connection chat pool. The supported concurrent-trip count and
response times remain unknown. The existing
offline guided-journey gate exercises signed browser/API requests, real
planning and disposable PostgreSQL, with synthetic identity and provider
boundaries. It is regression evidence for individual flows. [Compose limits](../compose.neon.yaml) ·
[Routing concurrency](../backend/app/routing/runtime.py) ·
[Offline release gate](../tests/guidedjourney/README.md)

Set latency, failure and saturation targets before a test. In an isolated
environment with equivalent caps, measure realistic route lengths and a mix of
streaming plans, itinerary requests, saved-trip reads and saves under stepped
concurrency and reconnect bursts. Record p50/p95/p99 time to first progress and
result, completion and abort rates, queue waits, CPU throttling, peak memory/OOM
and DB pool saturation. Separately verify authorized provider quotas, Neon
warm/cold behavior and proxy streaming on real devices. Coordinate the load
envelope with the shared-host operator and obtain separate approval for any
live Mentro verification. Record the exact tested backend revision, limits and
fixture/provider mix with each result.
