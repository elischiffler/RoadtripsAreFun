# Route-pin brand

The selected second concept is a forest-teal map pin with a winding pale road on
a sage tile. `frontend/public/favicon.svg` is the editable vector source, used
directly by the shared home control in the header and login/signup pages. Its
filled geometry stays legible at favicon sizes without tiny lane markings,
external images, gradients, or SVG IDs.

The mark uses forest teal `#165B50`, sage `#D6EAE2`, and pale mint `#E6F3EC`.
The control preserves a minimum 44px target, a visible keyboard-focus ring,
Enter/Space activation, and a single accessible home label. The image is
decorative within that named control. The mark is static, including on hover;
reduced-motion preferences also disable the border-color transition.

## App and browser icons

`frontend/index.html` connects the vector favicon, 180px Apple touch icon and
`site.webmanifest`. The manifest supplies 192px/512px PNGs and a separate 512px
maskable icon. Apple and maskable artwork have opaque full-bleed backgrounds;
the maskable pin is inset inside the central 80% safe circle. Normal icons keep
the rounded sage tile. The manifest supplies home-screen branding, not offline
caching or a service worker.

After editing the source SVG, regenerate all raster assets from the repository
root with Node 24 and Inkscape installed:

```sh
node scripts/generate-brand-icons.mjs
```

The script reads only the checked-in SVG and writes the four icon PNGs. It does
not make network, provider or AI requests. Run the frontend format, lint,
coverage and build gates. `LogoButton.test.jsx` covers naming, repeated clicks
and keyboard navigation; `brandAssets.test.js` checks asset wiring, PNG sizes,
static SVG geometry and control accessibility rules.

## Verification on the original logo commit

- Frontend formatting, lint, coverage and production build passed on Node 24.
- 55 test files / 409 tests passed; line coverage is 92.09% (thresholds unchanged).
- Rendered and visually inspected the SVG at 16, 20, 24, 32, 40 and 64px.
- Confirmed Apple/maskable PNGs are fully opaque. The maskable mark's farthest
  painted pixel is approximately 172px from center, inside the 204.8px safe radius.
- Real-browser layout acceptance remains unverified: the cloud browser could
  not reach the local Vite preview. No authenticated trip, live provider request,
  backend change, production deployment or remote publication was performed.

## Stage 2 integration, November 7, 2026

The selected artwork was recovered from `RoadtripsAreFun-route-pin-logo-547a640.zip`
(SHA256 `ed3a5b5b9c6ccfaf07e799efd26425cb4cbaa52549ce96143f5a686c3ed8d11d`).
All internal checksums and the Git bundle verified. Commit
`547a640c59956afbf39a68a8734b2aeb77631668` was imported once from the bundle;
the alternative mail patch was not applied. The chosen SVG and PNGs are unchanged.

`BrandLogo` composes this same SVG with an optional responsive wordmark, and
`LogoButton` keeps one accessible home label. The header and shared `AuthLayout`
use it. Login/signup surfaces, fields, focus states and password requirements
consume the existing master tokens and both themes. Auth handlers, return-path
validation and the two-phase sign-up contract remain intact. Password visibility
controls have explicit names and do not submit the form.

Integrated frontend format, lint, coverage and build checks pass: 63 files,
478 tests, 92.48% line coverage, with thresholds unchanged. Local browser checks
cover light/dark login, signup and header layouts at 320, 390 and 1440px, loaded
artwork, at least 44px home controls, keyboard home access and password toggling.
Auth layouts also pass at 200% text size without horizontal overflow. Browser
requests were restricted to the local fixture frontend; no account was created,
no provider/API/AI request was made, and no production deployment was performed.
