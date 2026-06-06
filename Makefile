## Run both backend and frontend dev servers concurrently
run:
	@echo "Starting backend (http://localhost:8000) and frontend (http://localhost:5173)..."
	@trap 'kill 0' SIGINT; \
	  (cd backend && uvicorn app.main:app --reload --reload-dir app) & \
	  (cd frontend && PATH="$$(pwd)/node_modules/.bin:$$PATH" npm run dev) & \
	  wait

## Run only backend dev server
run-backend:
	cd backend && uvicorn app.main:app --reload --reload-dir app

## Run only frontend dev server
run-frontend:
	cd frontend && npm run dev

## Run all tests from the repo root
test:
	cd backend && python3.9 -m pytest
	cd frontend && npm test

## Run only backend tests
test-backend:
	cd backend && python3.9 -m pytest

## Run only frontend tests
test-frontend:
	cd frontend && npm test

## Run coverage for both (enforces thresholds — fails if below minimums)
coverage:
	cd backend && python3.9 -m pytest --cov=app --cov-report=term-missing --cov-fail-under=63
	cd frontend && npm run test:coverage

## Run only backend coverage
coverage-backend:
	cd backend && python3.9 -m pytest --cov=app --cov-report=term-missing --cov-fail-under=63

## Run only frontend coverage
coverage-frontend:
	cd frontend && npm run test:coverage

## Format all code (backend: ruff, frontend: prettier)
format:
	cd backend && ruff format .
	cd frontend && npm run format

## Lint all code (backend: ruff check, frontend: eslint)
lint:
	cd backend && ruff check .
	cd frontend && npm run lint

## Fix auto-fixable lint issues
lint-fix:
	cd backend && ruff check --fix .
	cd frontend && npm run lint -- --fix
