# Testing the Routing Algorithms on localhost

A hands-on guide for running the two routing planners (`greedy` and `ortools`)
locally, comparing them, and reading the results. Covers three ways to test,
from fastest to most realistic:

1. **Offline benchmark** (no API keys, no network) — the fastest way to compare.
2. **Unit tests** — verify the planners in isolation.
3. **Live server** — hit the real endpoints with `curl`.

All commands run from the `backend/` directory.

---

## 0. One-time setup

The backend targets **Python 3.9**. Create a virtual environment and install
dependencies (this includes `ortools`, added for the knapsack planner):

```bash
cd backend

# Create + activate a 3.9 virtualenv (adjust the python path to your install)
python3.9 -m venv venv
source venv/bin/activate

# Install everything, including ortools
pip install -r requirements.txt
```

Verify OR-Tools imports:

```bash
python -c "from ortools.algorithms.python import knapsack_solver; print('ortools OK')"
```

> If you don't use a venv, substitute your Python 3.9 interpreter directly, e.g.
> `/opt/homebrew/opt/python@3.9/bin/python3.9`, in the commands below.

---

## 1. Offline benchmark (recommended first)

This is the best tool for *comparing* the algorithms. It runs every planner
against a fixed set of trip scenarios using **cached, deterministic candidate
data** — so it makes zero external API calls, needs no keys, and gives identical
results every run. Any difference in the numbers comes purely from the algorithm.

### Run it from the CLI

```bash
# Human-readable comparison table
python -m app.routing.benchmark

# Only compare specific algorithms
python -m app.routing.benchmark --algorithms greedy ortools

# Machine-readable JSON (for graphing / saving)
python -m app.routing.benchmark --json > benchmark.json
```

### Reading the table

```
CASE: cross_country_5_stops  (stops=5, budget=$1200, 40h drive)
algorithm         score       attractions   hotels   cost       detour_h   ms         api
---------------------------------------------------------------------------------------------
greedy *          -200.0      5             5        600.0      10.0       1.57       10
ortools           -591.667    5             6        720.0      10.0       2.85       7
```

| Column | Meaning |
|---|---|
| `algorithm` | The planner. `*` marks the best objective score for that case. |
| `score` | The scalar objective (higher is better): `w_v·value − w_c·cost − w_d·detour`. |
| `attractions` / `hotels` | Counts of each stop type in the produced trip. |
| `cost` | Summed hotel cost. |
| `detour_h` | Total hours lost to attraction detours. |
| `ms` | Planning wall-clock time. |
| `api` | Number of external candidate-sourcing calls (the real cost driver). |

The objective weights live in `app/routing/base.py` (`DEFAULT_WEIGHTS`). Tune them
to reflect a traveler profile ("see everything" vs "cheap and fast") and re-run.

### Adding your own scenarios

Edit `DEFAULT_CASES` in `app/routing/benchmark.py`:

```python
BenchmarkCase("my_case", duration_hours=12, num_stops=3, budget=800),
```

---

## 2. Unit tests

Run the planner + metrics + benchmark tests:

```bash
# Just the routing layer
pytest tests/routing -v

# The whole backend suite
pytest -v
```

These use injected fake services (no network), so they're fast and deterministic.
`tests/routing/` is the template for testing any future algorithm.

---

## 3. Live server (real endpoints)

To exercise the actual HTTP flow, run the dev server:

```bash
make run
# equivalent: uvicorn app.main:app --reload --reload-dir app
```

The server listens on `http://localhost:8000`. Live route generation calls real
external APIs (Mapbox, TripAdvisor, Google), so you need a populated `.env`
(see `.env.example`).

### Step 1 — get an initial route

`/generate-final-route` needs a raw Mapbox route as input, so first fetch one:

```bash
curl -s "http://localhost:8000/get-initial-route?start_lat=33.7186&start_lon=-117.9286&end_lat=40.7128&end_lon=-74.0060" \
  > initial_route.json
```

### Step 2 — generate a final route with a chosen algorithm

Build the payload from that initial route and pick the planner via the
`algorithm` field. Using Python to assemble the body keeps it simple:

```bash
# GREEDY
python - <<'PY'
import json, requests
initial = json.load(open("initial_route.json"))
body = {"initial_route": initial, "num_stops": 3, "budget": 800, "algorithm": "greedy"}
r = requests.post("http://localhost:8000/generate-final-route", json=body)
print("status", r.status_code)
data = r.json()
print("cost", data["cost"], "stops", len(data["stops"]))
PY
```

Swap `"algorithm": "greedy"` for `"algorithm": "ortools"` to run the knapsack
planner on the same route.

Selection precedence: the request `algorithm` field wins; otherwise the
`ROUTING_ALGORITHM` env var; otherwise the default (`greedy`). To change the
default without touching requests:

```bash
ROUTING_ALGORITHM=ortools make run
```

An unknown algorithm name returns HTTP **400**.

### Optional — the /benchmark endpoint

The offline benchmark is also exposed over HTTP, gated behind an env flag so it
never runs in production:

```bash
BENCHMARK_ENABLED=true make run

# in another terminal:
curl -s "http://localhost:8000/benchmark?algorithms=greedy,ortools" | python -m json.tool
```

It returns the same comparison payload as the CLI (and still uses cached data, so
no live API calls).

---

## Quick reference

| Goal | Command |
|---|---|
| Compare algorithms (offline) | `python -m app.routing.benchmark` |
| Compare, JSON output | `python -m app.routing.benchmark --json` |
| Run planner tests | `pytest tests/routing -v` |
| Start dev server | `make run` |
| Default to OR-Tools | `ROUTING_ALGORITHM=ortools make run` |
| Benchmark over HTTP | `BENCHMARK_ENABLED=true make run` then GET `/benchmark` |

---

## How it fits together

- **Algorithms** live in `app/routing/planners/` (`greedy.py`, `ortools_knapsack.py`).
- **Metrics** (`PlanMetrics`, `score_trip`) live in `app/routing/base.py`; they're
  attached by `RoutePlanner.run()`, which the benchmark calls. The normal request
  path calls `plan()` and carries no metrics overhead.
- **API-call counting** comes from `CountingServices` (`app/routing/services.py`),
  which transparently wraps the sourcing calls — no planner code knows about it.
- **The benchmark** (`app/routing/benchmark.py`) swaps in cached candidate data so
  runs are free and repeatable.

See [pluggable-routing-refactor.md](./pluggable-routing-refactor.md) for the
architecture and [algorithm-analysis.md](./algorithm-analysis.md) for the
objective function and the algorithm comparison framing.
