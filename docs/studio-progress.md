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
