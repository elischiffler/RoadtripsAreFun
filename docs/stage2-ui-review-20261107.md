# Stage 2 UI review — November 7, 2026

Release, merge and the sharing migration are on hold at the user's request while
the UI changes are completed. This review does not authorize a release or mark
the draft PR ready.

## Scope checked

The review follows the user's requests for concise copy, trip-first entry,
related onboarding questions, percentage progress, a matching login and logo,
shared design variables, reusable preferences, clearer saved trips and a simple
trip page with a map preview and itinerary. `/plan` is the actual responsive app
for desktop and DevTools device mode; it is not a separate landing-page mockup.

Home already sends an authenticated traveler without a saved trip to planning,
and returning owners or connected participants to their corresponding trip
workspace. Signed-out travelers still authenticate before protected planning
services. Login now presents that entry as planning, and keeps the safe return
path through account creation and confirmation. This does not add anonymous
provider access or change account authorization.

Settings, saved-trip deletion and recognizable cards, the main trip page, full
map and itinerary editor are connected in the existing candidate. The review
found that saved preference summaries still displayed legacy daytime clocks for
modern overnight schedules. They now display the actual driving and sleep
windows, including a next-day label, while preserving legacy summaries.

The native design components already use `frontend/src/design/tokens.css` as
their master. The older Material theme retained amber actions and different
typography. Its bounded concrete-value adapter now matches the master in both
themes, including actions, surfaces, system fonts, radii and touch targets.
Parity and contrast checks cover this adapter. Material's existing 8px numeric
spacing unit is preserved; it corresponds to the master's second spacing token.

Onboarding keeps five groups. Route inspection, saved preference selection,
place comparisons and interest amounts open within the current group instead of
stacking more content below it. Return actions restore focus. Attraction count
is grouped with travelers, with matching validation and review editing. The
comparison choices and exact preference values remain unchanged.

Setup progress follows completed input groups at 0, 25, 35, 38 and 40 percent.
The existing server milestones then move through checked roads, stops and
scheduling. Completion still requires the route, itinerary and durable save;
the progress bar is not a time estimate.

## Acceptance boundaries

The baseline browser review found substantial nested scrolling after a route
preview was prepared, despite the earlier checks showing no horizontal overflow.
At 390×844, the first question area measured about 121px with about 640px of
content. Ordinary no-scroll acceptance must therefore measure both the document
and question containers, with a prepared route, rather than only checking that
navigation buttons can be reached.

Short viewports and enlarged text retain accessible scrolling. Expanded content,
errors and provider location disambiguation must remain reachable; fitting a
screen must not rely on clipping content or shrinking touch targets.

The final strict presentation run passed 46 main, optional-panel and preference
screens at 375×812, 390×844 and 1440×900, plus the intentional 320×568 and 200%
text fallback cases. It enforced ordinary no-scroll assertions and did not use
baseline mode. Three ambiguous-location cases passed with explicit coordinate
selection and preserved answers. Twelve auth and four Material dialog/theme
screens also passed. These intercepted browser checks recorded no browser
exceptions or external requests. Representative screenshots, reports and the
exact-content comparison are in `docs/evidence/stage2-ui-review-20261107/`.

All local provider and identity fixtures remain synthetic. Browser and unit
checks do not establish live Cognito, Mapbox rendering, hotel availability or
Mentro behavior. The separate single approved live verification remains unused
here and is not permission for unrelated live calls.

Reusable browser checks are documented in `tests/ui-stage2/README.md`. Their
diagnostic baseline mode explicitly reports `passed: false`; it is not accepted
as ordinary no-scroll verification. The signed trip-creation journey remains
the separate required release gate.
