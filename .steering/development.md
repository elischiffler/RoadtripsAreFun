# Development and verification

Use Python 3.12 and Node 24 (`AGENTS.md`, Dockerfiles and CI). Backend dependencies
are pinned in `backend/requirements.txt`; frontend uses `package-lock.json`.
Ruff 0.16.7 is pinned by backend CI and configured in `backend/ruff.toml`.

## Setup and local runtime

Copy root `.env.example` to ignored `.env` and supply the intended development
configuration. `backend/app/core/config.py`, `routing/config.py` and
`frontend/vite.config.js` load from the repository root; never copy runtime secrets
into images or `VITE_*` variables. Vite values are public and embedded at build
time. Configure browser/backend Cognito pool/client consistently; agent use also
needs the Mentro gateway service credentials. A routing proxy reaches a deployed
backend and is not an isolated provider fixture.

On POSIX/WSL, from the root:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt 'ruff==0.16.7'
cd frontend
npm ci
cd ..
make run
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

The root Makefile starts a Node launcher that selects the native virtualenv
interpreter. `make run` starts API8000 and Vite5173 in the same terminal; Ctrl+C
stops both process trees. A server failure shuts down the other server. Vite
fails if port 5173 is occupied instead of choosing a different port.
`make debug` enables per-turn trip/tool logging, which can contain trip data.
Use `make run-backend` and `make run-frontend` for separate processes.
The uvloop requirement is skipped on Windows; Uvicorn uses asyncio there.
Launcher regression checks: `node --test tests/dev-runner.test.mjs`.

The diagnostic Docker preview is documented in `docs/container-runbook.md`:
set `ROADTRIPS_REVISION` to `git rev-parse HEAD`, then
`docker compose up --build --detach --wait --wait-timeout 60` from root.
Web8082/API8002 are loopback-only. This guarded preview intentionally returns
503 for business routes. Disposable PostgreSQL and the signed local journey
are separate test stacks, not real Cognito/provider acceptance.

## Required application checks

From `frontend/`:

```sh
npm ci
npm run format:check
npm run lint
npm run test:coverage
npm run build
```

From `backend/`, with the environment installed:

```sh
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=63
```

These are the module forms of CI's `ruff`/`pytest` commands. Backend tests follow
`*_tests.py` (`pytest.ini`). Frontend coverage thresholds in `vite.config.js` are
50% lines/statements, 60% functions and 70% branches. No dedicated static typecheck
script is configured in either service; do not describe build/lint as one.

Root `make test` runs backend and frontend tests; `make coverage` enforces coverage.
`make format` writes formatting and `make lint` checks both services. Use the
explicit commands above to match required CI gates.

From root with the respective running/disposable containers:

```sh
node --test tests/container-smoke.test.mjs
node tests/postgres/run.mjs
```

Smoke tests support alternate `ROADTRIPS_SMOKE_API`/`ROADTRIPS_SMOKE_WEB` URLs;
match the preview frontend/CORS configuration. PostgreSQL tests create unique
projects and preserve source/restore volumes and backups. See the runbook for
isolated Python image checks and `tests/journey/run.py`'s separate Mentro fixture
prerequisites. Do not use production data to satisfy a local gate.

## Focused investigation

Run `python -m tests.agent.token_benchmark` from `backend/`; the scripted proxy
is explained in `docs/agent-token-benchmark.md` and is not live billing evidence.
Run `python -m app.routing.benchmark` there for the offline registered-planner
benchmark; HTTP `/benchmark` requires explicit enablement and authentication.
Useful regression suites are `backend/tests/agent/`, `backend/tests/routing/`,
`frontend/src/tests/`, and `backend/tests/db_integration_probe.py` through the
disposable PostgreSQL runner. Use focused checks for documentation-only changes;
preserve thresholds and distinguish baseline/environment failures from regressions.
