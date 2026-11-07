# Incident gate evidence — November 6, 2026

This records local synthetic verification, not a live provider/account test or a
production deployment. The latest complete native run passes the positive and
negative cases below. The corrected original container wrapper subsequently passed on final main
`42d5068bb4c8804a8024df0e4463fb05e0a7e275` in Local containers run
[42315083289](https://github.com/elischiffler/RoadtripsAreFun/actions/runs/42315083289).
The final combined Stage2 flow passed a fresh native execution at
`48204ece680feb2a10aff6f4692976717cf5a754`, recorded below; its final container
execution remains required. No hosted database or live Mentro request was made.

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


## Stage2 combined journey — November 7, 2026

The mandatory browser gate now follows the combined five-stage setup and `/trip`
workspace. Its assertions cover a real reserved lunch (duration/window, no visit
overlap and arrival elapsed-time accounting), sequential modern visit revisions
without reload, actual stale-revision HTTP 409 with unchanged PostgreSQL state,
along-route browse and explicit replacement preview/save/reload, reusable
preference profile create/edit/reload/reuse, and separate trip-car persistence.
The preview is checked against durable state before saving. Existing expired-date
safe-error, no false completion/extra trip, actual non-owner research denial,
external-network refusal and 390px/1440px checks remain required.

Synthetic edit-place facts are supplied only at repository nearby/current-record
read seams, alongside the existing local source/geocoding/road/HTTP gateway
fixtures. Actual browse filters, current-fact validation, route-edit timing,
itinerary and scoped CAS CRUD remain active. The gate does not establish live
Cognito/Mentro/Mapbox acceptance, catalog SQL parity, every multi-day meal conflict,
or all possible saved-trip edit/race combinations.

Status: **fresh complete native journey passed** against the frozen application
checkpoint `0e2d0f345597311f66eaa8058b2316966227536c`, with a new Vite production
build served from a separate static output directory and a fresh empty marked
PostgreSQL instance. The command exited zero; its `finally` cleanup stopped only
its own API/static server and removed its own random PostgreSQL project.

The passing report contains two synthetic logins, one real CP-SAT solve, 13 road
adapter calls, nine candidate page reads, 13 browse reads, three current-fact
refreshes, two actual rating and two actual duration adapter calls. One saved
trip and two reusable profiles remain in the report. The explicit old revision
returned actual HTTP 409; route preview returned 200 and the subsequent save and
reload passed. Browser page errors, blocked external origins and prohibited
Python network attempts are all empty. The expired attempt returned the actual
422 `departure_not_upcoming` event without another save/solve or false completion.

Ignored local evidence: `.artifacts/result.json`, `.artifacts/happy-result.json`,
`.artifacts/saved-trip.png`, `.artifacts/trip-workspace.png` and
`.artifacts/reloaded-edited-trip.png`. The first attempt stopped at an overly
strict test locator for an implicitly labelled select; its retained
`initial-selector-failure` artifacts show that creation, meal timing, revision
writes and browse had already passed. Matching the actual combobox accessible
name fixed the locator; no application behavior or strict assertion was changed.

Source syntax, Ruff and whitespace checks pass. Independent read-only review
found no safety or coverage blocker. The exact integrated commit still requires
the normal Local containers CI gate; this native result does not replace it.

A separate fresh standard disposable PostgreSQL instance also passed
`tests/settings_postgres_tests.py::test_long_route_shortening_keeps_exact_geometry_initial_and_scoped_rollback`
(one test, 0.23s). This uses the real API/CRUD and segment-table transaction to
shorten 10,001 coordinates to two, retain the independent initial geometry,
preserve a foreign owner's rows and roll back a partial insert on an ownership
conflict. It supplies a synthetic endpoint identity rather than JWT verification;
the browser gate above covers the actual signed verifier. The instance used the
standard fixture's own required local credentials, fresh-schema guard and offline
runner with loopback only, and was removed afterward. Neither database target
guard was weakened to share credentials between the two fixtures.


## Registered candidates and daily rhythm — native execution passed

The gate is adapted to the combined registration → real candidate NDJSON stream
→ explicit one-day confirmation flow. It requires no AI before the explicit
check, no durable trip and no 100% progress after successful assessment, actual
server-derived under-12-hour proof including meals, no hotel calls, and no model
replay on duplicate assessment/confirmation or after cancellation. A second
actual HTTP candidate checks required overnight occupancy and an allowed short
flexible route with zero hotels, without another saved trip or new attraction AI.
Settings coverage now uses the actual 24-hour rhythm sliders/profile contract.
Existing save/reload, arrival correction/undo/CAS, route edit and metadata reset,
meals, car, non-owner auth, expired-date and viewport/network assertions remain.
Real device geolocation is blocked; automatic arrival positions are separately
mocked in their own harness.

Only lower external provider/repository seams are synthetic. No candidate
registration, assessment, proof, confirmation, scheduler, timing, auth or durable
storage behavior is stubbed. The hotel seam still rejects every call, so an
actual overnight hotel/sleep/rest/browser path is not claimed; those dated hotel,
rest/sleep, DST and infeasibility paths remain backend clock/API/integration
coverage. Source checks (syntax, Prettier, Ruff and whitespace) pass, and an
independent read-only review found no source blocker.

A fresh complete native run **passed** against frozen application checkpoint
`d07f6f75fc3b099e73ad120ffbafdc57df5ba2b2`. A new production-mode Vite bundle
used only fixture endpoints; the actual signed browser/API/CP-SAT/timing/CRUD
journey ran against a fresh empty marked PostgreSQL instance. The primary
candidate's actual elapsed time was 18,000 seconds, including its reserved meal.
Successful assessment had zero saved rows and progress below completion; only
explicit one-day confirmation caused the durable save. Repeated assessment and
confirmation reused work. Cancellation returned actual 410 without model or
solver replay. A second assessment rejected missing overnight occupancy with
actual 422, then accepted flexible mode with zero hotels and no additional
attraction AI. Actual itinerary construction validated that route's reserved
meal as well.

Save/reload, manual arrival correction/undo with sequential revisions, stale 409
with unchanged storage, route preview/save/reload and arrival-metadata reset,
24-hour profile create/edit/reload/reuse, separate car persistence, non-owner
Settings/research restrictions and 390px/1440px assertions all passed. The second
login's expired departure produced the actual typed 422 event and exact safe
future-date message without another save, solver call or false completion.
Final counts were two logins, three real solves, four rating adapter calls, two
duration adapter calls, six local gateway requests, zero hotel requests, one
saved trip and two profiles. Browser errors, prohibited browser origins/device
geolocation and prohibited Python network attempts were empty.

Fresh ignored evidence is `.artifacts/result.json`, `.artifacts/happy-result.json`,
`.artifacts/candidate-cache-result.json`, `.artifacts/saved-trip.png`,
`.artifacts/trip-workspace.png` and `.artifacts/reloaded-edited-trip.png`.
The native driver exited zero and removed only its own API/static process groups,
fresh random PostgreSQL project and temporary dependency symlink; fixture ports
were confirmed closed afterward. The exact final integrated commit must still
pass the mandatory Local containers CI gate before release. This native result
does not establish live Cognito/provider/device acceptance or replace that gate.


## Final readiness and shared-only Home follow-up — passed

The complete native browser/API/disposable-PostgreSQL journey was rebuilt and
rerun successfully against final frozen application checkpoint
`48204ece680feb2a10aff6f4692976717cf5a754`. All preceding candidate, proof,
cache/cancel, conditional occupancy, timing/meal, save/reload, revision conflict,
edit/reset, profile/car, research denial, viewport and expired-date assertions
passed unchanged. Actual `/ready` accepted the normal complete seeded schema.

The new Home checks awaited the final routing decision: an authenticated empty
owner reached `/plan`, and the same owner after saving reached `/trips`. The
owner created a capability using the actual revision-checked sharing API. A
second fixed synthetic account used real local SDK login and signed verification,
connected through the actual sharing API, then visited `/` and reached
`/shared-trips`. Its shared list and read-only trip/route outline rendered; owner
visit controls and private projection fields were absent. It had zero owned
trip rows; sharing left the owner's durable trip and model counters unchanged.
The capability remained only in memory, never in a URL or evidence artifact.

The final report contains three synthetic logins, three real solves, four rating
and two duration adapter calls, six local gateway requests, zero hotel requests,
one owned trip and zero participant-owned trips. Browser errors, prohibited
origins/device geolocation and prohibited Python network attempts were empty.
`.artifacts/home-entry-result.json` records the routing outcomes without
credentials or capability tokens. The fresh `.artifacts/result.json` and other
passing artifacts now represent this final run. Its command exited zero; own
API/static processes, random PostgreSQL project and temporary dependency link
were removed, with all fixture ports confirmed closed.

Separately, `tests/readiness_postgres_tests.py` passed all 17 actual-PostgreSQL
cases in a fresh standard guarded local database with the normal schema and
existing synthetic catalog seed. Real HTTP `/ready` connections were read-only.
A non-superuser effective app role with required grants returned 200; SELECT-only
sharing grants and each of eight individually missing privileges returned the
fixed 503. The session user remained privileged, proving checks use the effective
role. Each sharing table's absent name, missing column and wrong column type
returned fixed schema 503, and restored schema returned 200. Actual owner CRUD
still worked with both sharing table names unavailable. Test fixture changes
were restored and its separate disposable database/roles/project removed.
The normal PostgreSQL CI runner includes these tests after its existing catalog
seed; no readiness query, schema check or fixture target guard was bypassed.

The mandatory final exact-commit Local containers and PostgreSQL CI executions
remain required. These local results do not establish live Cognito, Mentro,
Mapbox, geolocation, true overnight-hotel browser acceptance or production schema
state.


## Unrestricted rhythm/true overnight extension — runtime pending

A separate test branch based on `4074181` prepares the sequential actual
browser/API/solver/timing/CRUD overnight extension described in README. It has
not yet run against the upcoming unrestricted-rhythm/progressive-preparation
application changes. Earlier passing checkpoints do not prove this new scope.
The hotel fixture supplies only remote provider records and exact requested
room/date quotes; actual candidate matching, model-response parsing, room
intersection, scheduling and durable storage are retained. Source assertions
now include the owners' two-night lodging/full-price metadata and actual
preparation/planner preview contracts. They still await a final combined
application checkpoint and actual native execution.
No hosted database, live provider/account or device location was used.
