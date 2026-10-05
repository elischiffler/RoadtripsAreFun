# Studio failure diagnostics and bounded retries

Studio returns a safe cause chain, failed stage and actual upstream HTTP status
when available. Gateway stream error codes/messages are retained; arbitrary
exception text, upstream URLs, credentials and response HTML are omitted.
A historical run that saved only an error code cannot recover a discarded cause.

Each retryable provider operation gets **three total attempts**, with one and two
seconds between attempts unless an applicable Retry-After supplies a delay.
HTTP permits are released during backoff. Timeouts, connection faults, HTTP 408/429/5xx and known
transient gateway stream errors qualify. Authentication/configuration errors,
unknown failures, invalid inputs and solver infeasibility are not blindly retried.
The existing gateway empty-completion loop is replaced by the same bounded loop,
so AI requests do not acquire nested three-by-three retries. Provider retries do
not restart the whole trip or repeat completed planning stages. Hotel discovery retries individual failed HTTP/geocoder calls; it does not
restart a successful listing lookup or multiply three attempts through parent retries.
Spatial hotel-search attempts remain a separate scheduler policy.

Live progress identifies the active operation and next attempt. Failed/recovered
attempts are recorded in the run envelope, including their operation, attempt
number, classification and safe cause, including available query/section/rating-batch
identity. Concurrent event sequence numbers and counters are synchronized.
Disconnect cancels queued/dependent work. Unavoidable synchronous in-flight work
retains its permit until real completion; late results are ignored. The top error panel and failed-stage JSON
both expose these diagnostics even when partial stage data exists. History's
Inspect disclosure shows saved errors after reload within the same Studio session.
Existing JSONB result storage holds errors, stages and attempts; no DDL change is
needed. Route availability continues to govern the map/itinerary button.

Verification is recorded in `docs/studio-progress.md`. Tests use controlled faults;
real trip acceptance uses live providers.
