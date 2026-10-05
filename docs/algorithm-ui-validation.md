# Algorithm Lab UI validation

October 5, 2026 (America/Los_Angeles). UI changes are based on `e0be624`
and are isolated on `codex/algorithm-lab-ui-redesign`. The UI was initially reviewed against
`codex/lab-live-presets-results`. PR #33 is being retargeted to
`codex/cp-sat-solver` to integrate its prerequisites and UI into feature PR #26.

## Presentation

- The workspace is capped at 1400px with a 380px input column, stacking below
  980px. Optional interests, occupancy, car and scheduling controls start closed
  and show summaries. Invalid fields open their containing section before native
  browser validation focuses them.
- Presets remain complete form replacements with an explicit run action. Edited
  inputs show Modified; reset or selecting another preset clears the marker.
- Results show four trip measurements and accessible Route, Itinerary and
  Algorithm details tabs. Warnings, failures, incomplete itinerary and save
  notices remain outside the tabs. Diagnostics and all existing explanations
  remain available in Algorithm details.
- The shared map mounts only in the active Route panel and is recreated for a
  new snapshot. Saved trips use the same compact route presentation. Native
  dialogs close before unmounting so keyboard focus returns to their triggers.
- History starts closed, retains the existing pagination and inspection tools,
  and refreshes after a run. Viewing history or saved results preserves inputs.
- No backend, database, API, dependency or shared routing contract was changed.

## Passed checks

- Node 24: `npm ci`, `npm run format:check`, `npm run lint`,
  `npm run test:coverage`, and `npm run build`.
- 288 frontend tests across 34 files passed; coverage thresholds remain unchanged.
  Existing build chunk-size warnings remain.
- Chromium browser verification used the Vite development server, fixture
  identity tokens, intercepted API responses, and `VITE_LOCAL_JOURNEY=true` for
  the existing deterministic SVG map path. No live provider requests were made.
- Desktop 1440px, tablet 900px and phone 390px widths had no horizontal page
  overflow. Map dimensions were 420×280, 420×280 and 324×220 respectively. The
  preset dialog had three, two and one columns respectively, with nine cards.
- Verified long place names, 30 candidate diagnostics, tab Arrow/Home/End
  navigation, map mounting after switching tabs, and default Route selection.
- Verified preset Escape dismissal and focus restoration, no automatic run,
  modified inputs, closed-section invalid-field focus, history draft preservation,
  saved-trip Escape dismissal/focus restoration, reopening saved maps, reduced
  motion media behavior, and no uncaught browser errors or Vite error overlay.

## Remaining acceptance

Live Cognito owner/non-owner access and a complete live provider trip were not
rerun. These checks remain separate from mocked UI verification; the draft PR
does not establish live Mapbox/provider behavior, deployment, migration status,
or repository required-check enforcement. Backend/container/PostgreSQL checks
were not rerun for this frontend-only diff.

## Clickable stop pins

- The shared map displays numbered pins for every route stop with valid finite
  latitude/longitude coordinates. Numbers match the stop list, including hotels;
  missing or invalid coordinates are skipped without inventing a position.
- Stop coordinates are converted from backend `[lat, lon]` to Mapbox `[lon, lat]`.
  The map fits the road geometry and stops with padding. Clicking or activating
  a pin by keyboard opens one popup with the name, type and available address.
- Popups use text DOM nodes, support Escape, and restore focus. Custom markers
  regain the button role after Mapbox initializes them, and the popup close
  button is exposed to assistive technology. Markers/popups are removed when
  the route changes or the map unmounts. Local SVG maps support equivalent pins.
- Attraction-count fallback recognizes the backend's `stop` type as well as the
  legacy `attraction` type.
- Unit checks cover coordinate conversion, invalid coordinates, ordered numbering,
  safe literal names, one popup, keyboard dismissal and cleanup. Chromium checks
  passed for the local map at desktop/tablet/phone sizes and the real Mapbox GL
  renderer with an intercepted blank style on desktop/phone. No live provider
  or Mapbox API request was made; both browser runs reported no uncaught errors.
