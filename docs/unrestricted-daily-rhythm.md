# Recurring driving and daytime sleep

Explicit daily rhythms retain 24 hourly `drive` / `rest` / `sleep` slots in
`route_local` time, exactly one cyclic driving block and one cyclic sleep block.
Wrapped driving, daytime sleep and multiple travel cycles are supported; they
are not rejected because of time of day. Existing overnight-count bounds,
strict one-day eligibility below 12 hours, complete actual-road validation,
source admission/calendars, occupancy and bounded hotel lookup remain in force.
Availability is not a guarantee that every possible combination is feasible.

## Travel cycles and local clocks

A cycle is anchored to the local date on which its driving block begins. Early
hours in a wrapped 20–06 block belong to the preceding cycle date. The next
restart is the next block's start, not an assumed morning. Hotel arrival and
booking dates are derived separately in the hotel's verified IANA zone. Final
actual Mapbox legs must remain inside the same availability deadline; an
unavailable clock after a timezone change fails rather than inventing a safe
roadside wait. Durations use UTC elapsed seconds across DST. Ambiguous/missing
relevant local sleep/drive/meal boundaries fail explicitly rather than choosing
an offset. Neighboring meal cycles outside the trip are ignored before strict
localization.

## Awake-relative meals

Only explicit rhythms shift the existing default meal windows by
`local sleep end hour − 07:00`; durations remain 30, 45 and 60 minutes. For sleep 08–16,
breakfast is 16–18, lunch 21–23 and dinner 03–05 the following calendar date. The
meal ID retains the wake-cycle date: that next-date dinner belongs to the
preceding date's awake cycle. Windows may cross midnight (wake 23 produces
breakfast 23–01). Meal timestamps include actual local dates and offsets.

Full, unsplit meals must fit awake hotel rest or driving/visit gaps, never sleep.
The same clock is used in estimated scheduling, final-road validation, itinerary
rebuild and route-edit previews. Eligibility uses fixed meal-free trip bounds;
one delayed break cannot recursively require more meals. Short trips therefore
do not manufacture a meal just by touching a window. Short awake cycles can be
infeasible and raise the existing typed meal conflict. The UI states that meal
breaks follow the sleep schedule. Meals reserve elapsed time only; no dining
venue, parking place, safe stopping point or extra detour is verified.

No-rhythm and sleep-end 07 defaults preserve their prior meal windows and keys.
No-rhythm policy serialization and frozen research/evaluation inputs remain
unchanged. Viewing existing saved content does not rewrite it; explicit rebuilds
and edit previews always recompute clocks instead of trusting stored meal rows.
Switching back to a legacy policy also discards copied derived rhythm blocks,
lodging display metadata and rhythm notices; booked dates and room offers are
retained rather than silently rewritten.

## Full dated hotel quotes

The original hotel source's one-night date assumption is extended to a bounded
full check-in/check-out range. Each room offer must confirm that exact range,
room occupancy, full-stay USD total including taxes/fees, and price scope. Every
room's independently verified total is summed once; a one-night price is never
multiplied into a multi-night quote. Search/detail controls and the booking URL
stay token carry the same requested dates. Checkout is part of request-local
room cache keys, so one- and two-night requests cannot alias. Default legacy
one-night lookups still require an effective one-night return and keep their
old absent-checkout wire shape and price scope.

The physical hotel rest interval and quoted reservation dates are different
concepts. For explicit rhythms we use the app's existing 18:00 arrival / 09:00
restart defaults as a conservative planning envelope, **not published hotel
hours**: arrival before 18:00 backs the check-in date up one day; departure after
09:00 extends checkout one day. Equality retains the ordinary one-night range.
Thus planned 08:00–18:00 daytime rest requests the prior day through the following
day: a real two-night total. A broader early-arrival/late-departure combination
can require three nights. The 24-hour recurring shape bounds a single physical
rest interval; the quote envelope is at most three calendar nights.

Consecutive daytime rests at different hotels may need overlapping calendar
night ranges. Each whole quote is retained and summed; overlapping nights are
not deduplicated. This conservative coverage can cost extra nights compared to
a standard night stay. The nightly budget remains advisory per room/night:
compare each full-stay quote against `budget × quoted nights`, and retain/display
the full quoted stay total, not an assumed nightly rate. Per-night variability
and simultaneous/continuous inventory across separate room quotes remain
unverified. Hotel access times still require confirmation even when dates fit.

A booking range beginning before the hotel's current local date fails before
hotel provider work. After actual road rerouting, changed required dates or
inconsistent room/date/total coverage reject the plan. Saved rebuild/edit cannot
trust copied `lodging` fields; quote dates and all room offers are checked and
physical timing/notice regenerated. Missing coverage on a new explicit-rhythm
stay requires a new quote. The internal meal-free timing pass is provisional;
only the final meal-aware clock validates actual quote coverage, including edits.

Private hotel and itinerary rows receive additive `lodging`:

```json
{
  "check_in_date": "2030-06-01",
  "check_out_date": "2030-06-03",
  "nights": 2,
  "planned_arrival": "2030-06-02T06:00:00-07:00",
  "planned_departure": "2030-06-02T20:00:00-07:00",
  "access_status": "confirmation_required",
  "notice": "Confirm check-in, checkout and continuous room access for the full quoted stay. Planned rest times, including daytime or after-midnight use, are not guaranteed."
}
```

The dates/nights label a quote, not a booking or check-in guarantee. The shared
public projection stays unchanged and omits this private lodging metadata.
New full-stay failures use fixed `lodging_stay_conflict` 422 copy; arbitrary
provider text is not exposed. No runtime schema migration or DB mutation is
needed. No live provider/model requests were made to validate this work; bounded
HTML fixtures and provider leaves prove the local contract, not current Google
markup or actual hotel inventory acceptance.
