# Roadtrips API production template

## Public browser API gate

The deployed Vercel frontend currently embeds
`VITE_BACKEND_SERVER=https://rp-routing.onrender.com/`; Vite bakes this value
into the JS bundle. The AWS switch is
`https://api.roadtrips.elischiffler.dev/` (trailing slash), first in a Preview
build and then Production after the journey passes. The browser's Cognito
`VITE_USERPOOL_ID` and `VITE_CLIENT_ID` must match backend
`COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID` in `us-west-1`. The backend
must allow the actual Preview and Production origins in `CORS_ORIGINS`. For the
current PR Preview deployment, the stable branch alias is
`https://roadtripsarefun-git-fix-public-a-261cfb-eli-schifflers-projects.vercel.app`.
The Neon Compose template accepts an explicit `ROADTRIPS_CORS_ORIGINS` host
interpolation value so the operator can add that exact origin for the controlled
Preview test and later remove it without changing the default production
allowlist. Do not use `*` or an unreviewed wildcard.

Public provider-backed route, geocoding, itinerary, and car requests now require
a verified Cognito access token in `Authorization: Bearer`; the signed-in chat
UI sends its session token. `/health`, `/ready`, and the static `/algorithms`
inventory remain public. `/benchmark` is disabled unless explicitly enabled
and is authenticated when enabled. This preserves the existing signed-in trip
flow; an anonymous planner would need a separate abuse-control design. CORS is
not an authorization control. Deploy the backend and frontend from matching
reviewed commits before a public business journey.

The [off-host recovery proposal](off-host-neon-recovery.md) defines the
specific S3 destination, 30-day retention, cost estimate, and restore proof
needed before enabling Neon writes. The current same-disk dump alone does not
clear that gate. Public DNS and TLS can be staged without switching the
Production frontend, but a healthy `/ready` does not prove authenticated
route/map/chat persistence.

`compose.prod.yaml` is the API-only template for the proposed same-host
PostgreSQL cutover. It builds the backend from a reviewed full commit SHA, publishes container port
8000 on host loopback port 8002, and keeps PostgreSQL private. The host proxy
would route `api.roadtrips.elischiffler.dev` to `127.0.0.1:8002` after HTTPS,
readiness, CORS, authenticated trip, persistence, and recovery checks pass.
`compose.yaml` remains a disposable local preview with fixtures.

That Compose project uses a separate egress network for Cognito, routing APIs,
and optional Mentro/Supabase calls, plus the external `roadtrips_database`
network for the future same-host PostgreSQL. That network and the database are
owned by `hosting-ops`; they are not created by this template and do not yet
exist on the shared host. Do not start the production template until the
reviewed database restore and network provisioning are complete. Neon is still
the live database. The interim Neon topology below is independent of that
network.

## Interim AWS API with live Neon

`compose.neon.yaml` runs the API on the same loopback port, with egress to the
existing Neon database and providers. It does not create a database, attach to
`roadtrips_database`, or migrate data. The operator-supplied target inventory
is Neon project `misty-mouse-24917066`, production branch
`br-noisy-forest-aqidrq92`, database `neondb`, PostgreSQL 18, four public
application tables, and no snapshot. Verify that inventory and the actual
endpoint/credential ownership in the provider console before staging; the
project and branch identifiers are not encoded in a Neon connection hostname.

Place the protected connection string in Git-ignored `.env.production.neon` as
`DATABASE_URL`. It must select a `*.neon.tech` host and `/neondb`. Remove any
`sslmode` or `sslrootcert` query parameter from a provider-generated URL; the
only allowed URL query parameter is `channel_binding=require`. The Compose
environment forces `DATABASE_SSLMODE=verify-full` and
`PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt`; the runtime image contains
the system CA bundle and psycopg2's libpq 16. This verifies the endpoint
certificate and hostname. A wrong target or weaker TLS mode fails application
startup. The source value must never be printed in commands or logs. Use the
same credential and provider env **names** listed below, supplied through the
host's protected configuration process.

`ROADTRIPS_NEON_WRITES_ENABLED` defaults to `false` in this Compose file. In
that private stage, the API rejects POST/PUT/PATCH/DELETE with 503, while
`/health`, `/ready`, and CORS preflight remain available. Keep Caddy and public
DNS disconnected during private validation. This HTTP gate is defense in
depth, not a database privilege boundary: a read-only DB role is preferable
where available. Set the host interpolation variable to `true` only after the
write/provider acceptance is explicitly authorized and the public release
gates below pass. The same-host PostgreSQL template does not use this switch.

**Private stage gate:** after a user-approved PR merge and successful required
checks, identify the merged image by full SHA/digest, verify the protected
Neon target and TLS trust, confirm the read-only switch is false, then start
the loopback-only API. Record process health, actual `/ready` against Neon,
source-filtered ops events, CORS, and restart/recovery without writes. A
readiness 200 only proves four table names and connection, not their full
schema or application compatibility. No live Neon queries were made while
authoring this template.

**Public release gate:** obtain a restorable Neon recovery point and verify
the restore procedure (none was reported at handoff); verify schema and
migration compatibility; test actual isolated Cognito with two users and real
routing/Mentro providers; then authorize a controlled write journey against
the intended Neon target. Confirm ownership, persistence, reload, and
recovery, followed by proxy HTTPS/CORS and frontend variable cutover. Keep
the prior backend image and frontend target. With Neon unchanged, rolling back
the API image can preserve data if writes and schema remain compatible. It
does not undo writes or incompatible schema changes; those require the
reviewed database restore/reconciliation plan. Do not infer safety from the
local fixture journey.

## Host configuration shared by both topologies

Set `ROADTRIPS_REVISION` to the checked merged-main full SHA. Place
`.env.production.neon` for the Neon topology or `.env.production` for the
same-host PostgreSQL topology in the project directory using the host's
protected secret delivery process. Both files are Git-ignored and must never
be copied from a developer machine. The relevant environment names are:

| Name | Purpose |
| --- | --- |
| `DATABASE_URL` | Neon endpoint for interim AWS, or private `postgres:5432` app-user connection for same-host cutover; credential is secret. |
| `DATABASE_SSLMODE`, `PGSSLROOTCERT` | Neon Compose forces `verify-full` and system CA bundle. Same-host PostgreSQL may use `disable` only on its dedicated private network. |
| `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID` | Trusted access-token issuer and client. |
| `MAPBOX_API`, `TRIPADVISOR_API`, `OPENCAGE_KEY` | Routing and geocoding provider credentials. |
| `CAR_DATA_API`, `GOOGLE_PLACES_API` | Provider credentials where the corresponding routes are enabled. |
| `AMADEUS_ENABLED`, `AMADEUS_KEY`, `AMADEUS_SECRET` | Optional hotel fallback and credentials. |
| `MENTRO_GATEWAY_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `MENTRO_SERVICE_EMAIL`, `MENTRO_SERVICE_PASSWORD` | Optional agent gateway and dedicated service account; leave service credentials unset when the agent is disabled. |

Both templates fix `LOCAL_PREVIEW=false`, `ROUTING_REMOTE_URL=''`, and the
production browser origins including `https://roadtrips.elischiffler.dev`.
Keep host-port publishing loopback-only and PostgreSQL unpublished. A healthy
`/health` means the process runs; `/ready` additionally checks connection and
the four expected application tables. The latter is a limited readiness
signal, not a schema/migration compatibility proof.

The API emits `kind=ops` JSON lines to stdout with a fixed service, event,
method/status/duration, ISO 8601 timestamp, level, and bounded message made
only from those fields. Request path, query, headers, body, and user identity
are never inputs to the event formatter. Raw Uvicorn and application output
can contain private data and must remain outside the monitor feed. The host
operator owns filtering on `kind=ops`, collector, file permissions, size and
retention policy for any future
`/var/lib/hosting-ops/logs/roadtrips-api.jsonl` feed. No host file is mounted
by this Compose template.

## Release gates

Before accepting this API, inventory the live Neon schema, extensions, and
migration history; verify a complete backup and restore; review write freeze
and rollback/reconciliation; and test with actual isolated Cognito and two
users. Re-run authenticated trip, itinerary, chat, memory, ownership,
persistence, browser reload, and recovery against the restored database and
real providers. The local signed-token/fixture journey proves only the local
path. After backend acceptance, configure API DNS/TLS and CORS preflight,
then change the frontend `VITE_BACKEND_SERVER` and rebuild it. Keep the current
frontend target until that sequence is complete. No production deployment is
configured or authorized by this template.
