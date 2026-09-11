# Project Structure

This is a monorepo. Two services live under the root:

```
MyRoadtrip/
├── backend/                  # Python/FastAPI routing microservice (formerly rp-routing)
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point; registers all routers and CORS middleware
│   │   ├── dependencies.py       # Shared FastAPI dependency functions
│   │   ├── core/
│   │   │   └── config.py         # Settings class; loads DATABASE_URL from .env
│   │   ├── routers/              # Route handlers (one file per domain) — thin controllers
│   │   │   ├── routing_api.py    # /get-initial-route, /generate-final-route, /algorithms, /benchmark
│   │   │   ├── location_api.py   # Location resolution: /validate-location
│   │   │   ├── itinerary_api.py  # Itinerary generation: /generate-itinerary
│   │   │   ├── car_api.py        # Car data: /get-car-details, /get-gas-price (FuelEconomy.gov)
│   │   │   ├── chat_api.py       # Chat CRUD: /chats, /chats/create, /chats/update, /chats/delete
│   │   │   └── routing_fns/
│   │   │       └── webscraping_fns.py  # Google Hotels scraping logic
│   │   ├── routing/              # Pluggable route-planning algorithm layer (see below)
│   │   │   ├── base.py               # RoutePlanner interface, PlanOptions/PlanResult, PlanningError, PlanMetrics
│   │   │   ├── registry.py           # name -> planner ("greedy", "ortools"); get_planner()
│   │   │   ├── services.py           # RoutingServices injected-dependency bundle + CountingServices
│   │   │   ├── config.py             # Shared API tokens + OpenCage geolocator (loads repo-root .env)
│   │   │   ├── scheduler.py          # Shared day/hotel scheduler both planners use
│   │   │   ├── geometry.py           # find_position (pure) — elapsed time -> [lat, lon]
│   │   │   ├── pricing.py            # get_price_range (pure) — dynamic nightly hotel band
│   │   │   ├── benchmark.py          # Offline planner comparison (CLI + /benchmark)
│   │   │   ├── planners/             # One RoutePlanner per algorithm
│   │   │   │   ├── greedy.py             # Original greedy heuristic (behavior preserved)
│   │   │   │   └── ortools_knapsack.py   # OR-Tools knapsack selection
│   │   │   └── sources/              # Candidate sourcing (all external API calls)
│   │   │       ├── mapbox.py             # call_route (Mapbox Directions)
│   │   │       ├── attractions.py        # find_stop / get_details / gather_candidates (TripAdvisor)
│   │   │       └── hotels.py             # find_hotel + Google Places + Amadeus fallback
│   │   ├── models/               # Pydantic response/domain models (not DB schemas)
│   │   │   ├── routing_models/
│   │   │   │   ├── routing_models.py       # Core types: Route, MapBox, Route_Payload, etc.
│   │   │   │   ├── amadeus_models.py       # Amadeus API response models
│   │   │   │   ├── google_places_models.py # Google Places response models
│   │   │   │   └── trip_advisor_models.py  # TripAdvisor response models
│   │   │   ├── itinerary_models.py         # Itinerary_Payload, Itinerary_Day
│   │   │   ├── location_models.py          # location_payload, location_model
│   │   │   └── car_data_models.py
│   │   ├── schemas/              # Pydantic request/body schemas (API input contracts)
│   │   │   └── chat_schemas.py   # ChatSchema, ChatDataSchema, ChatLogSchema
│   │   ├── crud/                 # Database access layer (Neon/Postgres)
│   │   │   └── chat_crud.py      # All chat/route/segment read-write operations
│   │   ├── external services/    # Legacy placeholder package (superseded by app/routing/sources/)
│   │   └── utils/                # Shared helpers
│   │       ├── auth.py           # JWT decode → user_id extraction
│   │       ├── crud_helpers.py   # Route segmentation for storage
│   │       └── geolocation_helpers.py  # get_location() wrapper around OpenCage
│   ├── tests/                    # pytest test files (mirror router names)
│   │   ├── main_tests.py
│   │   ├── chat_api_tests.py
│   │   ├── itinerary_api_tests.py
│   │   ├── location_api_tests.py
│   │   ├── geolocation_tests.py
│   │   ├── routing_api/
│   │   │   ├── routing_api_tests.py
│   │   │   └── amadeus_tests.py
│   │   └── routing/              # Planner-level tests (inject fake RoutingServices, no network)
│   │       ├── conftest.py           # Route fixture + FakeServices
│   │       ├── greedy_planner_tests.py
│   │       ├── ortools_planner_tests.py
│   │       ├── scheduler_tests.py
│   │       ├── registry_tests.py
│   │       ├── metrics_tests.py
│   │       └── benchmark_tests.py
│   ├── .env                      # Local secrets (never commit)
│   ├── requirements.txt          # Pinned Python dependencies
│   └── Makefile                  # `make run` starts the dev server
│
├── frontend/                 # React/Vite UI (formerly rp-ui)
│   ├── src/
│   │   ├── main.jsx              # Vite entry point; mounts React app
│   │   ├── App.jsx               # Root component
│   │   ├── Router.jsx            # react-router-dom route definitions
│   │   ├── index.css             # Global CSS custom properties (design tokens)
│   │   ├── assets/               # Static assets bundled by Vite (images, SVGs)
│   │   ├── components/           # Shared/global UI components
│   │   │   ├── GlobalHeader.jsx  # Fixed top nav bar (logo + auth actions)
│   │   │   ├── GlobalHeader.css
│   │   │   ├── LogoButton.jsx    # Animated SVG logo linking to home
│   │   │   ├── LogoButton.css
│   │   │   ├── Map.jsx           # Mapbox GL map wrapper
│   │   │   ├── AuthWrapper.jsx   # Cognito auth session guard
│   │   │   ├── Theme.jsx         # MUI theme definition and design tokens
│   │   │   ├── ThemedTooltip.jsx # Styled MUI Tooltip matching the earthy palette
│   │   │   ├── AlgorithmSettings.jsx  # Dev-mode routing-algorithm picker (gear popup; dev builds only)
│   │   │   ├── SpinningWheelChip.jsx  # Landing page feature chip – route animation
│   │   │   ├── SpinningWheelChip.css
│   │   │   ├── HotelChip.jsx          # Landing page feature chip – hotel animation
│   │   │   ├── HotelChip.css
│   │   │   ├── ClockChip.jsx          # Landing page feature chip – clock animation
│   │   │   ├── ClockChip.css
│   │   │   └── buttons/          # Reusable icon nav buttons
│   │   │       ├── ButtonStyles.css
│   │   │       ├── ChatButton.jsx
│   │   │       ├── MapButton.jsx
│   │   │       ├── ItineraryButton.jsx
│   │   │       └── ProgressRevealIcon.jsx  # Circular sweep overlay; reveals icon as progress 0→1
│   │   ├── pages/
│   │   │   ├── HomePage/         # Landing page (hero, feature chips)
│   │   │   │   ├── HomePage.jsx
│   │   │   │   └── HomePage.css
│   │   │   ├── ChatPage/         # Main trip-planning chat flow
│   │   │   │   ├── ChatPage.jsx          # Page shell: sidebar rail, message list, input area
│   │   │   │   ├── ChatPage.css
│   │   │   │   ├── useTripWorkflow.js    # State-machine hook driving the full workflow
│   │   │   │   ├── LocationInput.jsx     # Single-field address bar + 📍 geolocation button
│   │   │   │   ├── InputAddress.jsx      # Four-field structured address form (street/city/state/zip)
│   │   │   │   ├── InputBudget.jsx       # Number field for hotel budget override
│   │   │   │   ├── InputCar.jsx          # Three-field car input (year / make / model)
│   │   │   │   ├── InputStops.jsx        # Scrollable pill carousel (1–10 stops)
│   │   │   │   ├── InputStops.css
│   │   │   │   ├── TripSearch.jsx        # ⌘K spotlight-style trip search modal
│   │   │   │   ├── TripSearch.css
│   │   │   │   ├── getRoute.jsx          # getInitialRoute / getFinalRoute API calls
│   │   │   │   ├── CalcBudget.jsx        # calcHotelBudget / calcGasBudget helpers
│   │   │   │   └── DatabaseUtils.jsx     # createChat / updateUserData / initializeUserData
│   │   │   ├── MapPage/          # Interactive Mapbox route view
│   │   │   │   ├── MapPage.jsx
│   │   │   │   └── MapPage.css
│   │   │   ├── ItineraryPage/    # Day-by-day itinerary display
│   │   │   │   ├── ItineraryPage.jsx      # Renders day/stop cards from itinerary context; floating nav buttons
│   │   │   │   ├── ItineraryPage.css
│   │   │   │   └── generateItinerary.jsx  # Calls /generate-itinerary endpoint
│   │   │   ├── AuthPages/        # Login and sign-up pages
│   │   │   │   ├── AuthPage.css
│   │   │   │   ├── LoginPage.jsx
│   │   │   │   ├── SignUpPage.jsx
│   │   │   │   ├── PasswordField.jsx
│   │   │   │   └── PasswordRequirement.jsx
│   │   │   ├── SettingsPage.jsx  # User settings page
│   │   │   └── NotFoundPage.jsx  # 404 fallback
│   │   ├── services/
│   │   │   └── authService.ts    # Cognito auth helpers (TypeScript)
│   │   ├── states/
│   │   │   └── UserDataContext.jsx  # React context for shared trip/user state
│   │   └── tests/                # Vitest + Testing Library unit/component tests
│   │       ├── setup.js              # Global test setup (jest-dom matchers)
│   │       ├── testUtils.jsx         # Shared render helpers and mock providers
│   │       ├── AuthWrapper.test.jsx
│   │       ├── CalcBudget.test.js
│   │       ├── DatabaseUtils.test.js
│   │       ├── GlobalHeader.test.jsx
│   │       ├── HomePage.test.jsx
│   │       ├── InputBudget.test.jsx
│   │       ├── InputCar.test.jsx
│   │       ├── InputStops.test.jsx
│   │       ├── ItineraryPage.test.jsx
│   │       ├── LocationInput.test.jsx
│   │       ├── LoginPage.test.jsx
│   │       ├── MapPage.test.jsx
│   │       ├── PasswordRequirement.test.jsx
│   │       ├── SignUpPage.test.jsx
│   │       ├── TripSearch.test.jsx
│   │       ├── UserDataContext.test.jsx
│   │       └── useTripWorkflow.helpers.test.js
│   ├── public/               # Static assets
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── .github/
│   └── workflows/
│       ├── backend-ci.yml    # Runs pytest on changes to backend/**
│       └── frontend-ci.yml   # Runs npm build on changes to frontend/**
│
├── .gitignore                # Root gitignore covering both services
├── .env.example              # Template for required environment variables
└── README.md
```

## Conventions

- **Routers** use `APIRouter()` and are registered in `main.py` via `app.include_router()`. Routers are **thin controllers** — `routing_api.py` no longer contains the planning algorithm; it selects a planner, builds `RoutingServices`, calls it, and shapes the response.
- **Models vs Schemas**: `app/models/` holds domain/response models; `app/schemas/` holds request body schemas. Keep these separate.
- **Private helpers** inside a module are prefixed with `_` (e.g. `_call_route`, `_find_hotel`).
- **CRUD functions** in `app/crud/` take `auth_token: str` (the decoded `user_id`) as their first argument.
- **External API calls** use `requests.get()` synchronously, followed by `Model.model_validate(response.json())`.
- **Error handling**: routers catch `RequestException`, `ValidationError`, `KeyError/ValueError` and re-raise as `HTTPException` with appropriate status codes (500 for upstream failures, 502 for bad upstream responses, 404 for not found).
- **Environment variables**: loaded with `load_dotenv(override=True)` at the top of each router that needs them; accessed via `os.getenv()`.
- **Coordinates** are consistently stored and passed as `[lat, lon]` lists, except where an external API (e.g. Mapbox, GeoJSON) uses `[lon, lat]` order — be explicit about which convention is in use.
- **CI**: GitHub Actions workflows are path-filtered — backend changes only trigger the backend workflow, and vice versa.

## Routing Algorithm Layer (`app/routing/`)

Route planning is split into a **pluggable-algorithm architecture** so different
planners can be swapped without touching the endpoint, DB layer, or frontend.

- **The interface.** Every algorithm is a `RoutePlanner` with one method:
  `plan(initial_route, options: PlanOptions, services: RoutingServices) -> PlanResult`.
  Same inputs, same output, regardless of algorithm.
- **Selection.** `routing_api.py` picks a planner by name via
  `registry.get_planner(...)`. Precedence: request `Route_Payload.algorithm` →
  `ROUTING_ALGORITHM` env var → default `"greedy"`. Unknown name → 400.
  `GET /algorithms` lists registered planners.
- **Two shipped planners.** `greedy` (original heuristic, behavior preserved
  byte-for-byte) and `ortools` (OR-Tools knapsack selection). Adding one = a new
  file in `planners/` + a `register_planner(...)` call. No endpoint changes.
- **Selection vs scheduling.** Planners differ only in *selection* (which
  attractions). *Scheduling* — the day-by-day walk that inserts overnight hotels,
  the 09:00–16:00 window, the 2h detour — is shared in `scheduler.py`, which both
  planners call. This keeps them comparable (any benchmark difference is
  selection-driven).
- **Injected dependencies.** Planners never call external APIs directly; they go
  through `RoutingServices` (`find_stop`, `find_hotel`, `find_position`,
  `get_price_range`, `gather_candidates`). Real implementations live in
  `sources/`. This is what makes planners testable with fakes (see `tests/routing/`).
- **Neutral errors.** Planners raise `PlanningError` (with an optional status
  hint); the router maps it to `HTTPException`.
- **The stopping-point contract is fixed.** Any planner must emit stop dicts with
  `name`, `type` (`"stop"`/`"hotel"`/`"end"`/`"generic"`), `coordinates`
  (`[lat, lon]`), and `price` for hotels — the itinerary endpoint, CRUD storage,
  and frontend all depend on this shape.
- **Metrics + benchmark.** `PlanMetrics` (score, cost, detour, latency, API
  calls) is computed by `RoutePlanner.run()` (the benchmark path); the normal
  request path calls `plan()` with no metrics overhead. `benchmark.py` compares
  planners on cached, deterministic inputs — CLI (`python -m app.routing.benchmark`)
  or `GET /benchmark` (gated by `BENCHMARK_ENABLED=true`).
- **Known follow-up.** Attraction *values* are a flat placeholder; the knapsack's
  selection advantage only shows once real popularity rank feeds the objective.
  The planned next planner is CP-SAT (`ortools.sat`) for soft stop-count + budget
  + hotel-aware selection. See `docs/pluggable-routing-refactor.md`.

## Frontend Chat Workflow

The trip-planning chat uses a **state machine** implemented in `useTripWorkflow.js`:

- `step` is a string enum stored in React state (`start_input` → `start_validating` → `end_input` → … → `done`)
- Each step transition triggers a `useEffect` that performs exactly one unit of async work (API call, message append, or step advance)
- User input calls `submit(action, payload)` which validates the action against the current step and advances the machine
- **No `setInterval` polling.** No mutable class instance mutations. No stale closures over chat IDs.
- `inputMode` returned by the hook tells `ChatPage` which input component to render (`'location'` | `'stops'` | `'budget'` | `'car'` | `'none'`)
- Chat messages are always read live from the `chats` context array using `selectedChatId` — never from a stale snapshot state variable
