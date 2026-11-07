# Progressive route preparation

The road estimate now prepares unscheduled catalog ideas and tentative stay search
areas before explicit candidate assessment. It neither starts AI nor searches hotel
quotes, writes a trip, reserves a place, or decides one-day eligibility.

## Bounded authenticated reads

`POST /route-preparation/stream` requires the existing verified account dependency.
Its body contains known GeoJSON road geometry (2–10,000 points), finite road driving
duration, departure wall-clock and the existing validated scheduling policy. A
400 ms stable-input debounce prevents continuous slider movement from starting a
scan per edit. Changing the road, date, time, rhythm, owner or session immediately
hides obsolete results and aborts the previous request. At most four successful
results live in component memory for 60 seconds; source failures are not cached.

The endpoint makes at most six sequential five-mile catalog samples, distributed
by road-geometry distance, accepting at most two ideas per sample and twelve in
total. It uses the current catalog repository's active-generation admission,
release-hold and calendar-presence checks, and the existing public place projection.
Sparse samples can omit places. A source calendar is not evidence that a place is
open on the selected travel date: actual trip assessment still performs that check.
There are no external geocoding, road, hotel or model calls in this endpoint.

The shared process-limited routing runtime bounds catalog concurrency. Browser
abort cancels the stream/worker at an asynchronous boundary and prevents subsequent
section reads. Already-running synchronous database work can finish; cancellation
is not a promise of immediate SQL interruption. Partial source failures return
partial/unavailable status without source exception messages and do not block the
traveler from explicitly checking trip options.

## Tentative stay areas

Up to three points follow the known road curve. Road driving duration is distributed
by geometry distance; speed, attraction detours and waits are not inferred. Driving
windows delimit each day's approximate road capacity. Full meal allowances use the
single backend-owned `meal_windows` policy, including its wake-relative windows for
explicit rhythms; an allowance is only included where a full interval fits within
the driving block. These are estimates, not actual reserved meal events.

The calculation uses the departure wall-clock throughout. It does not establish
arrival-local timezone, DST, room availability, check-in access or quote coverage.
Visits, detours, local clock changes and meals outside a driving block can move the
areas. Invalid explicit departure hours yield no hint. Legacy first departures
before the normal morning restart retain their earlier first-day capacity.

Every area is marked `tentative: true`, `hotel_quotes_checked: false`,
`availability_checked: false`, and
`clock_basis: "departure_wall_clock_estimate"`. An absent hint says nothing about
whether stays will be needed. Candidate responses retain these hints separately
from the real candidate route and timing proof. The UI says "Tentative stay search
area" and explicitly disclaims hotel availability.

## Actual candidate progress

Existing candidate NDJSON streams now publish bounded `route.preview` scenes at:

- `considering`: actual discovered candidates after the planner's admission/calendar
  filter, before road detours/selection; displayed as unscheduled ideas.
- `selected`: the actual CP-SAT selection, still subject to scheduling and final
  timing; displayed as proposed stops.
- `checking`: the actual rerouted road geometry before final timing validation.

Every scene has `preview_only: true`. Public scenes retain only name, coordinates,
type and provider identity, with at most twelve stop pins and 10,000 geometry points.
Private interest weights, ratings and provider/source blobs are omitted. Early
`preparation.areas` progress retains at most three tentative areas. Preview events
cannot confirm a trip, trigger saving or signal 100% completion. Account/request
ownership guards discard late progress. The final route, actual timing checks and
explicit mode confirmation remain authoritative. Confirmation transport and retry
semantics are unchanged.

## Verification and remaining limits

Focused offline backend tests cover actual admission/hold projection, limits,
partial failure redaction, account guards, cancellation, real CP-SAT scene order,
legacy and wrapped rhythms, shifted meal allowances, zero geometry, dateline
interpolation, invalid inputs and candidate lifecycle regressions. Frontend tests
cover streaming transport/auth reuse, request serialization, debounce/cache keys,
partial rendering, immediate abort, late route/account events, tentative labels,
pin bounds and no-save/no-completion progress. Full suite results are recorded in
the branch handoff. Native integrated overnight verification remains a separate
release gate; isolated unit checks do not claim live hotel/provider verification.

Isolated branch verification on 2026-11-07: 73 focused backend tests passed
(`route_preparation_tests`, `planning_candidates_tests`, CP-SAT planner and guided
flow suites). Ruff passed for all changed Python sources/tests. Full guarded
frontend coverage passed 603 tests in 76 files, with 92.66% line coverage;
formatting, lint and production build passed. Build retains the existing large
bundle warning. Backend full-suite and actual native overnight coverage are left
to the combined integration gate to avoid competing with the rhythm backend lane.
No live provider, model, hosted database or production request was made.

The first combined backend run exposed a preview-only compatibility regression:
legacy planner geometries can provide coordinates without a Pydantic serializer.
The follow-up projects only known type/coordinates from mapping or attribute
containers; malformed display geometry is omitted, and no private serializer or
metadata is used. Actual planning geometry and the frozen regression fixtures are
unchanged. Both previously failing files plus preparation, CP planner, candidate
and guided-flow suites now pass together: 96 tests in 3.01 seconds. Ruff and diff
checks pass. Final combined full coverage remains an integration gate.
