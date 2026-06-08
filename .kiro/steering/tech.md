# Tech Stack

## Monorepo Layout
This repo contains two services: `backend/` (Python/FastAPI) and `frontend/` (React/Vite).

---

## Backend (`backend/`)

### Language & Runtime
- **Python 3.9**

### Framework
- **FastAPI 0.111.1** – async REST API framework
- **Uvicorn 0.30.1** – ASGI server
- **Starlette 0.37.2** – underlying ASGI toolkit (via FastAPI)

### Data Validation
- **Pydantic v2 (2.8.2)** – all request/response models and data validation use `BaseModel`. Use `model_validate()` (not the deprecated `parse_obj()`), and `model_dump()` (not `dict()`).

### Database
- **Neon (Postgres)** – Postgres-backed storage for chat sessions, route segments, and steps. Connection managed via `psycopg2-binary==2.9.9` using `DATABASE_URL` from `.env`.

### External APIs
| API | Purpose |
|---|---|
| Mapbox Directions | Route geometry and step-by-step nav |
| TripAdvisor Content API | Attraction search and details |
| Google Places API | Nearby city lookup |
| Google Hotels (scraping) | Hotel search with price range |
| Amadeus | Hotel search fallback |
| OpenCage | Reverse geocoding (coords → address) |

### Key Libraries
- `requests` – synchronous HTTP calls to external APIs
- `httpx` – async HTTP (available but requests is predominantly used)
- `geopy` / `geographiclib` – geodesic distance calculations and geocoding
- `python-dotenv` – loads `.env` for local development; `load_dotenv(override=True)` is used in routers
- `PyJWT` – decodes Cognito JWTs in `app/utils/auth.py`
- `pandas` / `numpy` – data utilities
- `lxml` – HTML parsing for web scraping
- `typer` / `rich` – CLI utilities pulled in as FastAPI CLI dependencies

### Testing
- **pytest 8.2.2** + **pytest-asyncio 0.23.8** + **pytest-cov 5.0.0**
- Tests live in `backend/tests/` and use `fastapi.testclient.TestClient`
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
- `TRIPADVISOR_API`
- `OPENCAGE_KEY`
- `AMADEUS_KEY`, `AMADEUS_SECRET`
- `CAR_DATA_API`

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
