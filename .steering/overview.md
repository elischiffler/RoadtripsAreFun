# RoadtripsAreFun context

RoadtripsAreFun is a React/Vite frontend and Python/FastAPI backend for authenticated
road trip planning, maps, itineraries, saved chats and conversational preferences.
The repository remote is `https://github.com/elischiffler/RoadtripsAreFun.git`.
Manifests, schemas, source and `AGENTS.md` take precedence over these notes.

This refresh inspected shared feature commit `6247a1e` against main `92ac3af` on
October 3, 2026 (America/Los_Angeles). The feature implementation is in draft
[PR #26](https://github.com/elischiffler/RoadtripsAreFun/pull/26); it is not merged
main or evidence of a production release. See [current work](current-work.md) for
the changes since the older guidance and implementation still in progress.

## Read next

| Context | Authoritative entry points |
| --- | --- |
| [Architecture](architecture.md) | `backend/app/main.py`, `frontend/src/Router.jsx` |
| [Development](development.md) | `frontend/package.json`, `backend/requirements.txt`, `.github/workflows/` |
| [Operations](operations.md) | `docs/container-runbook.md`, `docs/aws-api-readiness.md` |
| [Current work](current-work.md) | Git/PR state and the source map below; refresh before integration |

## Current capabilities and contracts

- `backend/app/routing/registry.py` registers only `cp_sat`; legacy greedy and
  knapsack implementations remain source references. Account persona weights
  inform provider-verified candidate utility; the backend owns selection,
  scheduling, validation and budget warnings.
- Every ordinary chat turn extracts supplied details before replying.
  `backend/app/agent/trip_profile.py` owns saved validated trip state;
  `record_trip_details` and `complete_trip` in `tool_dispatcher.py` collect and
  complete it. An explicit skipped car is valid; an unanswered choice blocks
  completion. Relative dates resolve in the starting location's IANA timezone.
- New endpoints receive a suggested address and require explicit owner/chat-scoped selection;
  pending endpoints block agent route and itinerary tools. See
  `docs/agent-location-confirmations.md`.
- The chat shows deterministic saved-detail lists and at most two missing-detail
  questions, plus one transient animated process line. See
  `docs/agent-trip-detail-lists.md` and `docs/agent-progress.md`.
- CP-SAT hotel prices are verified dated Google Hotels one-night totals for two
  adults in USD, with taxes/fees and comparison links. Hotel budget is a nightly
  target; usable over-budget hotels produce warnings. See `docs/hotel-prices.md`.
- [Flexible hotel evenings](../docs/flexible-hotel-evenings.md) adds shared local
  arrival deadlines and optional nearby suggestions; see the current-work handoff
  for the integration and remaining live acceptance gates.
- The frontend saves chats, route/itinerary actions, presentation and stable agent
  conversation IDs. PostgreSQL stores owner-scoped chat data and agent memory.
  Current schemas and ownership are described in [architecture](architecture.md).

## Documentation boundaries

`.steering/` is the current implementation map. `.kiro/steering/` contains
compatibility pointers to it. `docs/route-finding.md` mixes current CP-SAT notes
with explicitly historical greedy sections; `docs/pluggable-routing-refactor.md`
and `docs/algorithm-analysis.md` retain earlier designs. `docs/chat-agent-design.md`
also contains older contracts/plans: inspect the current schemas before using its
examples. Operational validation files contain dated evidence, not live status.
Avoid treating old planner defaults, unsigned JWT descriptions or Render targets
as current implementation facts.
