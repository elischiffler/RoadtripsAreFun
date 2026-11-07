# Mocked-position browser verification

This is a test-only harness, not an application route. It imports the real
ArrivalAssist, TripVisitProgress, session and revision-aware saved-trip service.
Only browser positions, synthetic identity and the local persistence HTTP reply
are mocked. It does not contact real geolocation, Cognito, providers or a database.
All non-loopback browser requests are rejected; artifacts omit headers/tokens.

Install the existing frontend dependencies and the guided journey's pinned
Playwright dependency, then start the harness from the repository root:

```sh
npm ci --prefix tests/guidedjourney --ignore-scripts --no-audit --no-fund
env -i PATH="$PATH" VITE_BACKEND_SERVER=http://127.0.0.1:5199/api/ \
  VITE_CLIENT_ID=fixture VITE_USERPOOL_ID=fixture VITE_MAPBOX_TOKEN= \
  node frontend/node_modules/vite/bin/vite.js --config tests/arrival-assist/vite.config.mjs
```

In another terminal, run `node tests/arrival-assist/browser.mjs`; set
`CHROMIUM_PATH` if Chromium is not `/usr/bin/chromium`. Stop that test server when
finished. The harness uses fixed synthetic browser time and controlled position
callbacks, so the 45-second dwell is checked without making live requests or
waiting for GPS. It verifies automatic save/Undo with actual client revision
refresh, co-located stop departure/re-entry across actual auto-save rerenders,
denied-location manual fallback, stale rejection without replay and
390px/1440px overflow. `.artifacts/` is ignored. See
[behavior, privacy and assumptions](../../docs/arrival-assist.md).
