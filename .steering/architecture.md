# Architecture and ownership

## Application boundaries

`backend/app/main.py` registers routing, location, car, itinerary, chat and agent
routers, CORS, process health and database readiness. HTTP inputs are Pydantic
models; routers translate errors and reuse capability functions also called by
agent tools. `frontend/src/main.jsx` mounts the app; `Router.jsx` defines home,
login/signup and protected chat/map/itinerary/settings pages.

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

## Agent turn and trip state

The JSON and NDJSON endpoints in `backend/app/routers/agent_api.py` run the same
turn. `app/agent/agent.py` loads owner/chat memory, calls `extraction.py` for a
strict JSON patch of the latest supplied details, and passes it through
`tool_dispatcher.py`'s `record_trip_details`. Invalid fields produce clarifications
while valid siblings persist. Extraction has one format retry. Outage recovery
and validated receipts are backend behavior, not evidence that a model always
extracts all traveler intent correctly.

`TripProfile` owns endpoints/coordinates, pending location choices, stop count,
traveler count and explicit room allocations, per-room nightly budget,
local departure time, canonical departure datetime/timezone,
car choice and trip persona overrides. `missing_details()` is shared by prompt
staging, presentation and completion. `trip_dates.py` rejects invalid, past or
ambiguous/nonexistent local departure times; `departure.py` shares normalized
departure handling. `persona.py` owns the 14 canonical weights, equal defaults,
normalization and account-versus-trip override rules.

`utils/location_resolution.py` yields up to five validated, deduplicated provider
candidates. Multiple candidates or bare two/three-letter abbreviations require
confirmation, even for a single match. `agent/location_confirmation.py` resolves
only opaque IDs in the authenticated chat's saved pending state; no model tool
can confirm them. Origin selection clears the old date while retaining local
time. Endpoint changes invalidate displayed route/itinerary. Failed revisions
retain prior confirmed endpoints but pending state prevents planning with them.

`prompt.py` supplies a short invariant, stage instructions and complete schema-
serialized trip state, refreshed after tools. Recent conversation is bounded to
six 400-character messages and a 600-character summary when full. Mentro gateway
SSE and its service-account authentication are owned by `providers.py`. Fenced
tool JSON is parsed by `toolcall_parser.py`; the loop caps tool batches at five.
Heavy geometry/itineraries stay in artifacts/actions rather than model context.
Usage totals aggregate extraction and continuation model calls.

`complete_trip` uses stored confirmed endpoints, validates required details and
passes the same departure to route and itinerary adapters. Route success with
itinerary failure returns partial status and preserves `route_updated`; saved
planned routes permit a later itinerary retry when the profile still matches.
Required nonretryable provider failures stop that turn. `presentation.py` derives
receipts/questions/outcome notes from persisted state and validated tool outcomes;
model prose cannot establish whole-trip completion.

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
are not trusted. Terra verifies attractions; `sources/google_hotels.py` verifies
dated totals, identity, addresses and a 30-mile radius. Limits/deadlines and
failure behavior are owned by source constants and `docs/hotel-prices.md`.

Provider verification does not establish subjective attribute ratings: those
are model estimates. `LocationProfile` now types provider facts, canonical ratings and provenance.
`routing/profiles.py` owns the shared crossmatch/contributions, with ratings
generated from the canonical persona vocabulary.

`planners/cp_sat.py` uses shared `cp_sat_selection.query_count()` to query `min(30, max(6, 3*n))` route points for positive stop
counts, accepts at most 30 candidates, selects utility >=0.60, at most the
requested count and one candidate per nearest query slot. A deterministic
one-worker/seed-zero/five-second solve accepts only feasible/optimal outcomes.
Fewer attractions than requested can result; this is not a globally optimal
joint solve of real driving, hotel prices and venue opening hours.

At inspected head `53fd0bf`, `cp_sat_scheduler.py` schedules two-hour visits and
uses `models/scheduling_policy.py`: preferred hotel 18:00, hotel cutoff 20:00,
restart 09:00, default final destination cutoff 21:00, with optional overrides.
It tries up to six overnight positions around the preferred point and ranks
usable hotels by per-room budget compliance, utility, price, distance and ID.
`routing/travel_timing.py` shares actual-leg timing with itinerary construction.
See `docs/flexible-hotel-evenings.md`, `docs/chat-creation-arrival-timing.md` and
`docs/travelers-and-hotel-occupancy.md` for integrated scheduling/occupancy rules.

The CP-SAT objective maximizes integer-scaled match surplus above 0.60 plus a
small stable tie preference. Scheduling, hotel cost and real detour durations
are outside that model. `base.score_trip()` is a legacy benchmark metric, not
the solver objective. Ordinary Route output keeps its compatible shape. The owner Lab uses
request-local `routing/explanation.py` to capture candidates and solver diagnostics
from `routing/cp_sat_selection.py`. `routers/algorithm_lab.py` reuses existing
owner auth, trip validation and shared live planning; all new runs persist independent experiment history. Replay requests are rejected.
The frontend `/algorithm` page uses server catalog values and shows details on
demand. See `docs/senior-demo-plan.md` for its API and limits. See `docs/cp-sat-explained.md` for the exact formulation.

Stop dictionaries carry `name`, `type`, `coordinates` in **[lat, lon]**, leg
`duration`, and hotel `price` with optional address/url/warning. Mapbox geometry
uses **[lon, lat]**. `models/routing_models/routing_models.py` and
`models/itinerary_models.py` own HTTP models; keep conversion at explicit boundaries.

## Frontend and persistence

`pages/ChatPage/useTripWorkflow.js` is now the agent-driven orchestration hook,
applying `route_updated`, `itinerary_updated` and `trip_profile_updated` actions to
the saved `ChatData` view. `ChatPage.jsx`, `DatabaseUtils.jsx` and
`states/UserDataContext.jsx` own selection, reload and user-session state. Stable
UUID `agentChatId` identifies backend memory; integer UI chat IDs are a separate
identity. Browser snapshots/UI hints remain advisory.

`ChatMessage.jsx` renders escaped native detail lists and pending-choice buttons.
`agentChat.js`/`agentProgress.js` consume the authenticated stream; `TripProgress.jsx`
renders one transient status line. `agent/progress.py` and `progress_stream.py`
own request-local events, bounded queues, worker execution and cancellation.
Progress is excluded from saved chat logs. See `docs/agent-progress.md` for exact
timeouts and disconnect limitations.

`crud/chat_crud.py` owns chats/route segments/steps and the shared thread-safe
five-connection PostgreSQL pool. `crud/memory_crud.py` reuses it for `chat_memory`:
cross-chat facts/persona, per-chat summary, trip profile and saved planned route.
Reads/writes use authenticated owner/chat scope; the frontend owns verbatim
ChatLog writes. `schemas/chat_schemas.py` accepts optional presentation in JSONB.
No new table migration is required for these JSON additions. Disposable DDL is
`tests/postgres/schema.sql`; production schema/history remain unverified.

## Algorithm Lab run measurements

`app/crud/lab_runs.py` owns owner-scoped `algorithm_lab_runs` storage;
`backend/sql/algorithm_lab_runs.sql` owns its additive migration.
`app/routing/run_metrics.py` owns request-local instrumentation, canonical hashes
and statistical aggregation. Only Lab runs activate capture; chat runs are excluded.
See [run history contract](../docs/algorithm-run-history.md).
