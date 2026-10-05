# Algorithm Lab implementation contract

Status: **IMPLEMENTED ON TASK BRANCH**, public release/live acceptance pending. Baseline
`53fd0bf`, October 4, 2026. Target: Tuesday, October 6. Product intent lives in
[product-vision.md](product-vision.md); current code is explained in
[cp-sat-explained.md](cp-sat-explained.md).

The header-free page uses short subtitles, hover/focus/click help for definitions,
and disclosures for formulas/provenance. The in-page link returns to chat.
API routes stay `/algorithm-lab/presets` and `/algorithm-lab/run`.
The trip-interest editor uses a pie chart: drag or click a topic to add a slice,
then drag its edge, use arrow keys, or enter a percentage to resize. A drop
overlay identifies the circle while carrying a topic. Allocations are capped at
100%; shrinking/removing a slice frees space without changing other topics.
Unused space is visible and is not a neutral interest: backend normalization
still scales positive weights to one. An empty mix disables Run.

Lab weights are explicit complete overrides. Replay uses synthetic selection-only
fixtures (`teaching-v1` / `empty-v1`), with null route/itinerary and no database or
provider calls. Live snapshots are not retained for replay. Car choice is
validated/displayed but this Lab does not estimate fuel. These are deliberate
milestone boundaries. See [public release/MacBook rehearsal](senior-demo-runbook.md).

## A single planning path

The owner-only `/algorithm` screen exposes three stages: **Trip inputs**,
**Candidate matches**, and **Route and explanation**. Reuse the existing theme,
map and itinerary rendering. Give the presenter an obvious Run button, editable
presets, a progress state, clear failure/retry, and comparison of two preference
profiles against the same candidate snapshot. Disable duplicate submissions.
Invalidate prior output after input changes; never show an old success as a new run.

The backend owns validation and computation. Factor a narrow shared orchestration
service only where necessary; reuse `plan_final_route`, `TripProfile` validators,
persona rules, occupancy rules, departure normalization and scheduling policy.
Keep pending-location confirmation for arbitrary typed locations. Reviewed
preset endpoints can be server-resolved and presented as explicit confirmed
selections without invoking the conversational extraction loop. Do not trust
browser-supplied coordinates merely because they came from a preset form.

Implemented API surface (`backend/app/routers/algorithm_lab.py` owns the schema):

- Owner-authorized preset catalog with schema version, labels and complete
  editable trip values; canonical interest keys/limits come from backend owners.
- Owner-authorized run operation taking preset/validated overrides and an
  explicit live or replay mode; no user ID, eligibility flag, utility or claimed
  verification supplied by the browser is authoritative.
- Response envelope with `schema_version`, mode, input snapshot, candidate
  snapshot identity, solver explanation, stage outcomes, and existing Route/
  itinerary models when those stages succeed. An empty eligible set is a
  **not run** solver result, not a fabricated OPTIMAL status.

Use both existing authenticated access-token checks and
`owner_routing_claims(subject, identity_token)` on every Lab data/run endpoint.
Missing owner evidence must fail closed with 401/403 as appropriate. A hidden
menu or `VITE_DEV_TOOLS` is not authorization. Existing non-owner algorithm
override behavior silently chooses the default; that is insufficient for this
owner-only endpoint. Preserve ordinary authenticated planning for everyone.
Do not broaden the existing owner selector accidentally. Honor account change,
logout, token expiry and stale-response invalidation in the UI.

## Input contract and presets

Use the parameters currently collected, rather than a second simplified form:

| Input | Owner and meaning |
| --- | --- |
| Start/destination | Confirmed provider-resolved labels, `[lat, lon]`, start IANA timezone; Mapbox geometry is `[lon, lat]` |
| Departure | Upcoming local date and time resolved to an offset-aware datetime; reject invalid/DST-ambiguous values |
| Attraction count | Chat profile currently validates 1–10; do not infer API bounds from unvalidated HTML controls |
| Travelers/rooms | Explicit total and 1–4 room allocations, each 1–6 guests with an adult and child ages 0–17; totals must match |
| Hotel budget | USD nightly target **per room**; disclose actual prices and over-target room quotes |
| Car | Explicit skipped or validated year/make/model; used for fuel estimates, not CP-SAT selection |
| Trip personality | All 14 effective weights; derive from account baseline plus trip override and normalize on backend |
| Schedule | Existing preferred hotel 18:00, hotel cutoff 20:00, restart 09:00, final arrival normally no later than 21:00; optional existing overrides |
| Evening interests | Existing optional food/culture/nightlife suggestions, separate from selected daytime stops |

Implemented editable scenarios; live provider availability are **not verified**:

| Preset | Parameters | Purpose |
| --- | --- | --- |
| Coastal nature | San Francisco to Monterey, 2 stops, 2 adults in 1 room, $180/room/night, 09:00 departure, car skipped, nature .6/history .3/food .1 | Small live route and obvious profile matching |
| Same corridor, culture | Same route/date/occupancy/budget, history/culture/food emphasis | Compare weights on the same candidate snapshot |
| Overnight road trip | San Francisco to Los Angeles, 3 stops, same occupancy/budget, 09:00 departure, balanced interests | Rehearse hotel/timing behavior; no guarantee an overnight is required until computed |

Preset dates must resolve at run time to a visible upcoming date in the origin
timezone (for example tomorrow), then be frozen in the run snapshot. Do not
hardcode the presentation date as a permanently valid departure. The backend
agent defines complete 14-key vectors with zero entries for unused interests;
partial overrides over a uniform baseline do not mean omitted keys become zero.
Keep preset definitions authoritative in one place and document validation dates.

## Explainability and readable code

The implementation introduces a typed internal location/candidate profile around the existing
`VerifiedPlace` and `AttributeRatings` contract, not a new database subsystem.
Include provider identity/coordinates, all canonical ratings, rating source,
verification provenance and available timestamps. Keep trip-specific match
utility/contributions separate from reusable place attributes. Unknown
timestamps remain unknown; never manufacture provider verification times.

`routing/cp_sat_selection.py` separates the model into named steps: prepare eligible candidates and
slots, build variables, add constraints, build objective, solve, decode and
explain. Preserve selected IDs/order, threshold, rounding, caps and scheduling
semantics in a behavior-preserving milestone. The actual integer coefficients
must feed both solver and explanation. Do not recalculate a different score in
React or expose the historical `score_trip()` benchmark metric as solver output.

Explanation should include effective weights and sources, candidate ratings and
weighted contributions, utility, threshold result, slot, selected state, modeled
objective coefficient, actual solve status, objective/best bound when available,
wall time and configured limit. Distinguish malformed/unverified/duplicate/
below-threshold candidates from eligible but unselected candidates. Only call
something an exclusion reason when directly supported by validation/constraints;
claims like “selected instead of X because of Y” need a proved comparison or
counterfactual solve. A slot grouping is geographic sampling, not a minimum
distance or proven drive-order guarantee. Rank-based tie terms do not guarantee
a mathematically unique subset for every equal-score input.

Return a bounded sanitized explanation; exclude credentials, hidden prompts,
unbounded provider payloads and account identifiers. Preserve ordinary response
compatibility and remote routing enforcement. Failed scheduling must not turn a
selection-only success into a “trip complete” UI.

## Replay and evidence

Replay uses a versioned, sanitized fixture or recorded provider snapshot with
its original source/date label. It runs the same candidate-scoring and solver
code. No network or fresh hotel verification is implied. Use an explicit fixture
clock/context for recorded dates rather than weakening upcoming-date validation
for live requests. If showing prerecorded geometry/itinerary, label it recorded;
do not imply it was rerouted live. Never silently substitute replay for a failed
live run. Rescoring the same snapshot is distinct from recollecting providers.

Minimum replay fixtures: two candidates in one slot, a below-threshold candidate,
more eligible slots than requested stops, no eligible attractions, and two
complete trip-weight vectors that visibly change the winner. Include a readable
small numeric example and reproducible expected selection.

## Work split and finish line

1. **Backend profiles/solver/Lab API:** freeze request/response examples first;
   own Python models, scoring/refactor, auth, presets, replay and backend tests.
2. **Frontend Algorithm Lab:** start after the backend contract handoff; own
   screen/service/header/router and frontend tests, consume backend values.
3. **Integration and rehearsal:** after both commits, own integration, complete
   required checks, browser/provider rehearsal, final docs and presentation notes.

Agents use disjoint worktrees and return branch, exact commit, owned files,
contract/schema, commands/results and blockers. No racing pushes to the shared
feature branch. The coordinator owns integration into PR #26; user owns merging.

Required checks remain those in [development](../.steering/development.md):
frontend install/format/lint/coverage/build; backend pinned install/Ruff/coverage;
running-container smoke; disposable PostgreSQL CRUD and recovery. Meaningful
regressions cover scoring provenance, normalization, brute-force optimality of
small selections, rounding/ties, deterministic frozen inputs, threshold and
count/slot exclusions, truthful statuses, replay/live separation, invalid
occupancy/dates, unauthorized requests, account changes and route failures.

Record PASS/FAIL/BLOCKED with exact commit, runtime and command. Add owner login
and non-owner denial, a complete live preset through map/itinerary, altered
preferences, failed provider/retry, reload behavior and ordinary chat regression.
If local-only demo is chosen, record that target; preview CI does not prove its
backend matches. Keep PR draft while material required acceptance is blocked.

Monday rehearsal: run all scenarios at least once, retain a sanitized replay,
record provider latency, and practice the explanation. Tuesday: sign in, show
trip profile, run, inspect one candidate score, show constraints/status, change
weights on the same snapshot, then show route and timing. Use the labeled replay
if necessary and state exactly what it demonstrates.
