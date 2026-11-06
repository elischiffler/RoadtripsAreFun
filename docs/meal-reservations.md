# Reserved meal breaks

New guided trips opt in with `reserve_meal_slots: true` on the final-route request.
The returned `Route` persists that flag. The default is false: old saved routes,
manual planner callers, and their existing itinerary timings remain unchanged.
`include_meal_slots` remains the legacy itinerary-only advisory display option;
for a reserved route it never adds advisory rows beside real reservations.

## Defaults and partial days

No meal-duration preference existed in the current trip settings. This change
uses the existing local windows and explicit planning defaults:

| Meal | Local window | Full reserved duration |
| --- | --- | --- |
| Breakfast | 07:00–09:00 | 30 minutes |
| Lunch | 12:00–14:00 | 45 minutes |
| Dinner | 18:00–20:00 | 60 minutes |

A meal is eligible only when its complete duration fits the intersection of its
window and the meal-free nominal trip bounds. A nominal 12:00–12:10 trip does not
acquire a 45-minute lunch; a 09:00 departure does not manufacture a predeparture
breakfast. These fixed bounds decide eligibility only. Once earlier breaks delay
activities, an eligible lunch may finish after the nominal destination instant
while still fitting its 14:00 window. Such delay does not make a previously
ineligible later meal eligible.

During route estimates, the nominal horizon uses baseline driving and visits,
extended by the selected overnight rest intervals. After Mapbox returns actual
legs, the authoritative clock first computes meal-free timing over those exact
legs, visits, chosen hotels and restart times. That fixed layout is the final
nominal baseline. Validation does not add hotels or recursively expand its bounds.
The estimate and actual-leg baseline can differ; actual-leg checks may reject a
candidate that its initial estimates allowed.

## Scheduling and failure

Driving time pauses for the reserved duration, and measured road durations remain
unchanged. The clock generally defers a driving break until its latest feasible
start, allowing an earlier unsplit attraction visit when a full meal still fits
afterward. Published opening waits can contain a meal. Visits are never split;
a visit moved after a meal must fit its source calendar again. Eligible deferred
breaks are accounted for before the final destination, including zero-duration
final legs.

Dinner and breakfast can occupy existing hotel rest time. The chosen morning
restart is not silently moved. When an early restart leaves insufficient hotel
idle time for breakfast, breakfast pauses the following drive instead. Hotel
searches budget meal time when choosing overnight progress. Actual driving
cutoffs, dated hotel checks and source-calendar admission remain authoritative.
Timed optional evening outings that overlap reserved breaks are withheld.

A full break that cannot fit its window or final driving cutoff produces a 422
planning failure, rather than an overlapping itinerary. The streamed transport
exposes only the dedicated `meal_schedule_conflict` code and a fixed public
message. Other provider errors retain their existing redaction. The guided client
does not save or announce completion when itinerary validation fails.

## Meaning and persistence

A meal reserves elapsed time, not a restaurant, parking space or safe stopping
location. No meal venue is recommended or added as a route waypoint. Extra
parking, road access and detour time cannot be verified until a place is chosen.
The user must choose a safe stopping place.

The next known physical stop's IANA timezone supplies a driving segment's planning
clock; the exact location of an in-drive meal is unknown. UTC elapsed durations
are preserved through timezone and daylight-saving changes. Meal identity is the
local planning date and meal type, preventing duplicate reservations when clocks
change. This is a timezone approximation, not a claim that a meal location was
geocoded. No additional provider calls are made to find meal locations.

Each physical stop owns recomputed `meal_breaks` metadata. The itinerary renders
those as `kind: meal`, `status: reserved`, aware arrival/departure timestamps,
window bounds and `duration_seconds`, with no place/provider identity. The API
never trusts caller-supplied meal intervals: final validation and itinerary
rebuild recompute them. Reserved routes lacking a complete dated policy route or
verified timezones are rejected and require replanning. Old route data is not
migrated or overwritten. Rebuilding a valid reserved route is deterministic and
does not repeatedly add its meal time.

Offline regressions exercise partial days, published-hours waits and visits,
measured long legs, hotel restart variants, final cutoffs, zero-duration final
legs, source-free wait notices, DST/timezone changes, stale or forged intervals,
legacy behavior, evening conflicts and allowlisted streamed errors. Hosted
Neon, live Mentro and live provider trips are excluded from these tests.
