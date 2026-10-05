# Current feature and senior demonstration work

## October 5 release consolidation

Active integration is now `codex/production-release`, targeting `main` in one
release PR. It contains the integrated feature/UI work and final live preset
fixes; every pre-cleanup local/remote branch tip is preserved in its ancestry.
See [release consolidation](../docs/release-consolidation.md) for the branch
audit, current validation and remaining production gates. The dated snapshots
below retain their original evidence scope; superseded PRs are closed during
cleanup. This integration does not merge main or deploy production.

Snapshot: October 4, 2026, America/Los_Angeles. Inspected and fetched shared
feature `53fd0bf9d03f31103b909818ee646fb19ce5b825` (`codex/cp-sat-solver`) against
main `92ac3af4155afc99704dc6072e6f25e57a4dc488`. The primary checkout was clean
and matched its remote. This refresh uses isolated `codex/senior-demo-plan`.

[PR #26](https://github.com/elischiffler/RoadtripsAreFun/pull/26) is open,
draft and unmerged. GitHub reported successful backend, frontend test/build,
container, disposable PostgreSQL and Vercel checks for `53fd0bf`. The new milestone passes the local suites recorded in
[demo validation](../docs/senior-demo-validation.md); live-trip acceptance remains
pending. Re-fetch before integration; concurrent branches may advance the feature.

## Implemented in this baseline

| Capability | Current owner / evidence |
| --- | --- |
| Sole registered `cp_sat` default, retained registry/switcher seam | `routing/registry.py`, `routing/selection.py`, `planners/cp_sat.py` |
| Account baseline, trip personality and provider-verified candidates | `agent/persona.py`, `routing/sources/persona_candidates.py`; ratings remain AI estimates |
| Mandatory extraction and independently validated detail recording | `agent/extraction.py`, `trip_profile.py`, `tool_dispatcher.py` |
| Confirmed locations, local departures, optional car and completion/retry | `agent/location_confirmation.py`, `trip_dates.py`, `departure.py`, completion tools |
| Saved detail lists, bounded questions and transient streaming progress | `agent/presentation.py`, `questions.py`, `progress.py`, `progress_stream.py`; frontend chat components |
| Owner-only algorithm override verified by Cognito ID/access subjects | `utils/auth.py`, `routing/selection.py`, `frontend/src/services/routingSettings.js` |
| Integrated local scheduling policy and optional hotel evenings | `models/scheduling_policy.py`, `routing/travel_timing.py`, `cp_sat_scheduler.py`, `sources/evenings.py` |
| Traveler total, explicit room occupancy and independent dated room quotes | `routing/occupancy.py`, `sources/google_hotels.py`, `docs/travelers-and-hotel-occupancy.md` |
| Chat creation before agent turns and bounded final-evening arrivals | `5f12124`; `docs/chat-creation-arrival-timing.md`; default final arrival through 21:00 |
| JSON-safe dated route persistence and failed-save tool-chain stop | `0eaa54a`, fixture follow-up `fab38ea`; `agent/tool_dispatcher.py` and tests |
| Current chat visual polish | `53fd0bf`; frontend chat icon/composer styles |

Backend paths are beneath `backend/app/` unless otherwise stated. Existing
feature docs retain dated validation reports; consult source for later behavior.
The prior October 3 snapshot at `6247a1e` is preserved in Git history.

Scheduling defaults are preferred hotel 18:00, latest hotel 20:00, morning 09:00,
and default destination deadline 21:00. Explicit late-driving/destination rules
and arrival-local IANA/DST handling refine those values. Hotels retain independent
room quotes and per-room budget warnings. Optional evenings remain distinct from
daytime attractions; unverified opening hours and hotel reception stay labeled.

## New direction: Tuesday, October 6

[Product vision](../docs/product-vision.md) is the single current product plan.
The [Algorithm Lab contract](../docs/senior-demo-plan.md) implements an owner-only
preset screen, explicit location profiles, backend score contributions, actual
solver diagnostics and labeled replay. **These additions are implemented on the senior-demo task branch; public
release/live-provider acceptance remains pending.** The [CP-SAT walkthrough](../docs/cp-sat-explained.md)
explains current inputs, integer objective, constraints, scheduling and outputs.

Delivery order: backend contract/profiles/solver diagnostics and authorized run
API, then frontend Lab, then integrated validation and rehearsal. Independent
frontend layout work may start after the response contract is frozen. Related
implementation returns exact commits to the coordinator for PR #26 integration;
do not let several agents push to its branch concurrently.

## Structural findings addressed by this milestone

- `cp_sat_selection.py` separates preparation, model construction and decoding;
  the exact objective and named constraints feed both solve and explanation.
- `profiles.py` derives rating fields from canonical persona keys and returns
  contribution arithmetic; `LocationProfile` separates provider facts/ratings
  from the trip-specific match.
- Benchmark comments distinguish historical value/cost/detour measurements from
  CP-SAT's actual match-surplus objective.
- Selection and scheduling use one query-count function.
- The direct Lab adapter reuses TripProfile and occupancy validation, preserving
  strict stop bounds, finite budget and complete weights.
- Frontend reuses the extracted `ItineraryDays` renderer and existing Map;
  `/algorithm` omits the header and uses accessible contextual help/disclosures.
  Trip interests use a capped percentage pie with pointer drag/drop, edge resizing,
  keyboard controls and precise numeric inputs; the backend still normalizes weights.

A joint time/budget/hotel optimization model is a separate later behavior-change
PR; the current grouped attraction selection is not that model.

## Remaining evidence

Live owner/non-owner Cognito, complete model/provider route and itinerary,
browser reload/persistence, and runtime parity remain unverified in this refresh.
No deployment, live account write, schema change or production setting was made.
Required repository checks and live demonstration gates remain separate. Keep
the feature draft until the applicable acceptance gates actually pass.

## Session expiry recovery

Frontend session renewal is owned by `services/session.js`; protected Axios and
NDJSON dispatch rebuild headers and legacy body tokens from one fresh session.
The Cognito SDK uses `GetTokensFromRefreshToken`, preserving rotation/device keys,
with coalesced renewal and one bounded verifier-rejection replay. Logout/account
changes invalidate late results. Same-account recovery keeps chat state and drafts;
server eligibility is rechecked with renewed identity tokens. The owner Algorithm
Lab uses the same protected transport. See [session renewal](../docs/session-refresh.md)
for the rejection audit, local/browser evidence and outstanding live Cognito gates.
No AWS settings, backend auth validation, schema or production deployment changes
are included. PR #26 remains draft pending its existing live acceptance requirements.

## Persistent Algorithm Lab experiments

Algorithm Lab now records live and selection-replay runs in a separate, owner-scoped
PostgreSQL table. Ordinary chat runs are excluded. A preset modal fills the complete form for individual live runs, with persistent
input/metric history and saved map/itinerary viewing. The benchmark batch modal
has been removed. See [run history and migration](../docs/algorithm-run-history.md) for scoring, feasibility,
comparison rules and operational boundaries. Apply the additive table migration
to the approved target before the backend release; local validation is not evidence
of a public database migration. Replay still needs the backend and this database.

## Live-only Algorithm Lab runs

The `/algorithm` form submits only live provider trips.
The run API accepts `mode: "live"` (also the default), rejects replay and fixture
snapshot fields, and always uses geocoding, live discovery, road routing and
itinerary construction. Hotel/evening providers run when the trip needs them.
The presets API no longer advertises synthetic candidate snapshots. Existing
replay history remains labeled for accurate historical measurements; offline
solver fixtures are retained only for unit verification.

The Trip presets button opens a native modal with all nine presets. Selecting a
card deep-copies every form field and closes the modal; running remains explicit.
The six benchmark profiles also vary departure times, party/room/child occupancy,
interests, vehicles and evening policy while retaining their route categories.
