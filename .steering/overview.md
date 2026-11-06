# RoadtripsAreFun context

RoadtripsAreFun combines a React/Vite frontend and Python/FastAPI backend for
road trip planning, maps, itineraries, saved trips and shared AI preference extraction.
The remote is `https://github.com/elischiffler/RoadtripsAreFun.git`.
Source, manifests, schemas and `AGENTS.md` take precedence over these notes.

This refresh inspects main `e9129a7551ef8c07405a9bf7552f6303765365af`
on October 16, 2026 (UTC), using an isolated task checkout. Studio and the EC2
deployment workflow are merged, along with the source-backed catalog, positive
match eligibility and source-calendar filtering. This source inspection does not
establish the currently running revision or active catalog generation. See
[current work](current-work.md) and [operations](operations.md) for dated evidence
and pending work.

## Read next

| Context                                           | Authoritative entry points                                                            |
| ------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [Architecture](architecture.md)                   | `backend/app/main.py`, `frontend/src/Router.jsx`                                      |
| [Development](development.md)                     | `frontend/package.json`, `backend/requirements.txt`, `Makefile`, `.github/workflows/` |
| [Operations](operations.md)                       | `docs/ec2-deployment.md`, `compose.neon.yaml`, `.github/workflows/deploy-ec2.yml`     |
| [Current work](current-work.md)                   | Merged release, source ownership and remaining acceptance boundaries                  |
| [Product vision](../docs/product-vision.md)       | Trip/location matching and demonstration priorities                                   |
| [Trip Planning Studio](../docs/studio-access.md)  | Visitor sessions, live presets, streamed runs and isolated history                    |
| [Adaptive planning](../docs/adaptive-planning.md) | Discovery budgets, road checks, concurrency and provider retries                      |
| [CP-SAT walkthrough](../docs/cp-sat-explained.md) | Actual inputs, model, objective, diagnostics and limits                               |

## Current contracts

- `backend/app/routing/registry.py` registers only `cp_sat`. The selection model
  chooses eligible attractions within a ten-percentage-point average-match bound,
  minimizing spacing and measured solo detours. Scheduling, hotels and final
  Mapbox timing validation remain separate responsibilities.
- The backend owns validated trip details, confirmed endpoints, departure dates,
  explicit room occupancy and optional car choice through planning APIs. Shared
  preference extraction and AI providers remain in `backend/app/agent/`. See
  [chat retirement](../docs/journeygenie-removal.md) for the removed UI and API.
- `/studio` is a header-free visitor page; `/algorithm` redirects to it. Signed
  Studio sessions are independent of Cognito accounts. New runs use live providers;
  replay requests are rejected. Existing historical replay records retain their
  original meaning.
- Cognito continues to protect saved account trips, maps, itineraries and settings.
  Frontend renewal and narrowly bounded authentication retries are owned by
  `frontend/src/services/session.js` and `protectedRequest.js`.
- The production API uses EC2 with external Neon. Successful CI on the exact
  current main commit gates automatic API deployment; the frontend remains a
  separate Vercel deployment boundary.

## Documentation boundaries

`.steering/` is the current implementation index; `.kiro/steering/` contains
compatibility pointers. Release plans, README descriptions and validation reports
may preserve earlier owner-only Lab, greedy planner or pre-deployment snapshots.
Use current router/source contracts and [operations](operations.md) when those
dated descriptions disagree. Historical local/fixture results do not establish
current Cognito, complete provider-trip, persistence or recovery acceptance.
