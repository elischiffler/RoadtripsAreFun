# RoadtripsAreFun

Local Docker preview: [runbook](docs/container-runbook.md) and
[validation/blockers](docs/container-validation.md). Its disposable PostgreSQL
checks are separate from the production AWS API, which uses external Neon.
The local preview does not establish production Auth or provider acceptance.

A road trip planning application. This monorepo contains two services:

| Service | Stack | Deployed at |
|---|---|---|
| [`backend/`](./backend) | Python 3.12 / FastAPI / Neon Postgres | [api.roadtrips.elischiffler.dev](https://api.roadtrips.elischiffler.dev/health) (AWS EC2) |
| [`frontend/`](./frontend) | React 18 / Vite / MUI | [roadtrips.elischiffler.dev](https://roadtrips.elischiffler.dev) (Vercel) |

The production frontend uses `https://api.roadtrips.elischiffler.dev/` as its
`VITE_BACKEND_SERVER`. The browser build embeds this value at build time. The
previous `rp-routing` Render web service was retired on 2026-09-28; do not use
its URL as a deployment or rollback target.

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

- [Current repository context](.steering/overview.md) — source ownership,
  repeatable checks, operational boundaries and the [active change map](.steering/current-work.md).

- [Trip detail lists](docs/agent-trip-detail-lists.md),
  [location confirmations](docs/agent-location-confirmations.md),
  [process status](docs/agent-progress.md) and [dated hotel prices](docs/hotel-prices.md)
  — current feature contracts and verification limits.

- [Owner routing settings](./docs/owner-routing-settings.md) — verified Cognito
  eligibility, session lifecycle, shared planner enforcement, and validation limits.

- [Route-Finding Algorithm](./docs/route-finding.md) — current CP-SAT notes and
  historical greedy design, with Mermaid diagrams. Use the
  [architecture map](.steering/architecture.md) for current planner ownership.

---

## Local Setup

### Prerequisites
- Python 3.12 on POSIX/WSL, or Docker for the pinned backend
- Node.js 24
- PostgreSQL for native persistence; use the disposable local test stack for fixtures

See [development context](.steering/development.md) for environment names and
platform limitations. The root Makefile uses POSIX shell syntax; the pinned
backend includes `uvloop`, which is not a native Windows dependency.

### 1. Clone the repo

```bash
git clone https://github.com/elischiffler/RoadtripsAreFun.git
cd RoadtripsAreFun
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
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt 'ruff==0.16.7'
```

### 4. Frontend

```bash
cd frontend
npm ci
```

On Windows PowerShell, use Python 3.12 and Node 24, then run from the root:

```powershell
py -3.12 -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt ruff==0.16.7
npm ci --prefix frontend
make run
```

Install GNU Make if `make` is unavailable (for example, `winget install --id
GnuWin32.Make --exact`). Add its `bin` folder to PATH and reopen PowerShell.
You can also start both services with `node scripts/dev.mjs`.

From the repo root (Windows, macOS, Linux, or WSL):

```bash
make run
```

This starts the backend at `http://localhost:8000` and the frontend at `http://localhost:5173` concurrently. Ctrl+C stops both.

To see the agent's per-turn tool arguments and trip-profile changes in the backend terminal, stop `make run` and start `make debug` from the repo root. Debug logging includes trip details, so use it only while troubleshooting.

Or run them individually:

```bash
make run-backend
make run-frontend
```

---

## Database Schema

The following is the checked-in local schema reference used by disposable tests.
Production schema and migration history remain unverified; do not apply this DDL
to a hosted database to satisfy local test gates. The disposable test's exact DDL
is [tests/postgres/schema.sql](tests/postgres/schema.sql).

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

GitHub Actions runs on every PR and main push, without service path filters:

- [Backend](.github/workflows/backend-ci.yml): Ruff format/lint and pytest coverage >=63%.
- [Frontend](.github/workflows/frontend-ci.yml): Node 24, npm ci, format/lint,
  coverage tests and build.
- [Containers](.github/workflows/container-ci.yml): diagnostic preview smoke and
  isolated backend tests.
- [Disposable PostgreSQL](.github/workflows/disposable-postgres-ci.yml): CRUD,
  ownership, recreation, loss recovery and backup/restore.

Repository check enforcement was not verified by this context refresh. No
automatic production Docker deployment is configured in these workflows.

---

## Running Tests

Unit tests use controlled provider/database responses. Separate container,
disposable real PostgreSQL and signed local journey tests have their own
prerequisites. They do not establish actual Cognito or full live provider acceptance.
Required format/lint/coverage/build commands are in [AGENTS.md](AGENTS.md) and
the [development map](.steering/development.md).

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
