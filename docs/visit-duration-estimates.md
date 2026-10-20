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
and itinerary reconstruction. Existing calendar policy is preserved: ordinary
outdoor places without required calendars remain eligible with explicitly unknown
hours; adding an estimate never invents or verifies hours. Timed venues still
require usable calendars, malformed/explicitly held calendars remain ineligible,
and full visits must fit any published window and the daily cutoff. The
discovery minimum is 15 minutes until an
estimate is available, followed by a full exact-dwell check. Fallback-feasible
records get priority before bounded discovery/rating quotas so narrow windows
cannot crowd out a usable fallback plan.

Saved stops without this optional metadata retain the prior two-hour policy;
no trip or database migration is required. Explicit malformed duration metadata
is rejected rather than silently shortening an existing visit. Both saved and
new untimed outdoor trips keep their labeled unknown-hours behavior; estimated
dwell still counts in scheduling, final road validation and leaving times.

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

PR #41 is integrated from reviewed `develop` head
`fcd795af63f40ca7233cc4d45514acf50013dc0f`. Its offline provider now reads
context-matched, immutable duration captures, or labels a missing-capture
two-hour fallback. It never requests a fresh estimate. Capture contexts include
the original source name/details, ratings, preferences and utility contributions;
changed context cannot reuse a duration by ID or score alone. Real captures
require model/prompt/configuration/time provenance predating the evaluation
clock, plus matching per-entry capture IDs and bounded estimates. See the
evaluation fixture README for the optional format.

`balanced-route-v5` daily active time sums measured driving, elapsed visit
timestamps and opening waits, excluding hotel rest. Missing, negative or
conflicting timing leaves that day's total and the maximum unassessed, rather
than publishing a partial total. Preselection workload screening reports the
15-minute–6-hour range and leaves exact visit time unknown; its optimistic
minimum remains explicitly separate from an infeasibility proof. Synthetic
offline tests cover a short opening window, waits, capture invalidation/isolation,
provenance, DST and agreement with route/itinerary clocks. The calendar-correction
and parent release gates still apply.

The reviewed PR54 frozen-catalog fix is integrated from `develop`
`aa41b8f10c2bd449a6bd6c17c51bae9dfb92915f`, including the seven-calendar
correction. Its validated `Fixture` lookup remains server-only and preserves
the shared identity/hold guard; ordinary HTTP/agent calls use active facts.
Additional synthetic regressions run recognized Boulder/Overture namespaces
with 15-minute/three-hour captured visits and missing-capture fallbacks while
forbidding database/network reads. They assert unchanged fixture bytes, retained
source attribution, matching route/itinerary clocks and actual active-time
metrics. Cached short estimates, long visits and fallbacks cannot bypass any
of the seven holds, and rejected agent retries preserve saved duration metadata.
