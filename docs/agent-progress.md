# Developer route progress

The chat UI uses authenticated `POST /agent/chat/stream` in development and
production. A single subtly pulsing text line shows the current process step,
falling back to "Thinking…" between stages. It has no card, background, border,
timer or expandable history. Labels map the backend's actual stage events to
traveler-facing descriptions. Status is transient, resets each turn and is
excluded from saved chat logs. Reduced-motion users receive static text.

Development builds also show `[RouteProgress <request id> +<elapsed>s]` console
messages while a turn runs. The API helper retains the existing JSON
`POST /agent/chat` path for callers without an `onProgress` callback.

The stream is newline-delimited JSON. Progress frames include a request ID,
sequence, stage, state, elapsed milliseconds, and optional duration/counts.
The single terminal `result` frame contains the existing AgentChatResponse;
an `error` frame contains an HTTP-equivalent status. Invalid credentials are
rejected before stream headers or events are sent. Auth/owner selection rules
are identical to the existing endpoint, and responses are not cached.

Stages cover detail extraction, model/tool calls, attraction query counts,
CP-SAT selection, overnight searches, hotel HTML/detail verification and AI
ratings, final Mapbox rerouting, itinerary building, and memory persistence.
Hotel diagnostics show the resolved city/check-in and counts rejected for
unusable price/link, identity mismatch, absent address, failed geocoding or
distance. They contain no credentials, raw prompts, response HTML, or route
geometry. City/date are the authenticated traveler's own trip data. Counts
and timings describe work completed; they are not a percentage or ETA.

A ten-second heartbeat logs the active stage during long provider calls. The
stream runs the existing turn in a private worker event loop so synchronous
legacy network/model calls cannot block delivery of those heartbeats. The shared PostgreSQL pool uses thread-safe checkout and locked lazy
initialization, with the existing five-connection limit. There
is no second turn or duplicate request. A disconnected stream cancels the
worker's turn at its next async boundary; a synchronous call already in flight
may finish up to its existing provider timeout first. Completed writes remain
completed. The client aborts after forty-five seconds without headers/data,
returns a structured failure for malformed/interrupted streams, and clears
the loading bubble even if response processing throws.

Progress reports are request-local and do not persist in the database. Stream
queues are capped at 256 frames (old progress may be dropped if delivery falls
behind); terminal results are retained. Existing debug/profile logs remain.

`complete_trip` preserves a nonretryable route provider failure instead of
rewrapping it as a retryable argument error. This stops the current turn before
it attempts an itinerary without a route or repeats a failed hotel lookup.
An expired token when saving messages is a separate authentication failure;
progress does not refresh or bypass Cognito credentials.

Regression coverage checks early events and heartbeats before a deliberately
blocking provider finishes, concurrent-request isolation, disconnect cleanup,
error scrubbing, invalid-token rejection, split/Unicode browser frames, final
response preservation, and nonretryable nested completion failures.
