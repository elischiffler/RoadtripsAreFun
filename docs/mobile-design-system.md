# Mobile design foundations

The opt-in library in `frontend/src/design/` supplies reusable parts for a calm,
centered trip experience. It follows the user's Apple design skill: system fonts,
immediate press feedback, clear grouping, rounded surfaces and inclusive settings.
The design references are Apple Maps for layered controls and Airbnb for a readable
day-by-day timeline. These are design directions, not copied assets.

## Master design file and supporting files

[`tokens.css`](../frontend/src/design/tokens.css) is the source of truth for visual
values. Variables live on `.rt-design`, so importing the library does not change
legacy pages. Change a token once to update every adopting component.

| Token family                                                                                          | Purpose                                                                                  |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `--rt-space-*`                                                                                        | A 4px-based rem spacing scale: 4, 8, 12, 16, 20, 24, 32, 40, 48 at the default root size |
| `--rt-radius-*`                                                                                       | Small details, controls, sheets and pills                                                |
| `--rt-target-min`, `--rt-control-height`                                                              | At least 44px hit targets, comfortable 52px inputs                                       |
| `--rt-slider-thumb-size`, `--rt-opacity-disabled`                                                     | Slider thumb appearance and shared disabled opacity                                      |
| `--rt-content-width`, `--rt-page-padding`                                                             | Centered 30rem column with fluid outer gutters                                           |
| `--rt-trip-content-width`, `--rt-map-content-width`, `--rt-map-*-height`, `--rt-map-header-clearance` | Workspace widths, shared map previews and full-map sizing                                |
| `--rt-checkbox-size`                                                                                  | Checkbox visuals; labels retain 44px minimum hit targets                                 |
| `--rt-text-*`, `--rt-weight-*`, `--rt-leading-*`, `--rt-tracking-*`                                   | System type hierarchy; tighter titles and comfortable body copy                          |
| `--rt-color-*`                                                                                        | Semantic page/surface/text/selection/error/focus and route colors                        |
| `--rt-shadow-*`, `--rt-material-*`                                                                    | Quiet surface depth and optional floating material                                       |
| `--rt-duration-*`, `--rt-ease`, `--rt-press-scale`                                                    | Immediate, restrained control feedback                                                   |

[`layout.css`](../frontend/src/design/layout.css) owns frame, sheet, grouped questions
and type classes. [`controls.css`](../frontend/src/design/controls.css) owns inputs,
actions and choices. [`patterns.css`](../frontend/src/design/patterns.css) owns stage
progress and timelines. [`index.js`](../frontend/src/design/index.js) imports all
supporting CSS and exports the public React API. Use that entry point rather than
importing individual files so styles arrive with components.

[`materialPalette.js`](../frontend/src/design/materialPalette.js) is the focused
bridge for the legacy Material UI 5 theme. Material's color calculations need
concrete color values, so the adapter names and reuses its existing dark palette
instead of passing scoped CSS variables into those calculations. Native controls
continue to use the CSS master. Keep matching semantic colors aligned when changing
the palette; do not introduce separate literals in individual Material overrides.

Structural values such as `0`, `100%`, `auto`, grid fractions, local timeline
stacking, and system colors in forced-color mode are intentionally not visual
tokens. Safe-area environment values follow the device. Do not add ad hoc spacing,
font, radius or color values in adopting pages; extend the master file deliberately.

## Public components

| Component        | API and responsibility                                                                                                                                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DesignFrame`    | `children`, optional `className`, native div props. Required boundary; contains the narrow centered column. Does not create another main landmark.                                                                    |
| `Sheet`          | `children`, optional `floating`, `className`, section props. Nonmodal document-flow surface; name it with `aria-label` or `aria-labelledby`.                                                                          |
| `QuestionGroup`  | Required `legend`, optional `description`, `children`, native fieldset props. Groups related questions; preserves external `aria-describedby`.                                                                        |
| `Field`          | Required `label`; optional `id`, `hint`, `error`, `className`; native input props. Automatically associates labels, hints and errors. Value/validation remain with the caller.                                        |
| `AmountControl`  | Required `label`, finite non-negative `value`, `onChange(number)`; optional `id`, `initialMax`, `disabled`, `describedBy`. Native continuous range and explicit − / + tap actions; preserves raw caller values.       |
| `ActionButton`   | `variant` (`primary` or `secondary`), `type` (defaults to `button`), native button props and children. Set `type="submit"` explicitly inside forms.                                                                   |
| `ChoiceGroup`    | Required `legend`, `options`, `onChange(value)`; optional `value`, `description`, `name`, `disabled`. Options have `value`, `label`, optional `description` and `disabled`. Native radio behavior, one selection.     |
| `StageProgress`  | Required `stages: [{id,label}]`; optional `currentId`, `completedIds`. Reports actual completed stage count; deduplicates and ignores unknown IDs. Caller owns validation/completion.                                 |
| `TripViewSwitch` | Required `value` (`map` or `itinerary`) and `onChange(value)`; optional `name`. Radio view preference, not ARIA tabs. Caller renders the chosen panel.                                                                |
| `TripTimeline`   | Required `label` and `items`. Items have `id`, `title`, `time`, optional `dateTime`, `description`, `status` (`upcoming`, `current`, `complete`). Current step and status text convey state without relying on color. |

[`DesignSystemExample.jsx`](../frontend/src/design/DesignSystemExample.jsx) is a
standalone local composition using representative public primitives. Mount its default export
in a temporary Vite entry for visual review or import it into a development harness.
It has no route, account, map provider, backend, storage or network dependencies.
Its save action changes local preview state only and its itinerary is sample data.

`AmountControl` removes the need to type an interest amount. Drag the native slider,
use its arrow/Home/End keys, or tap the labeled − / + actions. All three controls
have at least 44px hit targets and visible focus. Tap actions announce the updated
amount through a polite status; slider feedback uses native assistive-technology
behavior without repeated live announcements during dragging.

Amounts are relative weights, not percentages. `initialMax` is a soft display
range, not a stored-value cap: larger restored or explicitly increased values
expand it, and the range stays stable during a drag. The tap increment scales with
the range magnitude. Rendering does not round, normalize or write caller state;
the compact visual label is rounded for readability while the slider's accessible
value retains the exact amount. In the trip setup flow, the first manual action
seeds untouched amounts at full precision from the stated profile; subsequent
actions change only the chosen interest. Existing normalization and the internal
50/50 comparison blend stay in the setup model. All-zero profiles still fail its
existing validation.

## Integration contract

1. Import primitives from `src/design` and wrap only the adopting page region in
   `DesignFrame`. Existing `Theme.jsx`, `GlobalStyles.jsx`, routes and page CSS are
   unchanged. Bootstrap/MUI remain installed; scoped native element styling avoids
   changing their global theme.
2. Use `rt-stack`, `rt-display`, `rt-title`, `rt-copy`, and `rt-caption` inside that
   boundary for shared spacing and type. Prefer these primitives to mixing raw MUI
   `sx` values with tokenized native controls. MUI components do not automatically
   inherit all tokens; explicitly map their supported props when adopting them.
3. Keep validated trip state, endpoint confirmation, errors and submission in the
   existing flow/model. Feed these components confirmed state; they do not infer
   destinations, calculate personality, merge profiles or make planner requests.
4. Keep the page's existing main landmark and provide a visible heading. On stage
   changes move focus to the new heading and announce validation errors in the
   connected flow. `Field` associates an error but deliberately does not announce
   every keystroke. Persist drafts only through the existing draft owner.
5. Use one opaque sheet for text over a busy map. The `floating` material is optional
   for a separate control surface; avoid stacking translucent layers. `Sheet` is
   not a dialog and has no scrim, focus trap, snap points or pretend drag handle.
   Use an accessible dialog primitive if a later design needs a modal task.

## Four grouped onboarding stages

| Stage                | Related questions                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Route and dates      | Start, destination, confirmed locations, departure date/time; show a duration estimate only when calculated from valid routing data. |
| Travelers and budget | People, rooms and room occupancy, nightly budget and optional car. Reveal room details beside the room choice.                       |
| Your travel style    | A small number of place comparisons, pace and interests; optional short context input where free text adds meaning.                  |
| Review               | A compact route/date/traveler/budget summary with edit actions, then the actual planning request.                                    |

This grouping is integration guidance, not a replacement for backend required-field
validation or a new flow implementation. A stage may reveal related follow-ups
without navigating away. `StageProgress` counts verified completed stages. If
planning needs an early, fast perceived response, show received details and real
phase updates immediately rather than inventing 70% completion.

For the trip experience, group timeline items by local day with readable times,
travel intervals and plain-language state. Let a map selection open one place sheet;
carry the selected stop ID between map and itinerary and return focus to its trigger
when details close. Keep the map viewport separate from narrow question content,
and keep controls within thumb reach. None of these primitives calculate travel
or stop times, implement map rendering, or mark visits automatically.

## Accessibility and acceptance

Native labels/fieldsets/radios/buttons preserve keyboard behavior. CSS supplies
visible focus, 44px minimum targets, wrapping text, flexible layout, safe-area bottom
padding, reduced-motion feedback, solid materials for reduced transparency or more
contrast, and a selected outline in forced-color mode. Controls use a 1rem font to
avoid small-text input zoom at the default iOS setting.

The focused `designSystem.test.jsx` suite checks associations, native keyboard
selection, disabled actions, real progress semantics, textual timeline states, view
selection and the local composition. Run it with
`npm test -- src/tests/designSystem.test.jsx` from `frontend/`. Required integration
checks remain `npm run format:check`, `npm run lint`, `npm run test:coverage`, and
`npm run build`; preserve all repository thresholds.

Real iPhone/Safari, assistive-technology, map-content contrast, device safe areas,
large text and final product visuals still need acceptance in the adopting flow.
The library does not add gesture physics, dark mode, new dependencies, backend
changes, database operations, deployment or live Mentro requests.

## Verified in the cloud checkout, November 6, 2026

Node 24.19.0; starting develop ref
`04a9ecee951f3232b9f026ef7f43aa6b2067fe47`.

- Locked dependencies installed with `npm ci --ignore-scripts --no-audit --no-fund
--cache /tmp/roadtrips-npm-cache`. The initial default-cache attempt failed because
  the default cache was outside writable roots; the writable-cache install passed.
- Full frontend `format:check`, `lint`, `test:coverage`, and `build` passed.
  Coverage ran with `VITE_BACKEND_SERVER=http://127.0.0.1:9/`; 42 files / 301 tests
  passed. Total coverage: 92.82% statements/lines, 87.25% branches, 88.26% functions.
  Design code: 99.1% statements/lines, 97.91% branches, 92.85% functions.
- Vite compiled the standalone example in a temporary local harness with the
  existing Bootstrap stylesheet, MUI theme/CssBaseline and GlobalStyles loaded.
  Chromium checks passed at 320px, 390px and 1440px, with no horizontal overflow;
  the desktop inner column measured 480px. Controls measured at least 44px high.
  At 320px with 200% root text, the document still fit the viewport.
- Native arrow-key radio selection, map/itinerary panel switching, text entry and
  preview action feedback passed in Chromium. Reduced motion removed the button
  transition; more-contrast media used the stronger border setting. The harness
  allowed only local preview requests; no outbound requests or browser errors
  occurred. A phone screenshot was visually inspected.
- Build retains an existing large-bundle advisory. No production app entry imports
  this opt-in library yet, so the build is a compatibility check, not evidence that
  the new design is already visible on existing routes.

No backend tests, live provider/Mentro calls, database operations, Neon recovery
retries, migrations or deployment were performed. Real iPhone/Safari and screen
reader acceptance, live map styling and adoption into the separate guided-flow
prototype remain integration work.

### Progressive planning and daily rhythm

`OnboardingMap` is a source-coordinate route sketch: draft endpoints remain marked unconfirmed until accepted, catalog ideas are unscheduled, and estimated rest regions are explicitly not hotel inventory. Unverified progress geometry stays in the checking phase; only the server's complete candidate proof offers a trip under12hours. `PlaceContext` displays admitted reviewed context and retains mandatory image credit/license links.

`DailyRhythm` uses native continuously tracked hour sliders and the shared44px range target/focus treatment. Its24slots distinguish driving/exploring, rest and sleep. New opt-in requests send only `daily_schedule`; legacy profiles/drafts retain original timing until an explicit adjustment. The sleep interval is a planning constraint, without a health claim. Valid driving windows may cross midnight, and sleep may occur during the day. The editor labels a wrapped endpoint “+1 day” while preserving all 24 slots and the exact source clocks. Meal breaks follow the explicit sleep schedule; displayed meal dates and times come from the server. Actual local-clock conflicts and infeasible schedules remain server-owned errors.

Catalog preparation is an admitted read-only lookup, cached only in memory for60seconds/four owner-and-route keys. Planning and AI begin only after **Check trip options**. Registration is lightweight; an interrupted assessment retries the same registered request and immutable payload only on a user action. Expired/cancelled options require a new explicit check. Hotel occupancy/budget are deferred until **Allow hotel stays**; this option allows hotels when needed and does not force a stay. No partial itinerary is saved or shown as100% complete.

Reusable `LodgingDetails` inside owner `PlaceTiming` keeps server-returned quote calendar dates separate from planned arrival/leaving clocks. Lodging metadata is not added to the public shared-trip projection; shared views retain their existing planned timing only. A two-night quote may cover a daytime rest period on one calendar day; the UI never derives quote dates or prices from that rest interval. Arrival and departure access require confirmation with the property, and no room is booked. Legacy hotel rows without lodging metadata retain their previous display. Meal clocks include actual date/offset context and full accessible timestamps, including after-midnight and DST intervals.
