# Change map and active implementation

Snapshot: October 3, 2026, America/Los_Angeles. Inspected shared feature head
`6247a1e` (`codex/cp-sat-solver`) against main `92ac3af`. Git comparison covers
123 changed files, including tests, since main. Shared feature
[PR #26](https://github.com/elischiffler/RoadtripsAreFun/pull/26) is draft/unmerged.
The original primary checkout was clean at `620df3c`, two commits behind the
fetched feature head; refresh edits use an isolated worktree. Git and open work
can change while these notes are read: check status/fetch before integrating.

## Implemented in the inspected feature head

| Change from older context | Evidence and owners |
| --- | --- |
| Persona and verified candidates; CP-SAT became the sole default | `3ec2eaf`, `bfeb368`, `fbabe9f`, `ff370b5`; `agent/persona.py`, `routing/planners/cp_sat.py`, `routing/sources/persona_candidates.py`, registry/selection |
| Short stage prompts and aggregate turn usage | `5ecb9f9`; `agent/prompt.py`, `agent.py`, `backend/tests/agent/token_benchmark.py` |
| Independent validated detail recording, timezone-aware dates, optional car and single completion tool | `c919494`, `28ccfa8`, `1e2fb29`; `agent/trip_profile.py`, `trip_dates.py`, `departure.py`, `tool_dispatcher.py` |
| Mandatory extraction on each ordinary turn, outage/validation recovery, exact car-model lookup | `74c55d9`, `91a4666`, `21855b9`, `7c5981e`, `e7a83ab`; `agent/extraction.py`, `agent.py`, `routers/car_api.py`; legacy parsing removed |
| Account-owner-only interactive algorithm selection and Node 24 declaration | `5a32c71`, `180b525`; `utils/auth.py`, `routing/selection.py`, `services/routingSettings.js`, `frontend/package.json` |
| Dated Google Hotels totals/links; retired provider removed | `456c22a`, `1c1714f`; `routing/sources/google_hotels.py`, `persona_candidates.py`, `docs/hotel-prices.md`; old provider model/config removed |
| NDJSON progress, one animated status line and live verified collection facts | `570fe28`, `8b53940`, `999a96a`, `648ff41`; `agent/progress.py`, `progress_stream.py`, chat stream helpers/components; the intermediate expandable card was superseded |
| Rural all-outside-radius hotel results allow bounded earlier-stop retries | `ec9ecb0`; Google hotel source and candidate/scheduler regression suites; malformed/upstream failures remain terminal |
| Complete canonical profile context and explicit ambiguous-location choices | `9d2d006`, `620df3c`; `utils/location_resolution.py`, `agent/location_confirmation.py`, pending profile, frontend buttons/reload; provider precision is not intent confidence |
| Persisted validated detail lists, narrow summary/collection requests and truthful direct-tool outcomes | `d2e77f9`, `6247a1e`; `agent/presentation.py`, `schemas.py`, `ChatMessage.jsx`, `useTripWorkflow.js`, JSON/NDJSON and PostgreSQL probes |
| Local runtime, readiness and persistence support | `9ac43d0`, `51bd9ee`, `2220fe1` plus CRUD changes; local CORS/Neon readiness, `make debug`, backend virtualenv paths, thread-safe shared pool and saved planned-route support |

Backend relative paths in the table are beneath `backend/app/`; frontend service
and component paths are beneath `frontend/src/`. Changes include practical
regression coverage and disposable database probe extensions. They do not prove
the draft feature has been deployed. Signed Cognito verification, container
templates and much local recovery tooling already existed in inspected main;
the old Kiro descriptions of unsigned auth/Render/path-filtered CI were stale
even before this feature diff.

## Integrated flexible hotel evenings

The `codex/flexible-hotel-evenings` implementation builds on shared feature head
`cd03486`, preserving the concurrent receipts, direct-reply guards and context
refresh. See [the scheduling contract, example and validation](../docs/flexible-hotel-evenings.md).
The other observed hotel-evenings worktree is separate overlapping work; its
changes and reported tests are not part of this integration.

`backend/app/models/scheduling_policy.py` owns preferred hotel arrival **18:00**,
normal latest arrival **20:00**, morning restart **09:00**, and explicit late
driving through at most **24:00**. It flows through profile/extraction/tools,
HTTP/remote payloads, CP-SAT scheduling, shared actual-leg timing, itinerary and
persistence. Preferred arrival is soft; actual rerouted hotel/destination arrivals
must meet the arrival-local hard deadline while retaining selected attractions.
`routing/travel_timing.py` shares the clock logic rather than introducing a
second independently maintained itinerary policy.

Arrival-local IANA/DST deadlines retain the preceding booking night at midnight
and restart that same following morning. Existing saved routes without a policy
keep their legacy timing. Late reception remains unverified and is labeled
**Confirm late check-in with the hotel**.

`routing/sources/evenings.py` provides at most two optional alternatives around
the selected hotel, separate from daytime stops and waypoints, within 2 km and
15 minutes each way. Discovery has an eight-second total budget. Existing Terra
weekly hours do not verify date-specific exceptions, so live suggestions are
unscheduled **Check opening hours** options. Dated verified interval fixtures
exercise scheduled suggestions. Failures or insufficient time do not invalidate
a successful route. No new service, reservation or deployment is introduced.

The integrated local checks pass: 538 backend tests at 85.07% coverage, pinned
Ruff checks, all required frontend checks, two rebuilt container smoke tests and
real disposable PostgreSQL persistence/recovery. See the feature validation
ledger for scope and retained recovery data. Live provider/model/Cognito trip
acceptance and late reception remain blocked; PR #26 stays draft. Each later
shared-head change still requires its own CI evidence.

## Verification and structural follow-ups

At inspected head `6247a1e`, GitHub Actions backend, frontend test/build, container
and disposable PostgreSQL checks and Vercel preview reported success. PR notes
record 480 backend tests/84.29% coverage and 162 frontend tests from that delivery;
this context refresh did not rerun those suites. Live full-trip acceptance remains
unverified and the PR stays draft. Later commits require their own CI evidence.

Concrete structural issue: scheduler, final route validation and itinerary owned
different clock logic. The integrated policy refactor provides this bounded
fix; avoid a second parallel scheduling abstraction. A separate documentation
follow-up can reconcile the long historical `docs/chat-agent-design.md` and
mixed algorithm documents with the current contracts. Keep historical rationale,
but link current examples to schemas to prevent renewed drift.
