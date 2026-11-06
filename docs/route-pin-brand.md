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

## Verification for this change

- Frontend formatting, lint, coverage and production build passed on Node 24.
- 55 test files / 409 tests passed; line coverage is 92.09% (thresholds unchanged).
- Rendered and visually inspected the SVG at 16, 20, 24, 32, 40 and 64px.
- Confirmed Apple/maskable PNGs are fully opaque. The maskable mark's farthest
  painted pixel is approximately 172px from center, inside the 204.8px safe radius.
- Real-browser layout acceptance remains unverified: the cloud browser could
  not reach the local Vite preview. No authenticated trip, live provider request,
  backend change, production deployment or remote publication was performed.
