# Flexible hotel evenings

## Scheduling contract

`app/models/scheduling_policy.py` owns optional trip preferences. The same
`scheduling_policy` object is persisted in `TripProfile`, sent in `Route_Payload`
over local/remote routing, saved on the resulting `Route`, and used by the
CP-SAT scheduler, final Mapbox validation, and itinerary generation:

```json
{
  "preferred_hotel_arrival": "18:00",
  "latest_hotel_arrival": "20:00",
  "morning_restart": "09:00",
  "late_driving": false,
  "late_cutoff": "24:00"
}
```

Clocks are local HH:MM. Morning restart must precede preferred arrival;
preferred <= latest <= late cutoff. The cutoff never exceeds 24:00. Preferred
arrival is a soft hotel target. Latest arrival is the normal feasibility limit
for both hotels and the final destination. Only an explicit late-driving choice
extends that limit. A departure after the preferred arrival is valid if it
precedes the effective cutoff. First-day departure need not equal morning restart.

The traveler can say "I can drive until midnight", "Restart at 10:30 AM",
"Prefer hotels at 5 PM, latest 7 PM", or "No late driving". Extraction passes
only explicit choices to `record_trip_details`. Scheduling patches merge with
the saved policy; invalid preferences receive clarification while valid sibling
trip fields are retained. These preferences add no required planning questions.

The scheduler retains every selected daytime attraction and its two-hour visit.
When all remaining attractions plus the destination fit the effective cutoff,
it avoids an extra hotel. Otherwise it searches at the preferred target, 30
minutes earlier/later, 60 minutes earlier, the effective cutoff, then 2.5 hours
earlier: at most six distinct corridor points, capped before the next selected
attraction. Existing verified dated Google Hotels sourcing, radius checks,
provider errors, nightly-budget preference and actual prices remain authoritative.
The final Mapbox detours must pass the hard deadline again; a route that fails
is rejected with a feasibility explanation rather than relaxing the bound.

Live scheduling resolves actual start/stop/hotel/destination IANA timezones
through the existing OpenCage reverse geocoder, cached within a request. Missing
timezone verification blocks planning with a clear error. Travel durations
advance through UTC; local deadlines and morning restarts use IANA calendar
rules, including DST. Ambiguous/nonexistent wall-clock choices are rejected.
Offline injected services may use their fixture clock.

`travel_day` and `check_in_date` identify the travel/booking night. A November 21
travel day can arrive exactly at 00:00 November 22 when late mode allows 24:00;
00:01 fails. The hotel search still requests November 21-22 and departure is
09:00 November 22, or the explicitly selected restart. No automatic earlier
restart is used to rescue a plan. Actual arrivals are saved as offset-aware ISO
timestamps and displayed in the arrival location's timezone. Late arrivals show
"Confirm late check-in with the hotel"; a dated price is not reception verification.

Older profiles receive explicit policy defaults. Older saved routes with no
policy retain their original next-calendar-day 09:00 itinerary behavior.
New route timing and suggestions round-trip in existing chat JSON and memory
records, without a database migration.

New routes also save `departure_time`. A direct itinerary request may omit
`start_time` and reuse the saved departure, preserving its travel/booking night.
Policy routes saved before that field existed recover departure from the first
actual arrival minus its driving-leg duration, converted to the saved origin
timezone. An explicit `start_time` takes precedence. Legacy routes without
policy/timing metadata retain their existing fallback behavior.

## Optional suggestions

`evening_interests` accepts `food`, `culture`, and `nightlife`; `[]` explicitly
disables discovery. If omitted, above-baseline effective persona weights in
these categories can trigger it. The equal default persona does not. Discovery
uses the already selected hotel's coordinates; it never relocates the hotel.

At most two alternative suggestions are attached to a hotel, separate from
daytime attractions and route waypoints. Options must be provider identified,
have valid coordinates and an information link, lie within 2 km, and have
Mapbox driving legs of at most 15 minutes each way. The feasibility envelope
includes 30 minutes for check-in/rest and a one-hour visit, with return before
the effective cutoff. Late arrivals with insufficient time skip discovery.
Both suggestions are alternatives: choose one, not two consecutive visits.

The existing Terra API supplies categories, place status and weekly opening
periods ([provider field reference](https://docs.terra.tripadvisor.com/reference/locationget)).
Weekly periods do not establish date-specific holiday exceptions. The live
adapter therefore returns tentative suggestions labeled "Check opening hours",
with no assigned visit or return time. Unknown category adds "and venue category".
Closed places are excluded. A provider adapter may supply dated, aware opening
intervals; only then, with a verified category, can an optional visit time be
shown. Fixtures prove this path; no live date-specific adapter is claimed.

Discovery has an eight-second budget across the route, four seconds per hotel,
and three-second HTTP timeouts. Progress uses the existing minimal animated
status line. Provider failures/no results/timeout do not change route completion,
daytime stop counts, hotel prices or budget warnings. Suggestions survive reload;
itinerary departure overrides hide visits that no longer fit rather than showing
stale times. No reservation, new paid service, credentials or deployment is added.

## Fixture itinerary example

All times below are local to America/Los_Angeles. This is a controlled example,
not a real provider listing:

| Time | Activity |
| --- | --- |
| Nov 21, 09:00 | Depart |
| Nov 21, 18:00 | Actual arrival at the verified hotel |
| Nov 21, 18:40 | Optional nearby cafe, if dated hours are verified |
| Nov 21, 19:50 | Suggested return to hotel |
| Nov 22, 09:00 | Depart hotel |

With the current live adapter, the cafe appears unscheduled with "Check opening
hours" and "Return to hotel by: 08:00 PM". A midnight hotel arrival has no outing.

## Validation and remaining acceptance

Run the commands in AGENTS.md. Focused backend tests are
`pytest tests/routing/flexible_hotel_tests.py tests/routing/evening_tests.py
tests/agent/scheduling_contract_tests.py`. They cover early/preferred/later stays,
bounded misses, reroute deadlines, explicit opt-in, no extra hotel, selected
attraction preservation, timezone/DST, midnight/month/year rollover, policy
patches, remote payloads, JSON/NDJSON, optional discovery failures and reload.
`ItineraryPage.test.jsx` covers optional labels and actual local arrival display.
`tests/postgres/run.mjs` also checks the policy and suggestions in both chat and
planned-route memory through recreation and real backup/restore.

Local validation on October 3, 2026, against the integrated implementation
(including the concurrent detail receipts and direct-reply guards):

| Gate | Result |
| --- | --- |
| Backend pinned Python 3.12 suite | PASS: 541 tests, 85.08% coverage (63% required) |
| Ruff 0.16.7 format and lint | PASS |
| Frontend Node 24 install, format, lint, coverage and build | PASS: 164 tests |
| Rebuilt preview container smoke | PASS: 2 tests |
| Disposable real PostgreSQL | PASS: ownership, policy/suggestion persistence, recreation, outage recovery and backup/restore |

The disposable PostgreSQL runner retained source/restore volumes and its ignored
backup; the final run used project `roadtrips-crud-94c16c0960`. These are local
fixtures, not production schema or provider acceptance. The departure-recovery
follow-up `87a91c9` on `codex/hotel-evenings-integration` builds on integrated
shared head `079dc41`, retaining its single scheduling policy. Its three new
HTTP regressions cover omitted departure, saved departure and explicit override.
Container smoke used a separately rebuilt preview on ports 18004/18084 after
health checks completed; an earlier startup-race attempt was rerun successfully.

Live provider/model/Cognito planning, actual travel durations, hotel date/price
availability and reception/late-check-in acceptance remain BLOCKED pending
isolated real-provider validation. Fixture or container success does not replace
that gate. Keep PR #26 draft. No production deployment is configured by this change.

A separate follow-up could convert the existing main Mapbox client's synchronous
`requests.get` inside an async function to async HTTP, reducing worker blocking.
This feature's optional discovery uses async HTTP already; the broader client
change is outside this scheduling assignment.
