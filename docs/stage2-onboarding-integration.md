# Stage 2 onboarding integration

Based on develop `614de8d68d26ffb35261e3084b8733b6bb6e0366`.

## Delivered

`/plan` remains the actual responsive app, with its landing-page introduction and
numbered navigation replaced by accessible percentage progress. Back, review
edits, owner-scoped drafts, errors and focus movement remain supported.

Place comparisons are optional disclosure content. The comparison profile stays
hidden; preference blending and API payloads are unchanged. Native interest sliders
support touch, pointer and arrow keys; their amounts remain relative weights.

Car collection is removed from onboarding. New drafts skip car input; older
unanswered drafts migrate without losing other answers. Existing provided car
values survive. Coordinate car editing with the trip-settings worker: this patch
does not implement that editor.

The early estimate displays returned route geometry and matched addresses, with
editable start/destination text fields above it. Endpoint changes abort and clear
the old estimate. Ambiguous provider results require explicit selection. Existing
service validation rejects unusable geometry and preserves drafts on failure.

Spacing, depth and transitions use existing tokens. Reduced-motion users receive
no entering/press animation. Natural document scrolling remains available for
expanded details, large text and short screens.

## Remaining integration and acceptance

- Driving time excludes stops, visits and meals. It cannot establish a complete
  candidate under 12 hours. The structured API has no explicit one-day/skip-hotels
  contract. Complete-candidate evidence and an explicit one-day choice require
  coordinated planning work before hiding hotel inputs or skipping hotels.
- Extraction from one free-text trip description is not added. Existing explicit
  start/destination text fields and confirmed provider matches remain authoritative.
- The requested Apple design skill was absent from local files and available skill
  catalogs. This patch uses repository tokens and does not claim skill review.
- Local fixture browser acceptance is recorded below. `/plan` is the real app
  in DevTools device mode; a separate mobile-only URL is not added.
- No production, database or live Mentro calls were made. Release remains with the
  parent, after integration, review and complete-trip acceptance.

## Follow-up acceptance and branch coordination

The local browser harness is `tests/ui-stage2/browser-check.mjs`. Run Vite on
5187 with `VITE_BACKEND_SERVER=http://127.0.0.1:18999/` and
`VITE_LOCAL_JOURNEY=true`; install playwright-core and @axe-core/playwright under
`/tmp/roadtrips-ui-browser` and provide Chromium. Every non-local request is
intercepted or blocked. This verifies UI fixtures, not real trip feasibility.

All five stages are checked at 390×844, 320×568, 1365×900 and 390×844 with 200%
root text. The harness checks horizontal overflow, axe WCAG A/AA issues, reachable
actions, reduced motion, browser errors and preservation of provided car data.
Normal screens keep actions visible with an internally scrolling question panel;
short screens and enlarged text use natural document scrolling.

Inspected meal branch `cb8600a`: its documented `Route.duration` excludes visits,
meals and overnight rest. Room occupancy and the verified hotel provider remain
required even without overnight stops. Therefore no safe client-only one-day
switch exists. Server work must carry an explicit selected trip mode, compute the
complete candidate from aware timestamps with meals, waits, visits, final road
legs and local cutoffs, reject infeasible one-day candidates, and condition hotel
provider/occupancy requirements on that explicit mode. No such contract was
silently added to the concurrently edited scheduler.

That branch also introduces `AmountControl` in TripSetup, overlapping this PR's
native sliders. During integration prefer the shared accessible AmountControl
while retaining this PR's optional comparisons and compact layout. Do not merge
the old car question back into onboarding or drop existing provided car fields.
At inspection, available remote settings snapshots had no new car editor; the
parent must supply the settings worker branch for end-to-end editing acceptance.

November 6 follow-up: all 20 browser stage/viewport combinations passed with zero
axe violations, zero horizontal overflow and zero browser exceptions. All ten
ordinary desktop/mobile stages fit the viewport without document scrolling.
See `docs/evidence/stage2-onboarding/browser-report.json` and adjacent screenshots.
This is isolated fixture acceptance, not live-provider or database acceptance.
