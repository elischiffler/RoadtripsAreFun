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
│   │   ├── routers/              # Route handlers (one file per domain)
│   │   │   ├── routing_api.py    # Core route generation: /get-initial-route, /generate-final-route
│   │   │   ├── location_api.py   # Location resolution: /validate-location
│   │   │   ├── itinerary_api.py  # Itinerary generation: /generate-itinerary
│   │   │   ├── car_api.py        # Car data: /get-car-details, /get-gas-price (FuelEconomy.gov)
│   │   │   ├── chat_api.py       # Chat CRUD: /chats, /chats/create, /chats/update, /chats/delete
│   │   │   └── routing_fns/
│   │   │       └── webscraping_fns.py  # Google Hotels scraping logic
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
│   │   └── routing_api/
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
│   │   ├── components/           # Shared/global UI components
│   │   │   ├── GlobalHeader.jsx  # Fixed top nav bar (logo + auth actions)
│   │   │   ├── LogoButton.jsx    # Animated SVG logo linking to home
│   │   │   ├── Map.jsx           # Mapbox GL map wrapper
│   │   │   ├── AuthWrapper.jsx   # Cognito auth session guard
│   │   │   ├── Theme.jsx         # MUI theme definition and design tokens
│   │   │   ├── SpinningWheelChip.jsx  # Landing page feature chip – route animation
│   │   │   ├── HotelChip.jsx          # Landing page feature chip – hotel animation
│   │   │   ├── ClockChip.jsx          # Landing page feature chip – clock animation
│   │   │   └── buttons/          # Reusable icon nav buttons
│   │   │       ├── ChatButton.jsx
│   │   │       ├── MapButton.jsx
│   │   │       └── ItineraryButton.jsx
│   │   ├── pages/
│   │   │   ├── HomePage/         # Landing page (hero, feature chips)
│   │   │   ├── ChatPage/         # Main trip-planning chat flow
│   │   │   │   ├── ChatPage.jsx          # Page shell: sidebar rail, message list, input area
│   │   │   │   ├── useTripWorkflow.js    # State-machine hook driving the full workflow
│   │   │   │   ├── LocationInput.jsx     # Single-field address bar + 📍 geolocation button
│   │   │   │   ├── InputBudget.jsx       # Number field for hotel budget override
│   │   │   │   ├── InputCar.jsx          # Three-field car input (year / make / model)
│   │   │   │   ├── InputStops.jsx        # Scrollable pill carousel (1–10 stops)
│   │   │   │   ├── TripSearch.jsx        # ⌘K spotlight-style trip search modal
│   │   │   │   ├── getRoute.jsx          # getInitialRoute / getFinalRoute API calls
│   │   │   │   ├── CalcBudget.jsx        # calcHotelBudget / calcGasBudget helpers
│   │   │   │   └── DatabaseUtils.jsx     # createChat / updateUserData / initializeUserData
│   │   │   ├── MapPage/          # Interactive Mapbox route view
│   │   │   ├── ItineraryPage/    # Day-by-day itinerary display
│   │   │   │   └── generateItinerary.jsx  # Calls /generate-itinerary endpoint
│   │   │   ├── AuthPages/        # Login and sign-up pages
│   │   │   │   ├── LoginPage.jsx
│   │   │   │   ├── SignUpPage.jsx
│   │   │   │   ├── PasswordField.jsx
│   │   │   │   └── PasswordRequirement.jsx
│   │   │   ├── SettingsPage.jsx  # User settings page
│   │   │   └── NotFoundPage.jsx  # 404 fallback
│   │   ├── services/
│   │   │   └── authService.ts    # Cognito auth helpers (TypeScript)
│   │   └── states/
│   │       └── UserDataContext.jsx  # React context for shared trip/user state
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

- **Routers** use `APIRouter()` and are registered in `main.py` via `app.include_router()`.
- **Models vs Schemas**: `app/models/` holds domain/response models; `app/schemas/` holds request body schemas. Keep these separate.
- **Private helpers** inside a router module are prefixed with `_` (e.g. `_call_route`, `_add_stops`, `_find_hotel`).
- **CRUD functions** in `app/crud/` take `auth_token: str` (the decoded `user_id`) as their first argument.
- **External API calls** use `requests.get()` synchronously, followed by `Model.model_validate(response.json())`.
- **Error handling**: routers catch `RequestException`, `ValidationError`, `KeyError/ValueError` and re-raise as `HTTPException` with appropriate status codes (500 for upstream failures, 502 for bad upstream responses, 404 for not found).
- **Environment variables**: loaded with `load_dotenv(override=True)` at the top of each router that needs them; accessed via `os.getenv()`.
- **Coordinates** are consistently stored and passed as `[lat, lon]` lists, except where an external API (e.g. Mapbox, GeoJSON) uses `[lon, lat]` order — be explicit about which convention is in use.
- **CI**: GitHub Actions workflows are path-filtered — backend changes only trigger the backend workflow, and vice versa.

## Frontend Chat Workflow

The trip-planning chat uses a **state machine** implemented in `useTripWorkflow.js`:

- `step` is a string enum stored in React state (`start_input` → `start_validating` → `end_input` → … → `done`)
- Each step transition triggers a `useEffect` that performs exactly one unit of async work (API call, message append, or step advance)
- User input calls `submit(action, payload)` which validates the action against the current step and advances the machine
- **No `setInterval` polling.** No mutable class instance mutations. No stale closures over chat IDs.
- `inputMode` returned by the hook tells `ChatPage` which input component to render (`'location'` | `'stops'` | `'budget'` | `'car'` | `'none'`)
- Chat messages are always read live from the `chats` context array using `selectedChatId` — never from a stale snapshot state variable
