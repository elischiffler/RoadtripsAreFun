# Pluggable Routing Algorithms — Refactor Plan

A plan for restructuring the backend so different route-planning algorithms can
be swapped in "plug and play" style. This builds directly on the design thinking
already captured in [algorithm-analysis.md](./algorithm-analysis.md) (the four
candidate approaches) and [route-finding.md](./route-finding.md) (how the current
code works).

> **Scope of this refactor.** This is an *architecture* change, not an algorithm
> change. The goal is to carve out a clean seam so that the existing greedy
> heuristic becomes "algorithm #1 behind an interface," and future algorithms
> (OR-Tools, simulated annealing, AI/hybrid) can be dropped in without touching
> the endpoint, the DB layer, the frontend contract, or the candidate-sourcing
> services. Behavior of the current algorithm must not change.

---

## 1. Where the seam is today

Route generation happens in two phases (see route-finding.md). The refactor only
touches phase 2 (`POST /generate-final-route`).

Inside `backend/app/routers/routing_api.py`, three groups of code exist today,
tangled together in one file:

| Group | Functions | Role | Belongs to |
|---|---|---|---|
| **The planner** | `_add_stops`, `_find_position`, `_get_price_range` | Decides *which* stops/hotels to insert and *how the trip is scheduled across days*. | The swappable algorithm |
| **Candidate sourcing** | `_find_stop` / `_get_details` (TripAdvisor), `_find_hotel` + Amadeus helpers + `_get_nearby_city` (Google/Amadeus), `find_google_hotels` (scraper) | Given a `(lat, lon)`, returns a real attraction or a real hotel. | Shared infrastructure |
| **Routing + assembly** | `_call_route` (Mapbox), the endpoint body of `get_final_route` (re-route through stops, leg-walking, address backfill, `Route` construction) | Talks to Mapbox and shapes the HTTP response. | Shared infrastructure |

The **planner** is the only part that should vary between algorithms. Everything
else is shared plumbing that every algorithm reuses.

**The natural interface.** Every algorithm consumes the same inputs and produces
the same output:

```
plan(initial_route, num_stops, budget, start, services) -> (stopping_points, total_cost)
```

- `initial_route: MapBox_Route` — the raw single-leg route from phase 1.
- `num_stops: int`, `budget: float`, `start: datetime` — user inputs.
- `services` — injected candidate-sourcing + geometry helpers (see §3).
- returns `(stopping_points: list[dict], total_cost: float)` — exactly what
  `_add_stops` returns today.

This matches the docs' framing: all four approaches take
`Start, End, num_stops, budget, prefs` and emit a scheduled set of stops that the
same downstream "re-route through chosen stops" step consumes.

---

## 2. Target directory layout

```
backend/app/routing/                     # new package: the algorithm layer
├── __init__.py
├── base.py                  # RoutePlanner protocol/ABC + shared dataclasses
├── registry.py              # name -> planner mapping; get_planner(name)
├── services.py              # RoutingServices bundle (injected deps)
├── geometry.py              # find_position + interpolation (pure, no I/O)
├── pricing.py               # get_price_range (pure, no I/O)
└── planners/
    ├── __init__.py
    └── greedy.py            # the current _add_stops logic, unchanged behavior
```

Candidate-sourcing stays where it is functionally (Mapbox/TripAdvisor/hotels),
but gets pulled behind the `RoutingServices` bundle so planners never import
`requests` or hit an API directly. Options for where that code physically lives:

- **Minimal:** leave `_find_stop` / `_find_hotel` / `_call_route` in
  `routing_api.py` and just pass them into `RoutingServices`. Lowest churn.
- **Cleaner (recommended follow-up, not required for the seam):** move them into
  `backend/app/routing/services/` (e.g. `attractions.py`, `hotels.py`,
  `mapbox.py`) so the router file only wires things together. This aligns with
  the currently-empty `backend/app/external services/` placeholder package.

> A folder-per-algorithm is only needed once a planner grows past one file (e.g.
> the classical optimizer with a separate `model.py` + `solver.py`). Start
> file-per-algorithm under `planners/` and promote to a folder when it grows.

---

## 3. The injected dependencies (`RoutingServices`)

Rather than have each planner import candidate-sourcing functions, bundle them so
planners depend on an *interface*, not on TripAdvisor/Google/Mapbox specifics.
This is also what makes tests trivial (pass fakes) and what the docs' "gather
candidates up front" optimizer approaches will reuse.

```python
@dataclass
class RoutingServices:
    find_stop:      Callable[[str, float, float, int], Awaitable[dict]]   # attractions
    find_hotel:     Callable[[float, float, PriceRange, datetime, int], Awaitable[dict]]
    find_position:  Callable[[list, list, float], list[float]]            # pure
    get_price_range: Callable[..., PriceRange]                            # pure
```

`get_final_route` builds one `RoutingServices` instance (wiring the real
functions) and hands it to the selected planner. A test builds one with fakes.

---

## 4. Selecting the algorithm ("plug and play")

`registry.py` maps a name to a planner factory. Selection precedence:

1. **Per-request override** (optional): a field on `Route_Payload`, e.g.
   `algorithm: Optional[str] = None`. Lets the frontend or a benchmark harness
   pick a planner without redeploying.
2. **Environment default:** `ROUTING_ALGORITHM` env var (e.g. `greedy`).
3. **Hard default:** `greedy`, so nothing changes if neither is set.

```python
planner = get_planner(payload.algorithm or os.getenv("ROUTING_ALGORITHM", "greedy"))
stopping_points, total_cost = await planner.plan(initial_route, num_stops, budget, start, services)
```

Unknown name → `HTTPException(400)`. Adding a new algorithm = drop a file in
`planners/`, register it in `registry.py`. No endpoint changes.

---

## 5. Hard contracts that must NOT change

These are the invariants any planner must honor. They are the reason this is a
careful refactor and not a rewrite.

- **`stopping_points` dict shape.** The itinerary endpoint (`/generate-itinerary`)
  reads `stop["duration"]`, `stop["name"]`, `stop["type"]` (branches on
  `"hotel"` / `"stop"`), and `stop.get("url"/"price"/"address")`. Hotels must
  carry `price` (it is summed into `total_cost` and drives the next-day 9AM
  reset); attractions use `type: "stop"` (drives the +2h itinerary bump).
- **Coordinate order.** Planner emits `coordinates` as `[lat, lon]`;
  `get_final_route` flips to `[lon, lat]` for the Mapbox waypoint string. Do not
  move that flip into the planner.
- **`Route` response shape.** Must keep `cost`, `stops`, and `geometry`
  (`coordinates`). The frontend reads `finalRoute.cost`; map/itinerary pages read
  `stops` and `geometry`. `steps` stays empty by design.
- **Zero-stops / short-trip path.** `num_stops=0` on a short trip must still make
  only Mapbox calls (no hotel/attraction search). A test pins this.
- **No DB writes in route generation.** Persistence (`segment_route`,
  `_store_legs`) stays entirely in the CRUD layer and assumes
  `geometry.coordinates` + `legs[].steps[].geometry.coordinates`. The refactor
  must not change the shape of what gets stored.
- **Function names tests patch.** Tests patch
  `app.routers.routing_api.requests.get`, `get_location`, `find_google_hotels`,
  `_get_nearby_city`, and call `_find_hotel` / `_get_amadeus_token` directly. If
  those move, the tests must move with them (see §7).

---

## 6. Migration steps (ordered, each independently verifiable)

1. **Create the package skeleton** (`base.py`, `registry.py`, `services.py`)
   with the `RoutePlanner` interface and `RoutingServices` dataclass. No behavior
   yet. `pytest` still green.
2. **Extract pure helpers** `_find_position` → `geometry.py` and
   `_get_price_range` → `pricing.py` verbatim. Re-import them in `routing_api.py`
   so existing references keep working. Run tests.
3. **Move `_add_stops` into `planners/greedy.py`** as `GreedyPlanner.plan`,
   changing only how it *reaches* `find_stop`/`find_hotel`/`find_position`/
   `get_price_range` — via the injected `services`, not module globals. Behavior
   identical. Run tests.
4. **Wire the endpoint:** `get_final_route` builds `RoutingServices`, resolves the
   planner via the registry, calls `planner.plan(...)`. Everything after (re-route,
   leg-walking, `Route` build) is unchanged. Run tests.
5. **Add the selection knob** (`algorithm` field on `Route_Payload` +
   `ROUTING_ALGORITHM` env, defaulting to `greedy`). Run tests.
6. **Docs:** update `route-finding.md` to point at the new package boundary and
   note that `_add_stops` now lives behind `RoutePlanner`.

Each step is a small, revertible commit. After each, run the backend test suite
(`cd backend && pytest`) — the existing tests are the safety net that proves
behavior is unchanged.

---

## 7. Test strategy

- **Keep the existing endpoint tests passing unchanged** wherever possible — they
  are the behavior-preservation proof. If step 3/4 moves a patched symbol, update
  only the patch target, not the assertions.
- **Add a planner-level unit test** for `GreedyPlanner.plan` that injects a fake
  `RoutingServices` (canned attractions/hotels, no network). This is the first
  test that exercises the algorithm in isolation — impossible today because
  `_add_stops` reaches out to live APIs. It becomes the template every future
  algorithm reuses.
- **Add a registry test:** known name resolves, unknown name raises.
- Do NOT add tests for the future OR-Tools/AI planners in this PR — this PR only
  delivers the seam + the greedy planner behind it.

---

## 8. Decisions made (and what shipped)

The open design questions were resolved in favor of the cleanest SRP boundaries
and easiest long-term maintainability across planners:

1. **Selection surface — both.** An optional `algorithm` field on `Route_Payload`
   plus a `ROUTING_ALGORITHM` env var, defaulting to `greedy`. The frontend is
   untouched by default; a request or the environment can override.
2. **Interface carries a `PlanOptions` object.** `plan(initial_route, options,
   services)`. `PlanOptions` bundles `num_stops`, `budget`, `start`, the day
   window, and reserved `preferences` / `weights` fields — so preference-aware
   planners land without a signature change. Planners return a `PlanResult`.
3. **Both sourcing styles exposed.** `RoutingServices` provides per-point
   `find_stop` / `find_hotel` (used by greedy) *and* batch `gather_candidates`
   (used by the OR-Tools planner).
4. **Candidate-sourcing moved into `app/routing/sources/`** (`mapbox.py`,
   `attractions.py`, `hotels.py`), each owning its external API. The router
   re-exports them so existing test patch targets stay valid.
5. **Neutral `PlanningError` at the boundary.** Planners raise `PlanningError`
   (carrying an optional status hint); the endpoint maps it to `HTTPException`.
   Greedy's internal retry/radius logic is preserved inside the planner.
6. **Naming.** Package `app.routing`; planner keys `greedy` and `ortools`.
7. **Scope.** This PR ships the seam **plus two planners**: the extracted greedy
   planner and a new OR-Tools knapsack planner.

### What shipped

```
backend/app/routing/
├── __init__.py          # public exports
├── base.py              # RoutePlanner ABC, PlanOptions, PlanResult, PlanningError
├── registry.py          # name -> planner ("greedy", "ortools"); get_planner()
├── services.py          # RoutingServices dependency bundle
├── config.py            # shared tokens + geolocator
├── geometry.py          # find_position (pure)
├── pricing.py           # get_price_range (pure)
├── planners/
│   ├── greedy.py            # GreedyPlanner (the original _add_stops behavior)
│   └── ortools_knapsack.py  # ORToolsKnapsackPlanner
└── sources/
    ├── mapbox.py            # call_route (Mapbox Directions)
    ├── attractions.py       # find_stop / get_details / gather_candidates (TripAdvisor)
    └── hotels.py            # find_hotel + Google Places + Amadeus fallback
```

`backend/app/routers/routing_api.py` is now a thin controller: it fetches the
Mapbox route, builds `RoutingServices`, resolves the planner, runs it, and shapes
the `Route` response. `requirements.txt` gained `ortools==9.10.4067` (plus its
`absl-py`, `immutabledict`, `protobuf` deps).

### The OR-Tools knapsack planner

`ortools` gathers a candidate pool of attractions along the route corridor
(`gather_candidates`), then models attraction selection as a **2-dimensional 0/1
knapsack** solved by OR-Tools' branch-and-bound solver:

- profit = each attraction's value (from popularity rank),
- weight dimension 0 = a detour-time cost bounded by a detour budget,
- weight dimension 1 = 1 per item, capped at `num_stops` (so at most the
  requested number of attractions are chosen).

The selected attractions are then scheduled by the **shared scheduler** (see
below), so the emitted `stopping_points` honor the identical downstream contract.
Unlike greedy, it evaluates the whole candidate set together, so it can trade a
marginally lower-ranked attraction away to reduce total detour.

### Shared scheduler (`app/routing/scheduler.py`)

Route planning splits into two halves:

- **Selection** — *which* attractions to visit. This is where the algorithms
  differ: greedy discovers attractions on the fly as it walks; OR-Tools chooses a
  subset up front with the knapsack solver.
- **Scheduling** — *how* the chosen stops are placed in time: the 09:00–16:00
  daily driving window, the ~2h attraction detour, when to insert an overnight
  hotel, the hotel retry loop, and the running cost/budget updates.

Scheduling is now a single shared function, `schedule_route(...)`, that **both**
planners call. It is a verbatim extraction of the original greedy loop, so
greedy's output is unchanged. The one thing that varies — which attraction goes
at a given segment boundary — is abstracted behind a `stop_provider`:

- Greedy passes the live `services.find_stop` (on-the-fly discovery).
- OR-Tools passes a provider that dispenses its knapsack-selected attractions in
  order.

**Why this matters for benchmarking:** because both planners schedule with the
identical loop, the two produced trips differ *only* in their attraction set.
Any difference the benchmark reports (score, cost, hotel count) is therefore
attributable purely to selection — which is exactly the variable under study.
A test (`test_planners_schedule_identically_given_same_selection`) pins this: the
same selection through both planners yields the same hotel count and cost.

> **Not yet done — hotel-aware selection.** Selection currently runs *before*
> scheduling, so the knapsack can't see that a given attraction might tip the
> trip into an extra hotel night. A fully global optimizer would fold that hotel
> cost back into the objective. The shared-scheduler seam is where that feedback
> would plug in later; the split doesn't introduce the limitation (greedy has it
> too), it just makes the boundary explicit.

### Tests

- All original endpoint tests pass unchanged in behavior (patch targets updated
  to the new source module locations).
- New planner-level tests under `backend/tests/routing/` inject a fake
  `RoutingServices` (no network): greedy behavior, OR-Tools selection/ordering,
  and registry resolution. This is the template every future algorithm reuses.
