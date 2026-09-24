# Roadtrips workflow

Frontend: React/Vite in `frontend/`, Node 24, committed npm lockfile. Backend:
FastAPI in `backend/`, Python 3.12, pinned `requirements.txt`, Ruff 0.16.7.
Read the existing `.kiro/steering` architecture guidance. Keep routing/agent
contracts in their existing modules; backend validation remains authoritative.

From `frontend/`: `npm ci`, `npm run format:check`, `npm run lint`,
`npm run test:coverage`, `npm run build`. From `backend/`: install requirements,
then `ruff format --check .`, `ruff check .`, and
`pytest --cov=app --cov-report=term-missing --cov-fail-under=63`.
From root: `node --test tests/container-smoke.test.mjs` tests running containers;
`node tests/postgres/run.mjs` runs disposable real PostgreSQL CRUD and recovery.

[Container runbook](docs/container-runbook.md) owns local config and commands;
[PostgreSQL notes](docs/self-hosted-postgres.md) own TLS behavior. The exact
checked-in README and memory CRUD DDL supports disposable local PostgreSQL
tests. The production schema and migration history remain unverified; never
infer them from the local test or use production data to clear local gates.
[Validation](docs/container-validation.md) records passed and blocked checks.
Preserve thresholds and baseline failures.

Use task branches and PRs, never merge or push main. Draft PRs are appropriate
while required verification is blocked. CI runs on every PR/main change without
production credentials; repository settings must be checked separately before
claiming enforcement. No new production Docker deployment is configured.
