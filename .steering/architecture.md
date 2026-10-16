# Architecture and ownership

## Application boundaries

`backend/app/main.py` registers routing, location, car, itinerary, saved-trip storage,
Algorithm Lab and visitor Studio routers, CORS, process health and database
readiness. HTTP inputs are Pydantic
models; routers translate errors and reuse shared planning capability functions. `frontend/src/main.jsx` mounts the app; `Router.jsx` defines home,
login/signup, protected trips/map/itinerary/settings pages and visitor `/studio`.
The old `/algorithm` page redirects to `/studio`; `GlobalHeader.jsx` hides the
header on Studio, login and signup.

`backend/app/utils/auth.py` verifies Cognito access tokens using RS256/JWKS,
issuer, expiry/issued-at, token use and configured app client. Verified `sub`
owns stored data. Browser provider routes require a Bearer access token;
`/health`, `/ready` and static `/algorithms` remain public. Enabled `/benchmark`
is authenticated. CORS does not authorize requests.

`backend/app/routing/selection.py` alone decides interactive algorithm selection.
Only the configured owner with a verified matching Cognito ID token and verified
email may override the registry default. Non-owner overrides are ignored; unknown
owner selections fail validation. Interactive planning ignores environment
algorithm overrides. `frontend/src/services/routingSettings.js` obtains eligibility
from the backend, keeps selection in session memory and invalidates it on account
or token changes. See `docs/owner-routing-settings.md`.

## Shared trip state and AI

`app/agent/` retains its package name for shared consumers. `TripProfile`, persona,
departure/date validation, extraction, providers, diagnostics and progress are used
by planning and Studio. The conversational loop, prompts, dispatcher and API are
retired; see [removal details](../docs/journeygenie-removal.md).

`utils/location_resolution.py` provides validated provider candidates. Planning
APIs own validated endpoints, occupancy, budgets and local scheduling policy.
The Mentro gateway's provider protocol is shared infrastructure, independent of
the removed conversational HTTP endpoints.

## Route planning and provider boundaries

`routing_api.py` obtains an initial Mapbox route, chooses the eligible planner,
loads effective persona weights, builds `PlanOptions`, invokes injected
`RoutingServices`, and reroutes through selected stops using Mapbox. Actual final
leg durations are checked against the daily window before returning the route.
`routing_remote.py` forwards access and optional identity tokens to a separately
deployed routing backend, which must independently enforce the same contract.

`routing/sources/persona_candidates.py` separates model proposals/attribute ratings
from provider-verified names, coordinates and hotel prices. Backend utility is a
weighted sum of canonical attribute ratings; AI coordinates/prices/final scores
are not trusted. Attraction and optional evening identity/coordinates come from
licensed mixed-source records in PostgreSQL, with release, attribution and
upstream evidence dates. The first bounded catalog release was deployed in PR #40;
later reviewed releases and attributed calendar companions are also merged.
Catalog totals and live journey acceptance remain separate evidence. See
[rollout and rollback](../docs/neon-places-catalog.md) and the
[integration audit](../docs/tripadvisor-removal.md). Unknown hours are not
invented; empty coverage returns no places. `sources/google_hotels.py` verifies
dated totals, identity, addresses and a 30-mile radius. Limits/deadlines and
failure behavior are owned by source constants and `docs/hotel-prices.md`.

Provider verification does not establish subjective attribute ratings: those
are model estimates. `LocationProfile` now types provider facts, canonical ratings and provenance.
`routing/profiles.py` owns the shared crossmatch/contributions, with ratings
generated from the canonical persona vocabulary.

`planners/cp_sat.py` builds a typed adaptive discovery plan, balances bounded
nearby/rating pools across equal baseline driving-time sections, and road-checks
all shortlisted candidates before solving. The solver selects K eligible places
within ten percentage points of the best achievable average match, minimizing
all baseline gap deviations plus measured solo detour time. Candidate capacity is
18–60; query/rating budgets and sparse coverage remain inspectable. Production
eligibility keeps finite positive utilities. Source-calendar feasibility filters
records before discovery quotas, road checks and the bounded shortlist.
`trip_calendar.py` owns that necessary-condition test; `visit_calendar.py` owns
hard visit windows and full two-hour dwell. Unknown or expired timed calendars
fail closed. Final-road conflicts trigger bounded reselection with cached road
checks; neither guessed opening hours nor an objective penalty can permit a
closed visit.
See `docs/adaptive-planning.md` and `docs/cp-sat-explained.md`.

`cp_sat_scheduler.py` schedules two-hour visits and
uses `models/scheduling_policy.py`: preferred hotel 18:00, hotel cutoff 20:00,
restart 09:00, default final destination cutoff 21:00, with optional overrides.
It tries up to six overnight positions around the preferred point and ranks
usable hotels by per-room budget compliance, utility, price, distance and ID.
`routing/travel_timing.py` shares actual-leg timing with itinerary construction.
See `docs/flexible-hotel-evenings.md`, `docs/arrival-timing.md` and
`docs/travelers-and-hotel-occupancy.md` for integrated scheduling/occupancy rules.

The current objective minimizes spacing and detour seconds (`balanced-route-v3`).
Scheduling and hotel cost remain separate, with final live road timing validation.
Historical surplus scores retain their original meanings. `base.score_trip()` is
a legacy benchmark metric, not this objective. Ordinary Route output stays
compatible. Request-local explanation captures discovery budgets, road checks,
quality bounds, selection and solver diagnostics through existing JSONB storage.
Studio `/studio` uses shared live planning; `/algorithm` redirects. Replay requests
are rejected. Thread-compatible process permits bound leaf calls across private
worker event loops; HTTP clients and request deduplication are confined to one
run. Ratings/geocoders/solver work use bounded threads. See the adaptive contract
for dependency barriers, retries and cancellation behavior.

Stop dictionaries carry `name`, `type`, `coordinates` in **[lat, lon]**, leg
`duration`, and hotel `price` with optional address/url/warning. Mapbox geometry
uses **[lon, lat]**. `models/routing_models/routing_models.py` and
`models/itinerary_models.py` own HTTP models; keep conversion at explicit boundaries.

## Frontend and persistence

`pages/SavedTripsPage.jsx` loads account-owned saved trips through
`services/savedTrips.js`, retaining existing payload names. Choosing a trip records
its ID for map and itinerary navigation and reload. The retired `/chat` bookmark
redirects to `/trips`. New planning uses Studio until guided setup is integrated.

`crud/chat_crud.py` owns chats/route segments/steps and the shared thread-safe
five-connection PostgreSQL pool. `crud/memory_crud.py` reuses it for `chat_memory`:
cross-chat facts/persona, per-chat summary, trip profile and saved planned route.
Reads/writes use authenticated owner/chat scope; historical ChatLog content stays in storage. `schemas/chat_schemas.py` accepts optional presentation in JSONB.
No new table migration is required for these JSON additions. Disposable DDL is
`tests/postgres/schema.sql`; production readiness confirms expected table presence,
not complete column/schema compatibility or migration history. Source catalog
generations use `catalog/repository.py`, `backend/sql/places_catalog.sql` and
`backend/sql/places_catalog_calendars.sql`; calendar companions retain attributed
source evidence without overwriting immutable base rows.

## Algorithm Lab run measurements

`app/crud/lab_runs.py` owns owner-scoped `algorithm_lab_runs` storage;
`backend/sql/algorithm_lab_runs.sql` owns its additive migration.
`app/routing/run_metrics.py` owns request-local instrumentation, canonical hashes
and statistical aggregation. Only Lab runs activate capture; chat runs are excluded.
See [run history contract](../docs/algorithm-run-history.md).

## Public Studio session boundary

`routers/studio.py` exposes `/studio/access` and signed visitor-session endpoints
for presets, runs, history and saved results. It reuses `algorithm_lab.py` planning
and scoped storage under a random `studio:<uuid>` identity. It grants no Cognito
account access or algorithm override. Frontend `/studio` uses this session; old
`/algorithm` links redirect. The owner-only API remains private. See
[Studio access](../docs/studio-access.md) for expiry and deployment secrets.
