# Product: MyRoadtrip – JourneyGenie

**MyRoadtrip** is a road trip planning application hosted at [github.com/elischiffler/MyRoadtrip](https://github.com/elischiffler/MyRoadtrip). It is a personal monorepo containing two services:

- `backend/` — Python/FastAPI routing microservice (formerly `rp-routing`)
- `frontend/` — React/Vite UI (formerly `rp-ui`)

## Core Capabilities

- **Route generation**: Computes driving routes via the Mapbox Directions API, with support for intermediate waypoints.
- **Stop discovery**: Finds attractions along a route using the TripAdvisor API, ranked by popularity.
- **Hotel finding**: Locates hotels at nightly stopping points using Google Hotels web scraping, with Amadeus API as a fallback.
- **Itinerary building**: Converts a finalized route into a day-by-day itinerary with times and addresses.
- **Chat persistence**: Stores and retrieves user chat sessions (route state + message history) in Neon Postgres.
- **Location utilities**: Resolves coordinates to addresses and vice versa using OpenCage geocoding and Google Places.
- **Car data**: Fetches fuel efficiency (MPG) and current national average gas prices from the FuelEconomy.gov API to support budget calculations.

## Users

End users plan road trips through the `frontend/` React app. The backend is consumed exclusively via REST API. Authentication uses AWS Cognito JWT tokens (decoded without signature verification to extract the `sub` claim).

## Deployment

- **Backend** — deployed on [Render](https://dashboard.render.com/web/srv-cqvu44jv2p9s739hhb60) (web service). Runs on port 8000.
- **Frontend** — deployed on [Vercel](https://vercel.com/eli-schifflers-projects/rp-ui).
