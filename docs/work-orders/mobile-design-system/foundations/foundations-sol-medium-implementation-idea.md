# Mobile design foundations

Suggested model: Sol; reasoning: medium.

Own a reusable, opt-in mobile design system in `/workspace/RoadtripsAreFun`. Verified base: develop `04a9ecee951f3232b9f026ef7f43aa6b2067fe47`; current task branch `feat/mobile-design-system-20261106`.

Read repository `AGENTS.md`, `.steering/overview.md` and the Apple design skill (`skill://user/6ad18bf2ebe081919944af4397930bfb/apple-design/SKILL.md`). Existing frontend is React 18/Vite 5 with MUI 5, PropTypes, ESLint/Prettier and Vitest/Testing Library. Current develop has TripSetup pages. Current Theme/GlobalStyles own a legacy earthy theme and must remain compatible.

Create `frontend/src/design/` as a self-contained opt-in library. Use a master CSS variables file with standardized spacing, radii, control sizing, system typography, semantic colors, depth and motion. Supporting files should own layout, accessible controls and trip patterns. Avoid repeating raw design values outside tokens; document exceptions. Expose useful React primitives (e.g. centered phone-ready frame, rounded nonmodal sheet, grouped question fieldset, native labeled field/button/choice, stage progress, timeline and map/itinerary view switch) through a public barrel. Choose a focused set with useful composability over a large generic library. Do not build the other worker's flow, change app entry points/global Theme/routes, or add dependencies. No fake gesture handles or draggable claims. Native keyboard support, 44px minimum targets, readable solid surfaces, reduced-motion/transparency/high-contrast support, and responsive overflow matter. Stage progress reports actual state, not a misleading artificial percentage.

Document tokens, APIs, integration with existing MUI/global CSS, and a four-stage grouping example (route/dates; people/rooms/budget; place comparisons/preferences; review). Describe timeline/map patterns without implementing planner behavior. Provide a small composition/example that imports every public primitive so Vite can verify it on integration; avoid new app routes and network calls.

Write meaningful component tests for semantics, accessible descriptions, native keyboard interaction, selected state, stage completion/current semantics and timeline state. Do not mirror every CSS declaration in tests.

Do not deploy, modify any database, call Mentro AI (including tests), retry the prior denied Neon rollback test, or expand into backend/personality calculations. Preserve app behavior and backend authority. Stop and report newly discovered work outside this scope.

Return changed files and API summary. Run focused tests plus formatting/lint on changed files; coordinator runs full required frontend checks (`npm run format:check`, `npm run lint`, `npm run test:coverage`, `npm run build`). Do not commit or push while coordinator reviews. Finish with clear limitations, especially unperformed device/visual acceptance. Only write design files, tests and `docs/mobile-design-system.md`; work-order files belong to coordinator.
