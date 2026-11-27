# EC2 deployment workflow

After all required CI passes on the exact current main commit, Deploy EC2 replaces
this backend API container on the existing shared EC2 host and verifies health.
A manual dispatch on main can retry a release. The host also checks CI and main,
serializes deployments, rejects stale SHAs, and rolls back a failed release.

The production environment holds EC2_DEPLOY_URL=https://ops.elischiffler.dev and
an app-specific EC2_DEPLOY_TOKEN secret. EC2_DEPLOY_ENABLED=true is a repository
variable. The environment permits main only. Automatic runs activate when the
owner merges this workflow PR; production dispatch is not available before merge.
Runtime secrets remain on the host. No SSH/AWS key is stored in Actions.

Only the API is deployed. Existing Compose project identities, external databases,
volumes, frontends, and other applications are preserved. Database migrations
remain a separate reviewed operation. See the shared deployment and recovery
[runbook](https://github.com/elischiffler/hosting-ops/blob/main/docs/ec2-deployments.md).

## Apple Maps directions release

Set `APPLE_MAPS_TEAM_ID`, `APPLE_MAPS_KEY_ID` and `APPLE_MAPS_PRIVATE_KEY` in
the backend runtime secret file on EC2 before releasing. Use an Apple Maps
Server-enabled signing key. Set `APPLE_MAPS_PRIVATE_KEY_FILE` instead of the
inline key when using a protected in-container PEM mount. In a single-line
dotenv value, separate PEM lines with literal `\n` sequences. The browser uses a
separate, origin-restricted MapKit JS token.

Publish and verify the compatible production website map viewer before merging
the API release. Production API endpoints that return new directions require
`X-Roadtrips-Directions: apple` so previously loaded clients refresh before
receiving Apple road geometry. New saved routes retain waypoints, stops and
itinerary. The viewer fetches fresh Apple directions on reopen. Older saved
trips retain their original geometry and provider presentation.

[Apple Maps Server authentication](https://developer.apple.com/documentation/applemapsserverapi/creating-and-using-tokens-with-maps-server-api)

## OpenAI for trip planning

Provision the Roadtrips OpenAI project key as `ROADTRIPS_OPENAI_API_KEY` in the
protected server runtime environment before releasing this backend. The default
model is `gpt-5.4-mini-2026-03-17`. The optional `ROADTRIPS_OPENAI_MODEL`
setting can select a compatible Responses API model that supports JSON output.
The application sends `store: false` with structured requests and validates
trip details, place ratings, and visit durations before using them. Keep the
credential server-side. Existing validated cached ratings retain their original
provider provenance.

The signed guided-journey release gate uses an isolated HTTP provider fixture
and needs no live key. Check live provider access using an explicitly authorized
request with synthetic text.
[OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).
