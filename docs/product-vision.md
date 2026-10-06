# Product vision and Tuesday demonstration

Status: implemented in the senior-demo task branch, October 4, 2026 (America/Los_Angeles).
Presentation target: Tuesday, October 6. Source baseline: feature `53fd0bf`,
not a claim about deployed production. See [current work](../.steering/current-work.md).

## Product result

RoadtripsAreFun turns a traveler's validated trip profile into a personalized,
drivable road trip. A trip profile says what the traveler wants and what the
trip requires. A location profile describes a candidate place using the same
interest dimensions plus its provider identity and provenance. The backend
crossmatches the profiles, passes the resulting utility into CP-SAT attraction
selection, then schedules visits/hotels and verifies the resulting drive.

The chat is one way to collect inputs. It is not the routing algorithm. A
separate owner-only **Algorithm Lab** at `/algorithm` runs
the same planning pipeline from editable presets without a chat conversation.
The owner is the existing server-verified account policy in
`backend/app/routing/selection.py`. Do not create a browser email allowlist.

## Baseline and implemented milestone

| Capability | Feature baseline at 53fd0bf | Implemented task milestone |
| --- | --- | --- |
| Trip profile | Saved validated endpoints, date/time, stops, travelers/rooms, budget, car choice, interests and scheduling policy | Reuse the contract in an editable preset form; show effective values and sources |
| Trip personality | Account baseline plus partial trip override, normalized over 14 canonical interests | Show raw override, effective normalized weights and the default source |
| Location profile | Provider-verified identity/coordinates plus AI attribute ratings in candidate dictionaries | Explicit typed internal profile with provenance and inspectable score contributions |
| Crossmatch | Backend weighted sum already supplies CP-SAT utility | Explain each term and show how changing preferences changes selection |
| Solver | Attraction subset, stop cap, one per route query slot, utility threshold | Readable model-building code and structured explanation from the actual solve |
| Scheduling | Separate visit/hotel scheduler and final Mapbox timing check | Display stage outcomes and truthful partial/error states |
| Demonstration | Chat and ordinary map/itinerary pages | Owner-only presets, map, candidate table, solve summary and replay fallback |

Location ratings describe the place independently of the active trip. Do not
inflate a place's ratings to match a user. Providers verify place identity and
coordinates, not subjective interest ratings. Label AI estimates accordingly.
Changing weights against a frozen candidate set should only recompute backend
scores and rerun the same selection model. A new live discovery may produce a
different candidate set; label that as a different experiment.

## Tuesday scope and priorities

1. **Must:** a reliable owner-only direct run with complete validated presets,
   actual route/map output, and visible provider errors. Normal chat still works.
2. **Must:** explainable trip/location crossmatch, actual CP-SAT status and
   objective, candidate exclusions, and clear selection-versus-scheduling stages.
3. **Must:** a rehearsed live run and a conspicuously labeled recorded/fixture
   replay that runs the same solver when providers or classroom internet fail.
4. **Must:** source walkthrough and a short presentation script. The presenter
   can trace each input to its origin and each displayed result to code.
5. **After Tuesday:** consider joint time/budget/selection optimization only
   after defining reliable travel-time and duration inputs. It is not part of
   the current CP-SAT model and must not be advertised as implemented.

Keep CP-SAT the sole registered production planner and retain the switcher seam.
Avoid new services, a schema migration, bookings, or a deployment migration for
the demonstration. Preset runs do not silently update account preferences or
overwrite saved chats. If saving is added, make it an explicit existing
owner-scoped operation rather than a prerequisite for running the demo.

## Honest claims

Say: “We maximize modeled preference match among a bounded set of verified
candidate places, then check the resulting itinerary against scheduling rules.”
Do not say: “We find the globally best road trip,” “CP-SAT optimizes hotel cost
and driving time,” or “the AI ratings are verified facts.” An optimal subset
does not prove an optimal full trip. A feasible result does not prove optimality.
Replay demonstrates computation on saved inputs; it does not prove live provider
availability, current prices, or today's authentication state.

The current model is simple enough to solve by taking the best candidate in each
slot and then the best slots. CP-SAT makes the model explicit and provides a
foundation for richer constraints; do not claim this instance needs a complex
solver to be tractable. See the [code walkthrough](cp-sat-explained.md).

## Delivery and acceptance

The [public/MacBook runbook](senior-demo-runbook.md) owns release and rehearsal.
The [demo implementation contract](senior-demo-plan.md) owns scope, interfaces,
presets and gates. The [explanation](cp-sat-explained.md) owns current mathematics
and teaching. Preserve historical algorithm research as historical, linking here
instead of maintaining competing product visions.

Use isolated task branches based on the latest shared CP-SAT feature head,
coherent commits and reviewable PRs. Integrate related work into existing draft
PR #26 through an explicit coordinator handoff. Never merge or push main.
Required CI plus live owner/non-owner, browser, provider and persistence checks
have distinct evidence scopes. No cloud spending or production deployment is
authorized by this plan.

## Persistent Algorithm Lab experiments

Algorithm Lab now records live and selection-replay runs in a separate, owner-scoped
PostgreSQL table. Ordinary chat runs are excluded. A benchmark modal queues the
six route categories sequentially, with optional repeats and persistent input/metric
history. See [run history and migration](algorithm-run-history.md) for scoring, feasibility,
comparison rules and operational boundaries. Apply the additive table migration
to the approved target before the backend release; local validation is not evidence
of a public database migration. Replay still needs the backend and this database.
