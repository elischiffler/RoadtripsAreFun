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
- `boto3` – AWS SDK (available for future use)
- `PyJWT` – decodes Cognito JWTs in `app/utils/auth.py`
- `pandas` / `numpy` – data utilities
- `lxml` – HTML parsing for web scraping

### Testing
- **pytest 8.2.2** + **pytest-asyncio 0.23.8**
- Tests live in `backend/tests/` and use `fastapi.testclient.TestClient`
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
- `DATABASE_URL`
- `MAPBOX_API`
- `TRIPADVISOR_API`
- `GOOGLE_PLACES_API`
- `OPENCAGE_KEY`
- `AMADEUS_KEY`, `AMADEUS_SECRET`

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
- `@mui/material` – Material UI component library
- `bootstrap` – utility CSS

### Common Commands

```bash
# Run from frontend/

npm install        # Install dependencies
npm run dev        # Start dev server (Vite HMR)
npm run build      # Production build
npm run lint       # ESLint
```

---

## CI/CD
- **GitHub Actions** – path-filtered workflows in `.github/workflows/`:
  - `backend-ci.yml` – triggers on `backend/**` changes; runs `pytest`
  - `frontend-ci.yml` – triggers on `frontend/**` changes; runs `npm run build`
- **AWS CodeBuild** → **AWS Elastic Beanstalk** – backend deployment, sourced from `https://github.com/elischiffler/MyRoadtrip`
