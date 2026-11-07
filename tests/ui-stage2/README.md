# Intercepted UI acceptance

These checks exercise the actual React screens in Chromium with explicitly
synthetic HTTP replies. They never connect to Cognito, Mentro, maps, a database
or other providers, and they do not replace the signed disposable-PostgreSQL
[trip-creation release gate](../guidedjourney/README.md).

Install the committed frontend dependencies and the committed
`tests/guidedjourney` Playwright dependency, then start the dedicated loopback
server in a separate terminal:

```sh
node tests/ui-stage2/server.mjs
```

This server ignores `.env` files and inherited `VITE_*` variables, uses only
explicit synthetic endpoint configuration, and refuses a busy port 5187. Run:

```sh
node tests/ui-stage2/layout-check.mjs
node tests/ui-stage2/auth-check.mjs
node tests/ui-stage2/material-check.mjs
node tests/ui-stage2/location-check.mjs
```

`CHROMIUM_PATH` defaults to `/usr/bin/chromium`. `UI_BROWSER_TOOLS_DIR` may point
to an installed copy of the committed `tests/guidedjourney` package.
`ROADTRIPS_UI_EVIDENCE_DIR` selects a local screenshot/report directory.
No browser authentication state or bearer token is exported.

The layout check covers all five grouped stages after an actual route estimate
is rendered. Ordinary 375×812, 390×844 and 1440×900 viewports must fit without document or
nested vertical scrolling, keep the primary actions visible, preserve keyboard
focus and honor reduced motion. Short 320×568 and 200% text cases retain readable
questions and reachable actions without horizontal clipping; vertical scrolling
is an accessibility fallback in those cases. `UI_LAYOUT_BASELINE=true` records
overflow for diagnosing an old version; it **disables the ordinary no-scroll
assertions and is not a passing acceptance run**.

The auth check covers phone/desktop, light/dark, contextual trip sign-in,
sign-up mismatch errors, the replacement confirmation screen and invalid code
guidance. Only local intercepted SDK protocol responses are used; no account is
created. The Material check opens and cancels the actual saved-trip delete
dialog, checks recognizable endpoints/dates and verifies rendered MUI primary,
dialog surface and text colors against the shared CSS tokens in both themes.
It rejects every data write.

The separate location check exercises two ambiguous matches for each endpoint
at both ordinary phone sizes and desktop. All choices must fit without scrolling;
the selected coordinates must drive the initial route, and the typed draft/date
must remain intact. Its geocoding and road responses are intercepted fixtures.

These checks do not prove physical-device behavior, live map rendering, actual
provider acceptance, native iOS behavior or manual screen-reader usability.
