# rp-routing

Backend routing microservice for **JourneyGenie** — a road trip planning application. Generates optimized multi-stop driving routes, finds attractions and hotels along the way, and persists user chat sessions.

Built with **FastAPI** + **Python 3.9**, backed by **Neon Postgres**.

---

## Prerequisites

- Python 3.9
- [Neon](https://neon.tech) account with a project set up

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd rp-routing
python3.9 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

The `.env` file is gitignored and should never be committed. Required keys:

- `DATABASE_URL` — get from [console.neon.tech](https://console.neon.tech) → your project → Connection string
- `MAPBOX_API` — [Mapbox](https://mapbox.com) access token
- `TRIPADVISOR_API` — [TripAdvisor Content API](https://tripadvisor-content-api.readme.io) key
- `GOOGLE_PLACES_API` — [Google Places API](https://developers.google.com/maps/documentation/places/web-service) key
- `OPENCAGE_KEY` — [OpenCage](https://opencagedata.com) geocoding key
- `AMADEUS_KEY` / `AMADEUS_SECRET` — [Amadeus](https://developers.amadeus.com) API credentials (hotel search fallback)

### 4. Set up the database schema

Run this once against your Neon database using `psql` or the Neon SQL editor:

```sql
CREATE TABLE IF NOT EXISTS chats (
  user_id    TEXT NOT NULL,
  chat_id    TEXT NOT NULL,
  chat_data  JSONB,
  chat_log   JSONB,
  PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS route_segments (
  user_id    TEXT NOT NULL,
  chat_id    TEXT NOT NULL,
  route_id   TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  coords     JSONB,
  PRIMARY KEY (route_id, segment_id)
);

CREATE TABLE IF NOT EXISTS steps (
  user_id     TEXT NOT NULL,
  chat_id     TEXT NOT NULL,
  leg_id      TEXT NOT NULL,
  step_id     INTEGER NOT NULL,
  coordinates JSONB,
  PRIMARY KEY (leg_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_route_segments_route_id ON route_segments(route_id);
CREATE INDEX IF NOT EXISTS idx_steps_leg_id ON steps(leg_id);
```

---

## Running the Server

```bash
make run
```

This starts the dev server at `http://localhost:8000` with hot-reload enabled.

Equivalent to:

```bash
uvicorn app.main:app --reload --reload-dir app
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| POST | `/get-initial-route` | Generate an initial driving route |
| POST | `/generate-final-route` | Generate final route with stops |
| GET | `/location` | Resolve coordinates to address |
| POST | `/itinerary` | Build day-by-day itinerary from a route |
| GET | `/car` | Get car data for trip planning |
| GET | `/chats` | Get all chats for a user |
| POST | `/chats/create` | Create a new chat session |
| PUT | `/chats/update` | Update a chat session |
| DELETE | `/chats/delete` | Delete a chat session |

Interactive docs available at `http://localhost:8000/docs` when the server is running.

---

## Running Tests

```bash
pytest
```

Or as CI does:

```bash
python -m unittest discover tests
```

---

## Project Structure

```
rp-routing/
├── app/
│   ├── main.py               # FastAPI entry point; registers routers and CORS
│   ├── core/
│   │   └── config.py         # Settings; loads DATABASE_URL from .env
│   ├── routers/              # One file per domain
│   │   ├── routing_api.py
│   │   ├── location_api.py
│   │   ├── itinerary_api.py
│   │   ├── car_api.py
│   │   └── chat_api.py
│   ├── models/               # Pydantic response/domain models
│   ├── schemas/              # Pydantic request body schemas
│   ├── crud/
│   │   └── chat_crud.py      # All database operations (Neon/Postgres)
│   └── utils/
│       ├── auth.py           # JWT decode → user_id extraction
│       ├── crud_helpers.py   # Route segmentation helper
│       └── geolocation_helpers.py
├── tests/
├── .env                      # Local secrets (never commit)
├── requirements.txt
├── Makefile
└── .travis.yml               # Travis CI — runs tests on pull requests
```

---

## CI/CD

**Travis CI** runs tests automatically on every pull request (see `.travis.yml`). Builds are skipped on direct pushes to main.

## Deployment

Deployed to **[Render](https://render.com)** as a web service.

### Render setup

1. Create a new **Web Service** in Render and connect your GitHub repo
2. Configure the service:
   - **Runtime**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add all keys from `.env.example` as **Environment Variables** in the Render dashboard
4. Deploy — Render will build and start the service automatically on every push to your main branch

Authentication uses **AWS Cognito** JWT tokens — the `sub` claim is extracted as the `user_id` for all database operations.
