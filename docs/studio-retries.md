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

Terra live attraction and optional evening discovery additionally share a
process-wide pacer (`routing/terra_pacing.py`). Only one Terra request is in flight
at a time, with at least `TRIPADVISOR_REQUEST_INTERVAL_SECONDS` between
starts. The default is 1.1 seconds, with a validated minimum of one second,
matching Terra's shared 1 rps search/nearby bucket while leaving arrival-time
headroom. The documented five-request burst allowance is deliberately unused.
Existing run-local single-flight deduplication and adaptive query budgets remain.
AI ratings and Mapbox work can continue while Terra is queued.

Discover's separate package quota is 10,000 calls per rolling 24-hour window;
pacing cannot fix daily quota exhaustion. No account-wide quota counter or new
cross-trip response cache is introduced. Terra's
[caching policy](https://docs.terra.tripadvisor.com/docs/caching-policy) permits
only Location ID caching unless a contract explicitly allows other content.

A Terra 429 doubles the start interval up to sixteen times the configured minimum
and pauses every queued Terra query, including other trips, for the greater of
Retry-After and a 5/10/20/40/60-second backoff. Successful requests gradually reduce
the interval toward its configured minimum. The existing three-attempt cap and
safe status/cause diagnostics remain authoritative; the pacer adds no retries.
Cancellation releases the pacing lock without sending queued requests. Optional
evening discovery retains its existing deadline and may return no suggestions
while Terra is cooling down.

Pacing is shared across private event loops in one API process. Multiple API
processes/hosts using the same key need a shared external limiter or a sufficiently
conservative interval per process. The legacy, unregistered greedy planner's
synchronous Terra helpers do not use this pacer. Restart the API to load changes
to the interval. Live quota/reset behavior still requires provider evidence.

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

## October 5 Terra pacing verification

Python 3.12.14 and Ruff 0.16.7: backend format/lint passed, and all 755 backend
tests passed with 87.96% coverage (63% threshold unchanged). New regression checks
cover cross-loop serialization, start spacing, shared Retry-After cooldowns
(seconds and HTTP date), exponential backoff without a valid header, gradual
recovery, transport failure and cancellation while queued or cooling down.

The initial environment produced 754 passes and one existing development CORS
preflight failure because its allowlist omitted `http://127.0.0.1:5173`. A first
test-process override included only development origins and consequently failed
two preview/public-origin checks. The final run supplied all five configured
development, preview and public origins only to pytest; saved config and CORS
source remain unchanged. Frontend/container/PostgreSQL checks were not rerun for
this backend provider-only change. Live Terra acceptance and account quota usage
remain unverified; no new live requests or deployment were performed.
