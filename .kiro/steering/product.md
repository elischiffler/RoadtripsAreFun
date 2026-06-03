# Product: JourneyGenie – RP Routing Service

This is the backend routing microservice for **JourneyGenie**, a road trip planning application. It generates optimized multi-stop driving routes and itineraries for users.

## Core Capabilities

- **Route generation**: Computes driving routes via the Mapbox Directions API, with support for intermediate waypoints.
- **Stop discovery**: Finds attractions along a route using the TripAdvisor API, ranked by popularity.
- **Hotel finding**: Locates hotels at nightly stopping points using Google Hotels web scraping, with Amadeus API as a fallback.
- **Itinerary building**: Converts a finalized route into a day-by-day itinerary with times and addresses.
- **Chat persistence**: Stores and retrieves user chat sessions (route state + message history) in Neon Postgres.
- **Location utilities**: Resolves coordinates to addresses and vice versa using OpenCage geocoding and Google Places.
- **Car data**: Provides car-related data for trip planning (fuel estimates, etc.).

## Users

End users plan road trips through a separate frontend. This service is consumed exclusively via REST API. Authentication uses AWS Cognito JWT tokens (decoded without signature verification to extract the `sub` claim).

## Deployment

Deployed on AWS Elastic Beanstalk via CodeBuild (`buildspec.yml`). The service runs on port 8000.
