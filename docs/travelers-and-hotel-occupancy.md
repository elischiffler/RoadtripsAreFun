# Travelers and hotel occupancy

`TripProfile.traveler_count` is the total party including the person typing and
the driver. `hotel_rooms` is the explicit room allocation: each room has an
integer `adults` count and a required `child_ages` list (empty confirms no
children). Room occupants must sum to `traveler_count`. Count does not imply
adult occupancy, room allocation, or companion personalities.

For five travelers comprising three adults and children aged 5 and 8, an explicit
two-room allocation can place two adults and the 5-year-old in one room and one
adult and the 8-year-old in the other. The nightly budget applies per room.

Google Hotels' guest selector was inspected on 2026-10-03: it allows at most
six guests per search, distinguishes adults from children, and requires child
ages 0–17. Ages zero and one share its “0 - 1” age band, encoded as one. The
application permits up to four independent room searches (24 total travelers),
with at least one adult per room. Four rooms is an application request bound,
not a claim about Google inventory. Booleans, fractions, missing ages,
inconsistent totals, and larger allocations require clarification.

Each room is requested separately using its adult count and child ages. Both
search and detail pages must confirm dates, occupancy and USD; existing tax,
price, identity, address and radius verification stays in place. Each lookup
keeps its six-detail, 60-second and HTML-size limits. At most four room lookups
run sequentially for each bounded scheduler attempt.

Only hotels with verified quotes for **every** requested room are offered.
Each quote retains its own price, occupancy and dated comparison link through
the route and itinerary. Multiple-room costs sum separately fetched quotes,
including for identical allocations; they never multiply one two-adult price.
The sum is labeled **independent room quotes**. Simultaneous inventory, room
types and bed arrangements must be confirmed with the booking provider; this
is not a combined bookable whole-party offer. There is no automatic booking.
Nightly budget remains per room; scheduling checks every room quote against
that budget and discloses any room that exceeds it.

Old saved trips remain readable. Missing occupancy blocks new prices and
itinerary generation; no two-adult default is substituted. Confirm the allocation
before regenerating to obtain new prices and links.

Effective preferences are called **Trip personality**. Only interests explicitly
supplied by the typing user guide those weights; headcount never changes them.
Internal `persona_weights` keys, account defaults, trip override precedence and
owner-scoped storage isolation are preserved. Historical account preferences remain in their existing store.

Fixture tests cover shared profile validation, old records, independent
room quotes, child ages and occupancy-specific links. Browser inspection
verified the guest controls and child token encoding, but does not establish
live server-side price acceptance for the scraper, all room combinations,
simultaneous inventory, a live model conversation or authenticated persistence.


## Validation and handoff (2026-10-03)

Based on shared feature head `a640743`; implemented on `codex/trip-travelers`.
Preserved flexible hotel deadlines, local timezones, midnight booking nights,
saved departure recovery, evening suggestions and formatted collection receipts.

- PASS: Python 3.12 pinned requirements, Ruff 0.16.7 format/check, 579 backend
  tests, 85.30% coverage (required minimum remains 63%). Tests include
  JSON/NDJSON collection parity, remote serialization, route/itinerary JSON
  reload, one/two/three adults, infant age band, children, multiple independent
  room quotes, per-room budget targets, mismatched occupancy rejection and
  invalidation of incomplete child corrections at unchanged headcount.
- PASS: Node 24 `npm ci`, `npm run format:check`, `npm run lint`,
  `npm run test:coverage` (168 tests, 81.05% statement coverage), `npm run build`.
- PASS: separately rebuilt local containers, `node --test
  tests/container-smoke.test.mjs` (2 tests). Task-owned smoke containers stopped.
- PASS: `node tests/postgres/run.mjs`, real disposable CRUD, owner isolation,
  recreation, outage recovery and backup/restore. Preserved source/restore
  volumes and ignored backup for `roadtrips-crud-440182cf10`.
- BLOCKED/unverified: live full-trip model and Cognito acceptance, live scraper
  prices for every occupancy, simultaneous multi-room inventory. Browser guest
  controls/token inspection and fixtures do not satisfy those gates. PR #26
  remains draft; no production deployment or schema migration is included.
