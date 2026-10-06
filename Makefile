.PHONY: run debug run-backend run-frontend test test-backend test-frontend \
        coverage coverage-backend coverage-frontend format lint lint-fix

ifeq ($(OS),Windows_NT)
PYTHON = .venv/Scripts/python.exe
else
PYTHON = .venv/bin/python
endif

## Run both development servers on Windows, macOS, Linux, or WSL
run:
	@node scripts/dev.mjs

## Run with per-turn agent tool and trip-profile logs
debug:
	@node scripts/dev.mjs --debug

run-backend:
	@node scripts/dev.mjs --backend-only

run-frontend:
	@node scripts/dev.mjs --frontend-only

## Run all tests from the repo root
test:
	cd backend && $(PYTHON) -m pytest
	cd frontend && npm test

## Run only backend tests
test-backend:
	cd backend && $(PYTHON) -m pytest

## Run only frontend tests
test-frontend:
	cd frontend && npm test

## Run coverage for both (enforces thresholds — fails if below minimums)
coverage:
	cd backend && $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=63
	cd frontend && npm run test:coverage

## Run only backend coverage
coverage-backend:
	cd backend && $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=63

## Run only frontend coverage
coverage-frontend:
	cd frontend && npm run test:coverage

## Format all code (backend: ruff, frontend: prettier)
format:
	cd backend && $(PYTHON) -m ruff format .
	cd frontend && npm run format

## Lint all code (backend: ruff check, frontend: eslint)
lint:
	cd backend && $(PYTHON) -m ruff check .
	cd frontend && npm run lint

## Fix auto-fixable lint issues
lint-fix:
	cd backend && $(PYTHON) -m ruff check --fix .
	cd frontend && npm run lint -- --fix
