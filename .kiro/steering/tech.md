# Tech Stack

## Monorepo Layout
This repo contains two services: `backend/` (Python/FastAPI) and `frontend/` (React/Vite).

---

## Backend (`backend/`)

### Language & Runtime
- **Python 3.12** (CI runs 3.12; Render pinned via `backend/runtime.txt`). Modern
  syntax like PEP 604 unions (`X | None`) is used throughout, including in
  Pydantic model fields — do not reintroduce `Optional[...]` for style.

### Framework
- **FastAPI 0.111.1** – async REST API framework
- **Uvicorn 0.30.1** – ASGI server
- **Starlette 0.37.2** – underlying ASGI toolkit (via FastAPI)

### Data Validation
- **Pydantic v2 (2.8.2)** – all request/response models and data validation use `BaseModel`. Use `model_validate()` (not the deprecated `parse_obj()`), and `model_dump()` (not `dict()`).

### Database
- **Neon (Postgres)** – Postgres-backed storage for chat sessions, route segments, and steps. Connection managed via `psycopg2-binary==2.9.9` using `DATABASE_URL` from `.env`. The chat agent's memory (`chat_memory` table) reuses the same connection pool via `app/crud/memory_crud.py` — it never opens a second pool.

### External APIs
| API | Purpose |
|---|---|
| Mapbox Directions | Route geometry and step-by-step nav |
| TripAdvisor Terra (Partner API) | Attraction search and details (replaced the deprecated Content API) |
| Google Places API | Nearby city lookup |
| Google Hotels (scraping) | Hotel search with price range |
| Amadeus | Hotel search fallback (disabled by default) |
| OpenCage | Reverse geocoding (coords → address) |
| Mentro gateway (self-hosted, SSE) | Chat agent LLM provider (`/api/chat/stream-full`) |
| Supabase Auth | Mints the service-account JWT the backend uses to call the Mentro gateway |

### TripAdvisor Terra (Partner API)
The old **Content API** (`api.content.tripadvisor.com`) is fully retired. Attraction sourcing (`app/routing/sources/attractions.py`) now uses **Terra**:
- **Base URL**: `https://terra.tripadvisor.com/api` (override via `TRIPADVISOR_BASE_URL`).
- **Auth**: header-based — `X-API-Key: <TRIPADVISOR_API>`. The `TRIPADVISOR_API` env var name is unchanged but now holds a **UUID**, not the old 32-char key. Auth moved off the `key` query param.
- **Endpoints**: `GET /locations/nearby` (returns the *full* Location inline, so no per-result details fanout) and `GET /locations/{id}`.
- **Radius cap**: Terra rejects a nearby radius over **5.0 miles** with a 400; requested radii are clamped (`TRIPADVISOR_MAX_RADIUS_MI`).
- **Category enum**: Terra uses `ATTRACTION`/`RESTAURANT`/`HOTEL`; callers still pass the old lowercase strings, mapped through `TRIPADVISOR_CATEGORY_MAP` in `app/routing/config.py`.
- **Rank**: Terra has no popularity-rank integer, so results come `sort=rating,desc` and `find_stop` derives `rank` from result position (1 = best), preserving the "lower is better" objective semantics.
- **Models**: `app/models/routing_models/trip_advisor_models.py` was rewritten as `Terra_*` Pydantic models, all `extra="allow"` to tolerate the rich payload.
- An MCP server (`.kiro/settings/mcp.json`, key `tripadvisor-content`) points at the Terra docs endpoint `https://docs.terra.tripadvisor.com/mcp`.

### Chat Agent Layer
- The conversational agent lives in **`app/agent/`** and is exposed by `app/routers/agent_api.py` (`POST /agent/chat`). Like the routing layer, it is an **injected-dependency loop** (`run_turn` takes a provider chain, a `MemoryStore`, and a `ToolDispatcher`), so the whole thing is unit-testable with fakes — no network, no DB.
- **LLM provider**: a self-hosted **Mentro gateway** (SSE). The backend POSTs to `{MENTRO_GATEWAY_URL}/api/chat/stream-full` server-to-server, authenticating with a Supabase JWT minted from a service account (`SupabaseServiceAuth`). The gateway has **no native function-calling** — tool use is driven by a TEXT protocol: the model emits fenced ` ```tool ` JSON blocks that `toolcall_parser` extracts, dispatches, and feeds back (capped at 5 iterations).
- **Tools** (`tool_dispatcher.py`, `AppToolDispatcher`) are thin adapters over the *existing* app capabilities (routing, itinerary, location, car, memory/trip-profile) — no reimplementation. When `ROUTING_REMOTE_URL` is set (local dev), routing tools proxy the IP-whitelisted external calls through the deployed backend via `routing_remote.py`; unset (on the deployed backend) they run locally.
- **Memory** (`app/crud/memory_crud.py`, `MemoryCrudStore`) persists three tiers in one `chat_memory` table keyed by `(user_id, chat_id, mem_type, mem_key)`: durable cross-chat `fact`s (sentinel `chat_id=''`), a rolling per-chat `summary`, and a per-chat `trip` profile. The verbatim `ChatLog` is owned by the frontend and only *read* here, never written.
- **Debugging**: set `AGENT_DEBUG=true` for a per-turn console trace; `main.py` attaches an INFO handler to the `app` logger (level via `LOG_LEVEL`) so it's visible under uvicorn.

### Key Libraries
- `requests` – synchronous HTTP calls to external APIs (Mapbox, TripAdvisor Terra, scraping)
- `httpx` – async/HTTP client; used by the chat agent for the Mentro gateway SSE stream and Supabase auth
- `PyJWT` – also used by the agent to decode the Cognito `partitionKey` into a `user_id`
- `geopy` / `geographiclib` – geodesic distance calculations and geocoding
- `python-dotenv` – loads `.env` for local development; `load_dotenv(override=True)` is used in routers
- `PyJWT` – decodes Cognito JWTs in `app/utils/auth.py`
- `pandas` / `numpy` – data utilities
- `lxml` – HTML parsing for web scraping
- `ortools` (9.10.4067) – Google OR-Tools; the knapsack solver backs the `ortools` route planner in `app/routing/planners/`
- `typer` / `rich` – CLI utilities pulled in as FastAPI CLI dependencies

### Routing Algorithm Layer
- Route planning lives in **`app/routing/`** as a **pluggable-algorithm** layer behind a single `RoutePlanner` interface. Two planners ship: `greedy` (original heuristic) and `ortools` (OR-Tools knapsack). Selection is per-request (`Route_Payload.algorithm`), via `ROUTING_ALGORITHM` env, or the `greedy` default.
- Planners share one scheduler and reach external APIs only through an injected `RoutingServices` bundle, so they differ only in *selection*.
- `python -m app.routing.benchmark` (or `GET /benchmark` with `BENCHMARK_ENABLED=true`) compares planners on cached inputs. See `docs/pluggable-routing-refactor.md` and `docs/routing-localhost-testing.md`.

> The chat agent added **no new third-party dependencies** — it reuses `httpx`, `pydantic`, `PyJWT`, `psycopg2-binary`, and `fastapi`, all already pinned in `requirements.txt`.

### Testing
- **pytest 8.2.2** + **pytest-asyncio 0.23.8** + **pytest-cov 5.0.0**
- Endpoint tests live in `backend/tests/` and use `fastapi.testclient.TestClient`
- Planner-level tests live in `backend/tests/routing/` and inject a fake `RoutingServices` (no network) — the template for testing any new algorithm
- Chat-agent tests live in `backend/tests/agent/` and inject a fake `MemoryStore` / `ToolDispatcher` and a stub provider (no network, no DB) — the same injected-dependency pattern as the routing tests
- Configuration in `backend/pytest.ini`
- CI runs via `pytest` (GitHub Actions) from the `backend/` directory

### Common Commands

```bash
# Run from backend/

# Run dev server with auto-reload
make run
# equivalent:
uvicorn app.main:app --reload --reload-dir app

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

### Environment Variables
All secrets are loaded from `.env` (never committed). Required keys:

**Backend:**
- `DATABASE_URL`
- `MAPBOX_API`
- `TRIPADVISOR_API` – now a Terra Partner API **UUID** (sent as the `X-API-Key` header)
- `OPENCAGE_KEY`
- `AMADEUS_KEY`, `AMADEUS_SECRET`
- `CAR_DATA_API`

Chat agent (leave the Supabase service creds blank to run without the agent — the provider reports "not configured" and `/agent/chat` returns 503):
- `MENTRO_GATEWAY_URL` – Mentro SSE gateway base URL (defaults to the fly.dev instance)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY` – Supabase project the gateway auths against
- `MENTRO_SERVICE_EMAIL`, `MENTRO_SERVICE_PASSWORD` – service-account credentials for the password grant

Optional (all have safe defaults):
- `ROUTING_ALGORITHM` – default planner when the request omits `algorithm` (defaults to `greedy`)
- `AMADEUS_ENABLED` – enable the Amadeus hotel fallback (`false` by default)
- `BENCHMARK_ENABLED` – expose the `/benchmark` debug endpoint (`false` by default)
- `TRIPADVISOR_BASE_URL` – override the Terra base URL (defaults to `https://terra.tripadvisor.com/api`)
- `ROUTING_REMOTE_URL` – local dev only; proxy the agent's IP-whitelisted routing calls through the deployed backend. Leave **blank** on the deployed backend
- `AGENT_DEBUG` – per-turn agent console trace (`false` by default)
- `LOG_LEVEL` – level for the `app.*` logger namespace (defaults to `INFO`)

> The `.env` lives at the **repo root**. `app/core/config.py` and `app/routing/config.py` both load it via `parents[3]`; the routing layer centralizes its tokens in `app/routing/config.py`, and the chat-agent settings live on the `Settings` class in `app/core/config.py`.

**Frontend (Vite):**
- `VITE_BACKEND_SERVER` – base URL of the backend API
- `VITE_CLIENT_ID` – Cognito app client ID
- `VITE_USERPOOL_ID` – Cognito user pool ID
- `VITE_MAPBOX_TOKEN` – Mapbox public access token

> Note: `GOOGLE_PLACES_API` is no longer listed in `.env.example` — it may be embedded in the scraping logic or removed.

---

## Frontend (`frontend/`)

### Language & Runtime
- **Node.js** (latest LTS)

### Framework
- **React 18** + **Vite 5** – component-based UI with fast HMR dev server

### Key Libraries
- `react-router-dom` – client-side routing
- `axios` – HTTP client for backend API calls
- `@aws-sdk/client-cognito-identity-provider` – Cognito auth
- `mapbox-gl` – interactive map rendering
- `@mui/material` + `@mui/icons-material` – Material UI components and icons
- `@emotion/react` + `@emotion/styled` – CSS-in-JS styling engine (MUI peer deps)
- `@fontsource/roboto` – self-hosted Roboto font (MUI default)
- `bootstrap` – utility CSS
- `ldrs` – loading animation components
- `@react-login-page/page11` – pre-built login page layout
- `prop-types` – runtime prop type checking for React components

### Testing
- **Vitest 2.1.9** + **@testing-library/react 16.2.0** + **@testing-library/user-event 14.5.2**
- Tests live in `frontend/src/tests/`; config uses `jsdom` as the environment
- Run with `npm run test` (single pass) or `npm run test:watch`; coverage via `npm run test:coverage`

### Dev Dependencies
- `prettier` + `eslint-config-prettier` + `eslint-plugin-prettier` – code formatting; enforced via `npm run format` and `npm run format:check`
- `eslint` + `eslint-plugin-react` + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh` – linting
- `@vitejs/plugin-react` – Vite React plugin (Babel fast-refresh)
- `vitest` + `@vitest/coverage-v8` + `jsdom` + `@testing-library/react` + `@testing-library/user-event` + `@testing-library/jest-dom` – unit/component test stack

### Chat Workflow Architecture
The trip-planning flow is implemented as a **React state machine** in `useTripWorkflow.js`. Steps advance via `submit(action, payload)` — no polling loops, no class mutations. Each step change triggers a `useEffect` that does one unit of async work. See `structure.md` for the full step list and conventions.

Free-text chat is sent to the backend agent via `agentChat.js` (`sendAgentMessage` → `POST {VITE_BACKEND_SERVER}agent/chat`). The agent conversation is keyed by a **globally-unique UUID** (`agentChatId`), not the reused integer chat id, so per-chat agent memory can never collide across chats — `ChatPage` maps each integer chat id to a stable UUID and sends that as the backend `chatId`. Agent responses carry `actions` the UI applies (e.g. writing a new route/itinerary into `ChatData`).

### Common Commands

```bash
# Run from frontend/

npm install        # Install dependencies
npm run dev        # Start dev server (Vite HMR)
npm run build      # Production build
npm run lint       # ESLint
npm run format     # Prettier auto-format
npm run format:check  # Prettier check (CI-safe, no writes)
npm run test       # Vitest (single pass)
npm run test:watch # Vitest watch mode
npm run test:coverage  # Vitest with v8 coverage report
```

---

## CI/CD
- **GitHub Actions** – path-filtered workflows in `.github/workflows/`:
  - `backend-ci.yml` – triggers on `backend/**` changes; runs `pytest`
  - `frontend-ci.yml` – triggers on `frontend/**` changes; runs `npm run build`
- **Render** – backend web service deployed from `https://github.com/elischiffler/MyRoadtrip`
- **Vercel** – frontend deployed from `https://github.com/elischiffler/MyRoadtrip`
