# Visit duration and arrival/leaving clocks

New attraction plans use a bounded visit estimate after source identity and
preference ratings are available. The existing rating provider receives place
identity/address/category, available activity details, labeled activity ratings,
traveler preferences, and backend match/contribution context. Utility is a
preference match, never a duration formula. The prompt forbids invented hours,
activities and booking availability. No provider, credentials or access settings
are added.

The optional response must identify supplied places and give integral minutes
from 15 through 360. Values round up to five-minute blocks. Invalid, missing,
duplicate or out-of-bound output uses a labeled two-hour conservative planning
fallback; provider failure uses the same fallback. Neither a fallback nor a short
estimate relaxes a calendar hold, closing time, fixed start or daily cutoff.

Validated estimates are cached under a hash of prompt/provider namespace, source
identity/release, details, ratings, preferences and match context. The process
cache holds at most 512 immutable estimates: 24 hours for AI estimates and five
minutes for fallbacks. It stores no prompt or traveler identity. Request-local
singleflight and existing AI worker limits also apply. A cache hit never skips
the current source-calendar or actual-road validation.

`visit_duration` in route/itinerary JSON carries schema version, elapsed seconds,
source and reason. The shared validator reads that value for requested-trip
feasibility, CP-SAT opening windows, initial scheduling, final actual-road timing
and itinerary reconstruction. Unknown/malformed source hours and explicit holds
are ineligible for new plans. The discovery minimum is 15 minutes until an
estimate is available, followed by a full exact-dwell check. Fallback-feasible
records get priority before bounded discovery/rating quotas so narrow windows
cannot crowd out a usable fallback plan.

Saved stops without this optional metadata retain the prior two-hour policy;
no trip or database migration is required. Explicit malformed duration metadata
is rejected rather than silently shortening an existing visit. Old untimed trips
keep their labeled unknown-hours behavior. Regenerating a route creates a new
plan and uses the new verified-hours requirement.

Route and itinerary place cards share a formatter for arrival and leaving,
including local date, IANA zone and UTC offset. Leaving carries the AI/fallback
estimate label. Final destinations show arrival only. Source attribution,
addresses, booking links, quotes and notices remain in their existing sections.
The API retains departure rows for compatibility and marks those already paired
with a place; the new UI suppresses only those duplicate rows. Stored legacy
itineraries still render.

Synthetic tests cover output bounds, partial/duplicate/invalid responses,
fallback/cache behavior, full-window/fixed-start/hold checks, midnight/DST,
variable overnight placement, actual-road daily deadlines, reload and consistent
route/itinerary display. These fixtures establish no real opening hours, model
quality, road times or production acceptance.

PR #41 integration remains a release dependency: its offline pipeline and daily
active-time evaluation must consume variable visit durations, including waits,
instead of assuming 7,200 seconds per attraction. Complete that follow-up after
PR #41 reaches `develop`, then return the rebased exact head for independent
review. The calendar-correction and parent release gates still apply.
