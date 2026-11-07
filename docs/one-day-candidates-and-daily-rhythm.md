# Complete one-day candidates and daily rhythm

The original implementation started at reviewed PR67 head
`3a5494d5e7b1d7121982d86522e66045b2af3cb9`. It adds an explicit account-owned
assessment/choice flow. Existing route generation stays in `overnight` mode by
default, and policies without a daily rhythm retain their existing timing.
There is no deployment, migration, hosted database action or live provider test.

## Assessment and confirmation

The UI must start complete-candidate assessment only after an explicit action such
as **Check trip options**. Ordinary product assessment can use the existing
attraction rating/duration models; early background work must remain read-only
catalog/geocoding/initial geometry. The implementation and tests here use mocks.

1. `POST /planning-candidates/requests` with `{request_id: UUID}` allocates a
   lightweight owner-bound request record. No provider or model work runs. The
   response contains `request_id`, `expires_at` and `status: ready`.
2. `POST /planning-candidates` or `/planning-candidates/stream` takes the existing
   route payload plus that `request_id`. Hotel budget and rooms are optional;
   `reserve_meal_slots` is true. The stream uses the existing NDJSON progress/result
   framing. The server selects a hotel-free candidate, obtains the actual complete
   road route, refreshes admitted source facts, and validates local visits,
   opening waits, reserved meals and driving availability.
3. The response contains `candidate_id`, `input_key`, `expires_at`, `one_day`,
   `candidate_route` and `possible_overnight_areas`. `one_day` contains `eligible`,
   `elapsed_seconds`, `threshold_seconds: 43200`, `reason_code` and `reason`.
   Eligibility requires a complete valid candidate with strict aware UTC elapsed
   time **less than** 43,200 seconds. The initial driving estimate is not proof.
   `candidate_route` is present only if complete timing is valid; a candidate may
   be valid but exceed 12 hours. In that case eligibility is false. If timing
   cannot produce a valid candidate, the route is null and no eligibility is
   claimed. Upstream failures return a fixed error, never a successful proof.
4. `POST /planning-candidates/{candidate_id}/confirm` takes `input_key`,
   `trip_mode: one_day | overnight`, and conditional hotel inputs. One-day requires
   no hotel service, room list or hotel budget. It refreshes current source facts
   and recomputes the meal-aware clock before returning the server-owned route.
   Overnight requires consistent `traveler_count`, `hotel_rooms` and `budget`,
   then reuses only the bounded road-checked attraction pool. It does not repeat
   attraction discovery/ratings. Normal hotel lookup/rating is new work authorized
   by the explicit overnight confirmation. Allowing overnight stays does not force
   a hotel into a candidate that can finish without one.

A `route.preview` progress event carries actual final road `geometry` in [lon,lat]
and stop coordinates in [lat,lon], with `phase: checking` and `preview_only: true`.
It is an unconfirmed map preview; timing and eligibility are not established until
the completed response. No provisional hotel location is invented:
`possible_overnight_areas` is currently an empty list. Actual hotel stops in a
confirmed overnight route are the authority for hotel pins and quoted totals.

## Cancellation, input binding and uncertain requests

Requests and candidates live only in the current API process. Registration and
candidate lifetimes are each 15 minutes; there are at most 32 registered requests
and 32 retained candidates. A deployment/restart loses this cache and returns a
fixed 410. A miss never silently runs the models again. Multi-worker deployments
would need consistent routing or a separately reviewed shared store.

The request fingerprint binds confirmed endpoints/initial geometry, departure,
interests, stop count, party count and daily policy. Hotel budget/room inputs are
collected only for the later overnight choice. Changing semantic trip inputs must
cancel the old generation and explicitly assess a new one. Confirmation requires
the server's input key, rejects changed party count, and accepts no client route
or eligibility boolean.

Repeated identical registered assessment requests share one in-flight operation
or return its cached success/fixed failure. An uncertain response is retried with
the same UUID, without re-registration. Only a new explicit check action registers
a new UUID. Reusing a UUID with different inputs returns 409. Cache loss/expiry,
cancellation and registration absence all fail closed without model replay.

`DELETE /planning-candidates/requests/{request_id}` cancels pending work and
invalidates any completed candidate belonging to that request. It also works
before a candidate token exists. `DELETE /planning-candidates/{candidate_id}`
cancels an already identified candidate. Both derive account ownership from the
verified authentication boundary. Studio visitor identity grants no access.
Cancellation cannot undo a provider request already received, but no cancelled
result is stored or confirmed. A duplicate confirmation cannot start concurrent
work; completed identical confirmation returns the same route, while a changed
choice returns 409. None of these endpoints writes a saved trip.

All candidate routes and responses are `Cache-Control: no-store`. The dedicated
fixed error map in `backend/app/core/candidate_errors.py` owns public status/code/
text. Transport sanitizes typed errors against that map and redacts arbitrary
provider exceptions, including forged codes or wrong statuses. Clients must use
an exact status/code allowlist and their own text rather than arbitrary detail.

## Daily rhythm contract

Opt in with `scheduling_policy.daily_schedule`:

```json
{
  "timezone": "route_local",
  "slots": [
    "sleep",
    "sleep",
    "sleep",
    "sleep",
    "sleep",
    "sleep",
    "sleep",
    "rest",
    "rest",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "drive",
    "rest",
    "rest",
    "sleep",
    "sleep"
  ]
}
```

There are exactly 24 hourly labels. One continuous driving block and one continuous
sleep block are required around the cyclic clock; the remaining hours are rest.
Driving availability can cross midnight, such as 20:00–08:00. It is availability
for driving, visits and meals, not a claim of uninterrupted driving. Individual
legacy clock overrides cannot be combined with this opt-in rhythm. The example
is the proposed UI default: driving 09–20, sleep 22–07, rest elsewhere.

The rhythm owns the driving cutoff, preferred hotel-arrival boundary and restart.
Departure during rest/sleep fails before model work. A one-day night drive may
cross a calendar date if it stays within the valid drive block and full elapsed
proof remains under 12 hours. It cannot silently add an overnight stay. Actual
road timing enforces the lower and upper bounds in the next physical stop's
verified timezone; if a westbound clock change puts a positive leg into rest or
sleep, the server rejects it instead of inventing a safe roadside waiting place.
As with the existing meal clock, this is a next-known-stop planning clock; it is
not a timezone survey of every point along the road geometry.

Overnight planning supports wrapped driving, daytime sleep and repeated travel
cycles. Physical rest lasts from actual hotel arrival to the next driving
block, with full rest/sleep intervals shown on their actual local dates. Meal
breaks follow the sleep schedule: explicit rhythms shift the defaults relative
to local wake-up time, keep their full durations, and never overlap sleep.
Short awake cycles or conflicting visits/roads can still be infeasible; valid
rhythms are not rejected merely because of time of day.

Hotel booking dates are separate from physical rest times. The planner requests
real quotes for the full conservative check-in/check-out range, which can include
a prior night or additional nights for daytime rest. Every room's dated occupancy
and full-stay total must match; a one-night rate is never multiplied into a
multi-night offer. The advisory budget remains per room/night while the saved
cost is the sum of whole quotes. Actual rerouting, rebuild and edit revalidate
coverage. Hotel rows show distinct quote dates and planned arrival/departure with
a concise reminder to confirm check-in, checkout and continuous access. These
are quoted options, not bookings or a guarantee of daytime hotel access.

See [recurring driving, awake-relative meals and full dated hotel quotes](unrestricted-daily-rhythm.md)
for the coverage convention, midnight/DST behavior, preserved legacy defaults,
remaining shape constraints and live-provider acceptance boundary.

All durations use UTC-aware elapsed arithmetic across DST; local deadlines retain
IANA zones and booking/rest dates. Actual ambiguous/nonexistent drive or sleep
boundaries return fixed 422 guidance to choose another hour. An unrelated clock
change outside the actual stay cannot invalidate it.

## Persisted mode and rebuilding

`Route.trip_mode` defaults to `overnight` for old routes. Confirmed one-day routes
carry derived `one_day_proof` with elapsed seconds, threshold and validation time.
This metadata is display-only, not an authorization credential. The route model
keeps it in saved JSON. Itinerary generation and edit preview recompute the actual
meal-aware clock and enforce the strict one-day limit again. Supplied proof cannot
authorize a hotel or a longer edit; failures return conflicts and cannot be saved
as a successful preview. Public sharing projection must preserve the mode and
rhythm meaning when integrated, while retaining its separate privacy allowlist.

## Historical implementation verification

At the first implementation checkpoint, 65 offline focused regressions pass:
21 rhythm/one-day clock tests, 18 candidate API/cache tests, and 26 retained
reserved-meal/edit regressions. They include strict threshold boundaries,
opening waits/meals, actual versus initial roads, midnight/DST, timezone lower
bounds, source refresh, persisted edit/rebuild enforcement, conditional hotels,
owner/Studio rejection, capacity/expiry/restart, duplicate single-flight,
cancellation and provider-error redaction. Full Ruff checks pass. Subsequent full backend validation passed **2,848 tests, 151 skipped**, with
**81.83% coverage** (63% required), plus full Ruff formatting/lint. The full run
found and fixed an absent-rhythm serialization regression: only the new
`daily_schedule` field is omitted when None; all old None fields and the frozen
legacy policy fingerprint `221b934c1c1157c0e5407227fa8be84a8e60b86ad21cb861423d42c93ecc5d21`
remain intact. No frozen fixture was rewritten.

After that full run, a small independently reviewed shared-clock guard also closes
unsupported overnight rhythms on direct saved itinerary rebuild/edit, rather than
only on candidate confirmation. The final focused run passes **109 tests**:
42 frozen evaluation, 23 rhythm/mode, 18 candidate orchestration and 26 retained
meal/edit checks. The full run predates only this bounded guard and its regression.

Both implementation and final deltas were independently source-reviewed. Frontend
and combined integration acceptance remain separate gates. No test calls Mentro,
live provider endpoints or a hosted database.
