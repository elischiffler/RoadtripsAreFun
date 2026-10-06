# Live Studio planning progress

The building-route box on `/studio` consumes actual backend progress through
`POST /studio/run/stream`. Visitor session and trip validation run before stream
headers. This endpoint calls the same `algorithm_lab.run` as ordinary JSON runs,
so provider calls, validation, storage and returned route/itinerary stay shared.
No fixture trips or timed stage simulation are introduced.

The existing request-local progress reporter transports events from a private
worker loop, preserving updates and ten-second heartbeats while synchronous
provider calls block that worker. Streaming responses disable proxy buffering;
reverse proxies must preserve incremental NDJSON delivery. Disconnect cancels
at the worker's next async boundary; bounded synchronous provider I/O may finish
first. A cancelled run can remain unfinished in history and is not counted as
completed. The client cancels reads, ignores late updates and times out after
45 seconds without data. Progress does not retry or restart a billable trip.

Nine steps explain form validation, OpenCage city/timezone resolution, the
Mapbox base route, live place verification and AI ratings, integer CP-SAT
selection, separate hotel/visit scheduling, final road timing, itinerary and
result persistence. Live counts report sampled points, scored candidates,
threshold-eligible candidates, solver status, selected attractions and hotel
searches. AI ratings remain labeled estimates. Hotel prices and timing remain
separate checks after the attraction-subset model; the display does not claim
joint optimization or that every requested attraction will be delivered.

Each stage shows Waiting, In progress, Done or Failed from actual backend events.
Completed stage summaries are retained without an unbounded event log. Generic
nested Mapbox events cannot move a completed parent phase backward. Heartbeats
keep the connection alive and do not advance phases or estimate a percentage.
A polite live region announces the current activity; details disclose how each
step supplies inputs or validates results. No raw provider request or credential
is included in streamed errors. The final envelope still feeds the existing map,
itinerary, evaluation and saved-result viewer.

The header link now reads **Back to home page** and navigates to `/`.

## October 5 verification

On `codex/production-release`, all 699 backend tests passed with 87.00% coverage
and all 296 frontend tests passed with 90.05% line coverage. Ruff and frontend
format/lint checks passed; the production build passed with the existing bundle
size warning. Locked dependencies from the validated release were reused.
Stream tests cover split Unicode frames, heartbeats, interrupted transport,
HTTP/stream errors, pre-header authorization/validation, callback failure,
cancellation, and late authentication rejection against a newer visitor session.
Existing worker tests verify progress delivery during blocking I/O and cancellation.

A real coastal-nature run displayed six actual route samples with changing
provider/rating counts before delivering 2/2 attractions, a 118-mile route and
a saved dated itinerary. The building box was captured during live AI rating
collection, not simulated. The home link was confirmed as `/` in the browser
and component tests.

Rebuilt preview containers at implementation `9f053ee` passed both smoke checks.
Disposable PostgreSQL project `roadtrips-crud-a0d6f31c46` passed CRUD, ownership,
result persistence, recovery, recreation and backup/restore. Test containers were
stopped; source/restore volumes and the private backup were retained. No production
deployment or main merge was performed. Live announcements sit outside the busy input form.

## Inspecting a finished run

Algorithm details now contains **Run data by stage** instead of generic completion
messages. Collapsed rows show useful summaries; expanded rows show precise JSON
for validated inputs, resolved cities/timezones, retained direct-route metrics,
candidates/weights/query points, solver output and selected candidates, final
scheduled stops/hotel quotes, final route geometry/timing, and the dated itinerary.
Raw distances/durations and coordinate ordering are labeled. Missing data stays
explicitly unavailable. Failed stages can show the retained sanitized error.

The initial upstream Mapbox response and intermediate scheduler response are not
retained; their rows say so. Scheduling data is drawn from the final validated
route, not presented as an intermediate provider response. JSON renders only
when its disclosure opens and has a bounded scroll area, preserving numeric
precision without making a large candidate or geometry payload fill the page.
This frontend change adds no new backend response data or provider calls.

Frontend validation passed 300 tests with 90.14% line coverage, formatting, lint
and production build. Four new tests verify faithful data/precision, escaped
place names, lazy rendering, final route/itinerary output, and missing/failure
records. The existing build bundle-size warning remains.

Browser validation used a fresh live coastal-nature run: 26 retained candidates,
six route samples, three eligible candidates, two selected attractions and a
119.8-mile saved route. The selection disclosure showed actual solver objective
and bound 1,040,004, exact solve time, threshold, selected candidates, scores,
contributions and provenance. No fixture trip was used for this browser check.

## October 5 failure diagnostics and retry validation

The [retry contract](studio-retries.md) adds safe exception causes and upstream
HTTP statuses to top-level errors and failed-stage data, retaining them together
with failed/recovered attempt records in experiment JSONB results and history.
Provider retries use three total attempts without a nested AI retry loop.

Final checks: frontend 305 tests, 90.20% line coverage, format/lint/build passed
(existing bundle-size warning); backend 710 tests, 87.26% coverage, Ruff checks
passed with the unchanged 63% gate. Controlled faults verified 429/503 recovery
and exhaustion, immediate 400/401/403 stops, transport errors through wrapped
causes, cancellation, credential redaction, honest local versus upstream status,
Mapbox attempt metrics, and errors beside retained candidate data.

Disposable PostgreSQL project `roadtrips-crud-5142ceb944` verified failed-stage
errors and attempts in history/results, owner isolation, connection recovery,
recreation and backup/restore. Its source/restore volumes and backup are retained.
Final source preview rebuilt under `local-studio-retries` and passed both
container smoke checks; preview containers were stopped. These isolated checks
use the checked-in schema, with no production migration/schema claim.

The user's Medium two-day preset was rerun twice with live providers. Both
completed with 4/4 attractions, a 653.3-mile / 11.5-hour route and a $151 hotel
quote for two adults and children aged 7 and 12. Map and dated itinerary were
verified, including final arrival in Boise on October 7. The discarded cause of
the original AI ratings failure cannot be recovered; neither rerun reproduced
it, so a provider policy block has not been established.
