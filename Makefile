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

## Run only backend tests
test-backend:
	cd backend && python3.9 -m pytest
