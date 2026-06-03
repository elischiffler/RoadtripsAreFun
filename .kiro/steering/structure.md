# Project Structure

This is a monorepo. Two services live under the root:

```
MyRoadtrip/
├── backend/                  # Python/FastAPI routing microservice (formerly rp-routing)
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point; registers all routers and CORS middleware
│   │   ├── core/
│   │   │   └── config.py         # Settings class; loads DATABASE_URL from .env
│   │   ├── routers/              # Route handlers (one file per domain)
│   │   │   ├── routing_api.py    # Core route generation: /get-initial-route, /generate-final-route
│   │   │   ├── location_api.py   # Location resolution endpoints
│   │   │   ├── itinerary_api.py  # Itinerary generation from a finalized route
│   │   │   ├── car_api.py        # Car data endpoints
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
│   ├── src/                  # React source files
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
