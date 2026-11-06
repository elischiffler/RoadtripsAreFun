# Incident gate evidence — November 6, 2026

This records local synthetic verification, not a live provider/account test or a
production deployment. The latest complete native run passes the positive and
negative cases below. The corrected container wrapper still needs its next
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

## Previously failing negative case

The subsequent expired-departure attempt produced the actual NDJSON error status
422, did not execute the solver again and left the trip count at one. The UI
remained below completion (70%) and did not show a saved result. However, its
message was still the generic “The planning service could not finish. Your draft
is kept. Please try again.” rather than an actionable departure rejection.

The first full gate therefore remained **failing**, intentionally, at its assertion that
the expired departure explains the need for a future date/time. Fix the actual
stream/client error contract before claiming the full gate passed. Do not inject
a message in the fixture or relax that assertion. `.artifacts/failure.json` and
`.artifacts/failure.png` record this later failure.

## Strict positive and negative follow-up: passed

After the application introduced its typed `departure_not_upcoming` contract and
the frontend's matching status/code allowlist, the actual static-browser journey
was rebuilt into a separate output directory and rerun against a fresh marked
disposable PostgreSQL database. The full browser command exited zero. Creation,
save/reload, persisted visit/undo and saved-itinerary reopening passed again.
The expired attempt returned the actual NDJSON event with status 422 and code
`departure_not_upcoming`; the browser displayed exactly “Choose a departure date
and time in the future.” The solver still ran once, the database still contained
one trip, and the failed attempt had no saved result or 100% progress. The fixture
did not inject or replace the error message. Unexpected browser/network attempts
and page errors were empty. `.artifacts/result.json` records the passing run.

## Container wrapper follow-up

[The first PR64 container run](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/42312379976)
passed image building, smoke tests and the isolated Python suite. It passed the
journey's image checks and fresh PostgreSQL initialization, then correctly failed
the required workflow because `/journey/fixture.py` evaluated a native-only
`parents[2]` path before selecting the Docker `/app` source root. The bootstrap
now selects the existing Docker source root first, so the shallow mounted path
does not get indexed. No check or assertion was removed. The corrected wrapper
must pass CI on the final candidate before release; native success alone does not
establish that container execution.

[The following run on head `90817465`](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/42313074948)
passed that bootstrap point and warmed the actual API database pool. Its retained
`/ready` check correctly returned 503 because schema-only initialization had no
active nonempty catalog generation. Initialization now also applies the existing
`tests/postgres/catalog-fixture.sql` inside the same fresh disposable database:
one explicitly synthetic import, one place and the active pointer. No readiness
override or application health change was made. A fresh local rerun returned
actual `/ready` HTTP 200 with `status:ready`; the active generation's declared
and actual row counts were both one. The entire strict static-browser positive
and expired-departure journey passed again against that seeded database. The
next container CI execution remains required.

Node syntax, Python compile/Ruff, Compose configuration and whitespace checks
pass. Independent review checked the fixture isolation, real execution seams,
native progress assertions, persisted visit/undo assertions, database target
guards and image revision checks. Those checks and the full native pass do not
replace the outstanding corrected container-wrapper run.
