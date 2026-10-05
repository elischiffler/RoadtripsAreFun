# Algorithm Lab UI validation

October 5, 2026 (America/Los_Angeles). UI changes are based on `e0be624`
and are isolated on `codex/algorithm-lab-ui-redesign`. The PR targets
`codex/lab-live-presets-results` so its diff contains only the UI redesign.

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
- 285 frontend tests across 33 files passed; coverage thresholds remain unchanged.
  Coverage after the implementation: 88.71% lines/statements, 85.28% branches,
  81.20% functions. Existing build chunk-size warnings remain.
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
