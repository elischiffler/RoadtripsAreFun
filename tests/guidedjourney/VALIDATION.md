# Incident gate evidence — November 6, 2026

This records local synthetic verification, not a live provider/account test or a
production deployment. The required Local containers wrapper still needs its
GitHub CI execution after integration. No hosted database or live Mentro request
was made.

## Reproduced save failure

The actual current guided UI was built with Vite in production mode using only
fixture endpoints, then served as static `dist` on loopback. Its requests passed
through actual FastAPI, RS256 JWT verification, LivePlaceProvider, local HTTP
Supabase/Mentro SSE adapters, rating/duration parsers, CP-SAT, actual-leg timing,
itinerary construction and real disposable PostgreSQL.

The pre-fix CREATE path from release `275950a` reached the endpoint and failed at
`chat_api.chat_add` → `chat_crud.create_chat` → `json.dumps(chat_data)` with
`TypeError: Object of type datetime is not JSON serializable`. Nested typed
`Route.departure_time` remained a Python datetime because the endpoint used
`model_dump()` without JSON mode. The uncaught 500 lacked the normal CORS header,
so Chromium surfaced Axios `Network Error` and the UI remained unsaved at 96%.
The disposable database contained zero trips. This was not a client matching-ID
guard failure: a read-only debugger confirmed a present token, matching subject,
and matching numeric record/snapshot ID. No credentials or headers were exported.

Ignored evidence: `.artifacts/base-save-failure.png` and
`.artifacts/base-save-failure.json`.

## Positive flow after the JSON serialization fix

With the actual CREATE/UPDATE JSON-mode fix subsequently committed as
`af7d5729b8e65b8dba10868b00bcb9aca73634a7`, the same static UI and provider fixtures
successfully created a future trip and received HTTP 200 from the actual saved
trip endpoint. It opened and reloaded its itinerary from PostgreSQL, persisted a
visit update, reloaded that visited state, persisted undo, then reopened the saved
trip and confirmed the same stop was unvisited. Both PUT requests returned 200.
Browser page errors and unexpected external requests were empty. The real solver
executed once; local gateway rating and duration requests executed twice each.
One account-owned trip existed in PostgreSQL.

Ignored evidence: `.artifacts/happy-result.json`, `.artifacts/saved-trip.png` and
`.artifacts/reloaded-itinerary.png`. The fixture is deliberately synthetic at the
external provider/catalog boundary and does not prove live provider correctness.

## Known failing negative case

The subsequent expired-departure attempt produced the actual NDJSON error status
422, did not execute the solver again and left the trip count at one. The UI
remained below completion (70%) and did not show a saved result. However, its
message was still the generic “The planning service could not finish. Your draft
is kept. Please try again.” rather than an actionable departure rejection.

The full gate therefore remains **failing**, intentionally, at its assertion that
the expired departure explains the need for a future date/time. Fix the actual
stream/client error contract before claiming the full gate passed. Do not inject
a message in the fixture or relax that assertion. `.artifacts/failure.json` and
`.artifacts/failure.png` record this later failure.

Node syntax, Python compile/Ruff, Compose configuration and whitespace checks
pass. Independent review checked the fixture isolation, real execution seams,
native progress assertions, persisted visit/undo assertions, database target
guards and image revision checks. These checks do not replace the outstanding
full container-wrapper and fixed negative-case runs.
