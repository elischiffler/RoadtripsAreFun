# Guided trip setup verification

This frontend change adds authenticated /plan, centered grouped setup steps, tab-local owner-scoped drafts, editable review, actual-place interest answers and an explicit backend preference receipt. Home links directly to setup, AI Studio and saved trips. Studio keeps its separate visitor password, presets, cancellation, history, metrics and comparison groups.

## Contract and source scope

Setup sends through the existing authenticated agent/chat/stream message path, stable agentChatId and chat persistence. A plain-language summary is displayed/saved in the chat; canonical weights and tool instructions are carried only in the API message. No new API fields/endpoints or backend behavior were added. The full canonical 14-key vector must be returned in authoritative tripProfile (or a validated trip_profile_updated action), normalize to the chosen shares and have no validation issues before the UI says interests are confirmed. A mismatch/error keeps the draft and offers retry/chat. Address confirmation and server validation remain separate steps. This is a model-mediated existing tool path; local fixtures do not verify real LLM extraction or real account persistence.

Direct interest choices and optional place answers map through a documented reversible points rule. Only user-selected travel-interest reasons affect place-answer adjustments; skip/unsure have no effect. Manual amounts are normalized and must contain a positive value. Graphs show actual draft shares, with no confidence/personality claims. Existing research cohort/version/candidate/evidence filtering is preserved. No new route, hotel-price, method-comparison or availability statistics were fabricated.

The two factual cards reference CC0 Boulder catalog records boulder:284 (Halfway House) and boulder:272 (Realization Point), from backend/tests/fixtures/catalog/boulder-reviewed-12.json. Facts are name, trailhead identity, Flagstaff Road and official visitor URL. Fixture AI vectors, timing, current availability and photos were not copied. Attribution and dated operator evidence appear in the UI. These two examples are a small optional prompt, not a representative preference study.

Integration base is develop **3c38284** (PR52 parking holds), which includes PR50/41/39. PR51 remains separate/open; last observed head **3f8ce0cc9b8477889e9e261d3e7f8d4137ef99b0**. This patch does not edit ItineraryDays.jsx, AlgorithmLab/RouteOverview.jsx, PR51 timing components, backend scheduling, catalog/source data, credentials, security settings or production.

## Local checks

- Node 24.19.0; npm ci succeeded with a writable /workspace/.npm-cache. No dependency or lockfile change.
- frontend npm run format:check and npm run lint passed.
- frontend npm run test:coverage: **43 files, 339 tests passed**. Coverage: **89.10% lines/statements, 84.28% branches, 84.63% functions**, above unchanged gates. The later history-table focusability change also passed its 5 targeted tests.
- frontend npm run build passed. Vite reports the existing large bundle warning; no gate was changed.
- Root node --test tests/dev-runner.test.mjs: **5 passed**.
- Python 3.12 / Ruff 0.16.7: ruff format --check . and ruff check . passed.
- Backend pytest --cov=app --cov-report=term-missing --cov-fail-under=63: **1,880 passed, 128 skipped**, **81% coverage** on the PR52 integration base.
- git diff --check passed.

These local checks cover the final source changes, except where a later targeted check is explicitly stated. Exact pushed-head GitHub CI is a separate gate; consult the PR checks.

## Reproducible nonproduction browser check

The checked-in tests/ui-rework/browser-check.mjs uses Chromium and intercepted local API fixtures only. It never reaches provider services, Cognito verification or a database. Captures include a visible fixture label.

1. Install browser tools outside the application dependency tree:
   npm install --prefix /tmp/roadtrips-ui-browser playwright-core@1.64.1 @axe-core/playwright@4.14.0
2. From frontend start:
   VITE_BACKEND_SERVER=http://127.0.0.1:18084/ npm run dev -- --host 127.0.0.1 --port 5174
3. From repository root:
   ROADTRIPS_UI_EVIDENCE_DIR=/tmp/roadtrips-ui-evidence node tests/ui-rework/browser-check.mjs
   UI_BROWSER_TOOLS_DIR and CHROMIUM_PATH may point to the local tools and Chromium executable.

Observed: home navigation, keyboard focus into setup, focused field-error summary, step editing, reload of draft answers, actual-place rating reasons, normalized API submission, matching and mismatching receipts, fresh chat UUID without overwriting saved chat 7, pending endpoint confirmation in chat, sign-out draft cleanup, protected /plan redirect, independent Studio password gate, preserved live-run/preset/history controls and honest empty history. No route/provider run was requested.

Axe WCAG 2 A/AA and 2.1 AA scans: **zero violations in eight exercised views**: home desktop; initial setup; interests desktop; interests mobile; interests at 320px; review mobile; review with 200% root text size; Studio mobile empty history. Tested no horizontal overflow at 320px and with 200% text on the narrow review, and reduced-motion removes the section animation. This is bounded automated/manual browser evidence, not a claim of comprehensive accessibility certification.

Screenshots: home-desktop.png, setup-desktop.png, interests-desktop.png, interests-mobile.png, review-mobile.png, unconfirmed-mobile.png, studio-mobile.png. Browser report: browser-results.json. All use fixture identities/data, not personal account data.

## Open gates

The disposable PostgreSQL command node tests/postgres/run.mjs first failed because Docker tried writing /home/agent/.docker/buildx on a read-only path. Retrying with a fresh temporary DOCKER_CONFIG passed that tooling prerequisite but failed while building isolated images: pip could not reach the network for pinned annotated-types==0.7.0. No API/database test stack was started and no application assertion failed. Container smoke checks require a running diagnostic stack and remain unverified locally for the same Docker-build limitation. Required CI and independent review must clear applicable gates.

Real Cognito owner separation, live LLM preference acknowledgement, complete provider itinerary, real reload/persistence and production/runtime parity remain unverified. Use an approved nonproduction environment to gather that evidence. No merge or deployment is authorized by this change.

