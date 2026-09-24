# RoadtripsAreFun

Local Docker preview: [runbook](docs/container-runbook.md) and
[validation/blockers](docs/container-validation.md). The container work does not
change production hosting. Disposable PostgreSQL CRUD/recovery checks pass; the
full trip journey, live-schema compatibility and isolated Auth/provider checks
remain open. The PR remains draft.

A road trip planning application. This monorepo contains two services:

| Service | Stack | Deployed at |
|---|---|---|
| [`backend/`](./backend) | Python 3.12 / FastAPI / Neon Postgres | [Render](https://dashboard.render.com/web/srv-cqvu44jv2p9s739hhb60) |
| [`frontend/`](./frontend) | React 18 / Vite / MUI | [Vercel](https://roadtripsarefun.vercel.app) |

---

## Frontend UI

The frontend uses an earthy design system (cream, sand, bark, amber) with Playfair Display headings and Inter body text.

### Key pages

| Route | Description |
|---|---|
| `/` | Landing page — app name, CTA, three interactive feature chips |
| `/chat` | Main chat interface for planning a trip |
| `/map` | Interactive Mapbox route view |
| `/itinerary` | Day-by-day trip itinerary |
| `/login` | Auth — AWS Cognito sign in |
| `/signup` | Auth — new account |

### Global header

A fixed `GlobalHeader` component renders on every page (hidden on `/login` and `/signup`). It contains:
- **Left** — custom SVG logo: a car driving over mountains. Hover plays a driving animation (scrolling road + spinning wheels). Clicking navigates home.
- **Right** — amber login button when logged out; amber avatar circle when logged in. Clicking the avatar opens a dropdown with a sign-out option.

### Feature chips (landing page)

Three interactive pills on the landing page each have a unique hover animation:
- **Route generation** — pill transforms into a spinning wagon wheel with the label text on the rim
- **Hotel finder** — pill becomes a hotel building with windows that randomly flicker on/off
- **Itinerary builder** — pill becomes an analog clock with hands that sweep forward and back continuously

### Design tokens

All colours are defined in `frontend/src/components/Theme.jsx` and exposed as CSS custom properties via `frontend/src/index.css`. Amber (`#C4873A`) is the sole accent colour throughout the UI.

---

## Documentation

Technical docs live in [`docs/`](./docs):

- [Route-Finding Algorithm](./docs/route-finding.md) — the two-phase route
  generation flow, day-by-day scheduling, attraction and hotel discovery, and
  data models, with Mermaid diagrams.

---

## Local Setup

### Prerequisites
- Python 3.9
- Node.js (LTS)
- A [Neon](https://neon.tech) Postgres database

### 1. Clone the repo

```bash
git clone https://github.com/elischiffler/MyRoadtrip.git
cd MyRoadtrip
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Fill in your values
```

See `.env.example` for all required keys. The `.env` at the repo root is shared by both services.

### 3. Backend

```bash
cd backend
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Frontend

```bash
cd frontend
npm install
```

From the repo root:

```bash
make run
```

This starts the backend at `http://localhost:8000` and the frontend at `http://localhost:5173` concurrently. Ctrl+C stops both.

Or run them individually:

```bash
make run-backend
make run-frontend
```

---

## Database Schema

Run once against your Neon database (via `psql` or the Neon SQL editor):

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

## CI

GitHub Actions runs on every PR, path-filtered per service:

- `backend/**` changes → runs `pytest` ([workflow](.github/workflows/backend-ci.yml))
- `frontend/**` changes → runs `npm run build` ([workflow](.github/workflows/frontend-ci.yml))

---

## Running Tests

All tests use mocks — no real API keys or database connection needed.

**From the repo root:**

```bash
make test
```

**From `backend/` directly:**

```bash
cd backend
pytest
```

Tests live in `backend/tests/`. Configuration is in `backend/pytest.ini`.
