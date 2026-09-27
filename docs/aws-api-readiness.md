# Roadtrips API production template

`compose.prod.yaml` is the API-only template for the proposed shared host. It
builds the backend from a reviewed full commit SHA, publishes container port
8000 on host loopback port 8002, and keeps PostgreSQL private. The host proxy
would route `api.roadtrips.elischiffler.dev` to `127.0.0.1:8002` after HTTPS,
readiness, CORS, authenticated trip, persistence, and recovery checks pass.
`compose.yaml` remains a disposable local preview with fixtures.

The Compose project uses a separate egress network for Cognito, routing APIs,
and optional Mentro/Supabase calls, plus the external `roadtrips_database`
network for the future same-host PostgreSQL. That network and the database are
owned by `hosting-ops`; they are not created by this template and do not yet
exist on the shared host. Do not start the production template until the
reviewed database restore and network provisioning are complete. Neon is still
the live database. An interim Neon deployment would require its own reviewed
network and TLS configuration rather than silently reusing this cutover
template.

Set `ROADTRIPS_REVISION` to the checked merged-main full SHA and place
`.env.production` in the project directory using the host's protected secret
delivery process. The file is Git-ignored and must never be copied from a
developer machine. Required names for the proposed database cutover are:

| Name | Purpose |
| --- | --- |
| `DATABASE_URL` | Private `postgres:5432` app-user connection string; credential is secret. |
| `DATABASE_SSLMODE` | `disable` only on the dedicated same-host database network; `require` or `verify-full` with a trusted root for remote databases. |
| `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID` | Trusted access-token issuer and client. |
| `MAPBOX_API`, `TRIPADVISOR_API`, `OPENCAGE_KEY` | Routing and geocoding provider credentials. |
| `CAR_DATA_API`, `GOOGLE_PLACES_API` | Provider credentials where the corresponding routes are enabled. |
| `AMADEUS_ENABLED`, `AMADEUS_KEY`, `AMADEUS_SECRET` | Optional hotel fallback and credentials. |
| `MENTRO_GATEWAY_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `MENTRO_SERVICE_EMAIL`, `MENTRO_SERVICE_PASSWORD` | Optional agent gateway and dedicated service account; leave service credentials unset when the agent is disabled. |

The template fixes `LOCAL_PREVIEW=false`, `ROUTING_REMOTE_URL=''`, and the
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
