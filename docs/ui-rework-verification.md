# Standalone guided planner verification

This file supersedes the chat-dependent implementation evidence from PR55 head
96b232cb57b30f7c3aec5fed1a53e5abca3879a9. That evidence remains historical.
The current integration includes removal PR56 at
8e9cba550f86be0d1b79045e66d76aea459aad3d and keeps its retired files deleted.

## Current contract

Authenticated /plan is a standalone form/container. It sends structured requests to:
- POST /validate-location, retaining both single matches and multiple 409 candidates for explicit user confirmation;
- GET /get-initial-route and POST /generate-final-route with the complete canonical preference vector, occupancy, hotel target, local departure and scheduling policy;
- POST /generate-itinerary with the unchanged returned route, preserving shared visit-duration/timing fields;
- existing owner-scoped /chats CRUD solely for compatible saved-trip records, with empty message arrays for new trips.

The full nightly target is stored in structured tripProfile metadata; the obsolete integer hotelBudget slot stays null, preserving fractional amounts.

There is no form-to-message serialization, composer, conversation orchestration or retired API call. Saved IDs load before allocation. Creating a row precedes updates; failed saves stay visibly unsaved. Partial routes remain available, and itinerary/save retries do not rerun route generation. Account changes and aborted requests discard late client results. /chat remains a bookmark redirect to /trips.

The rated-place mapping, skip/unsure/manual controls and normalized preference graph are retained. The result graph is labeled “Interests sent to the planner”; the direct route API does not echo an effective-weight receipt. Car details are retained as saved metadata; fuel cost is not estimated. AI Studio remains separately gated with its controls/history/comparison semantics.

## Checks

- Node 24 install, frontend format check/lint/build passed.
- Frontend: 35 files / 236 tests passed; 91.06% lines/statements, 84.58% branches, 87.22% functions; thresholds unchanged.
- Backend Ruff format/check passed. Full suite: 1,656 passed, 128 skipped; 79.23% coverage against the unchanged 63% gate.
- The focused adapter/container tests cover provider choices, typed preference payloads, partial results, create-before-update, failed update retry, saved-ID load errors, account switch and preservation of returned timing fields.
- Dedicated Chromium fixture flow passes: retained draft answers and 320px layout, explicit ambiguous-address choice, structured preferences in the route payload, partial route save, itinerary-only retry, unchanged old row, selected map/itinerary reload, old bookmark redirect and Studio gate.
- Three exercised Axe WCAG A/AA views have zero findings: interests at 320px, mobile address confirmation and mobile structured results.
- The captured route and saved-trip payloads also pass the retained backend Pydantic schemas locally, including a $150.25 target and unchanged visit-timing facts.

All API traffic in that browser flow is intercepted. External requests are aborted, including legacy font requests; no live Mentro or other provider calls are made.

Browser reproduction (start a separate instance; never restart the user's PC preview):
1. Install playwright-core@1.64.1 and @axe-core/playwright@4.14.0 under /tmp/roadtrips-ui-browser.
2. From frontend: VITE_BACKEND_SERVER=http://127.0.0.1:18987/ VITE_COGNITO_ENDPOINT=http://127.0.0.1:18987 VITE_LOCAL_JOURNEY=true VITE_USERPOOL_ID=fixture-pool VITE_CLIENT_ID=fixture-client npm run dev -- --host 127.0.0.1 --port 5187
3. From root: node tests/ui-rework/browser-check.mjs
UI_BROWSER_TOOLS_DIR, CHROMIUM_PATH and ROADTRIPS_UI_EVIDENCE_DIR configure local tools/output only.

## Compatibility and open gates

The retained direct route API interprets the supplied departure as origin-local wall time during planning and resolves timezones through its provider. However, its earlier is_upcoming_departure check treats a naive value as UTC. Near-now departures can therefore be accepted/rejected against the wrong instant. This existing backend boundary cannot be repaired correctly by guessing the browser timezone. A separate backend-owner change should localize and validate the origin departure before that future check, using the retained trip_dates/departure helpers; ambiguous/nonexistent DST times must remain rejected. This integration makes no backend behavior change and stays draft pending that compatibility decision.

Real Cognito/provider planning and actual persistence remain unverified. Live Mentro calls require explicit user approval. Fixture results are not real trips, prices or performance statistics. The disposable PostgreSQL probe was adapted to read retained presentation JSON by dictionary keys, preserving the same four value checks after retirement. This changes no application behavior.

Local Docker build networking was already blocked in the prior phases; container/disposable PostgreSQL gates must be satisfied by exact-head CI. No production deploy, data purge or security-setting change is part of this integration.

PR51 timing components and backend shared provider/message/profile interfaces are preserved. The coordinator should integrate/review removal PR56 before PR55, then evaluate the combined PR51 functionality. The user's task01a142f0 PC preview was not edited or restarted; later sync must bring its local changes forward deliberately.
