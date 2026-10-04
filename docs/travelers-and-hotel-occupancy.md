# Travelers and hotel occupancy

`TripProfile.traveler_count` is the total party including the person typing and
the driver. `hotel_rooms` is the explicit room allocation: each room has an
integer `adults` count and a required `child_ages` list (empty confirms no
children). Room occupants must sum to `traveler_count`. Count does not imply
adult occupancy, room allocation, or companion personalities.

Example collection:

- Assistant: “How many people are going, including you?”
- Traveler: “Five of us: three adults and two children, ages 5 and 8.”
- Assistant: “How many hotel rooms do you need, and who is in each room?”
- Traveler: “Two rooms. Two adults and the 5-year-old in one, one adult and the
  8-year-old in the other.”
- Assistant confirms five travelers, the two allocations, and a nightly budget
  **per room** before planning.

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

Old saved chats remain readable. Missing occupancy blocks new prices and
itinerary generation; no two-adult default is substituted. A count correction
clears the previous room allocation. Room/count changes invalidate the UI's
route and itinerary, and saved-route retry requires the same validated profile.
Confirm the replacement allocation and regenerate to obtain new prices/links.

Effective preferences are called **Trip personality**. Only interests explicitly
supplied by the typing user guide those weights; headcount never changes them.
Internal `persona_weights` keys, account defaults, trip override precedence and
owner/chat isolation are preserved. Account tools remain labeled saved
preferences across trips and require explicit save-for-future-trips intent.

Fixture tests cover collection/readiness, old chats, corrections, independent
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
