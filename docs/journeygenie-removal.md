# JourneyGenie retirement and integration

The dedicated conversational feature is removed on `codex/remove-journeygenie`,
based on current `develop` `aa41b8f10c2bd449a6bd6c17c51bae9dfb92915f`.
This change targets `develop`; it does not merge, deploy, migrate or change main.

Refs inspected through origin and the open PR list on October 16, 2026 (UTC):

| Ref | Verified head |
| --- | --- |
| `main` | `5cd24eb15acae671127679e21aa5ce64afcb2fba` |
| `develop` | `aa41b8f10c2bd449a6bd6c17c51bae9dfb92915f` |
| PR55 `ui-rework` → `develop` | `96b232cb57b30f7c3aec5fed1a53e5abca3879a9` |
| PR51 `codex/arrival-visit-durations` → `develop` | `c3d2ffe6e117526bdcd0726768556ed47663c74b` |

Those were the two open PRs. Neither branch was edited. The user's existing
PC preview and its labeled fixtures were not accessed, restarted or changed.

## Removal inventory

- Removed the `frontend/src/pages/ChatPage/` UI, composer, conversational workflow,
  messages/presentation, location-confirmation controls, chat progress and search.
  Removed the chat navigation button, welcome text and placeholder branding.
- Removed `/agent/chat` and `/agent/chat/stream` and their router, conversational
  loop, dedicated prompt/question/presentation modules, tool dispatcher/context,
  text tool-call parser, location-confirmation orchestration and routing proxy.
- Removed `ROUTING_REMOTE_URL` as an application setting/example, `AGENT_DEBUG`,
  `make debug` and the unused `ldrs` dependency/lock entry. Shared provider
  credentials and backend requirements remain because planning still uses them.
- Removed obsolete API/loop/tool/UI tests, conversational journey/session browser
  fixtures and tool parser probe. Retained shared provider, extraction, profile,
  persona, persistence, progress and planning tests. Mixed suites lost only tests
  of the retired tool/agent paths.
- Deleted dedicated agent design/progress/question/location/token documentation
  and the obsolete location-proposal validation report. Kept shared arrival
  policy in `arrival-timing.md`; updated current documentation and navigation.

`/trips` now lists existing account trips and opens their saved map/itinerary.
Home planning opens Studio; saved-trip navigation and login's default return use
`/trips`. `/chat` redirects there for old bookmarks. No conversation is rendered,
submitted or generated. Guided setup remains a separate integration below.

## Retained compatibility, data and shared dependencies

No database migration or data cleanup is included. No stored chats, user data,
saved trips, routes, itineraries, history or Git history are purged. Existing
owner-scoped `/chats` CRUD, payload names (`ChatData`, `ChatLog`, `chatId`,
`agentChatId`), selected-trip storage keys, message/presentation JSON, table names
and memory CRUD remain compatible. Historical structured presentation is retained
as JSON metadata instead of importing a removed rendering model. The new page
reads records; it exposes no automatic deletion or rewriting.

`services/savedTrips.js` moves the existing persistence helpers out of the deleted
UI directory. `services/routes.js` similarly preserves direct routing helpers.
Existing saved messages remain stored and are not displayed in the new list.
Session logout still clears obsolete browser UUID hints to prevent account leaks.

The `app.agent` package name stays for shared imports. Dependency tracing found
`providers`, `schemas` (LLM messages/tools/usage), `extraction`, `persona`,
`trip_profile`, `trip_dates`, `departure`, `progress`, `progress_stream` and
`provider_diagnostics` needed by planning, shared preference extraction, Studio
or retained memory. These are preserved. PR51's `sources/visit_durations.py`
imports `LLMMessage` and shares the candidate-rating provider; both contracts
remain. No planner, catalog, calendar, opening-hours or duration implementation
is changed by this removal.

The gateway's upstream `/api/chat/stream-full` is a shared completion protocol,
not an application conversation endpoint. The local isolation guard continues
to reject a legacy nonempty `ROUTING_REMOTE_URL`; empty deployment-template
entries are retained rather than altering deployment/security settings. The
SVG map fixture flag remains shared map-test support.

Case-insensitive tracked-source searches cover `journey[ _-]*genie`,
`ChatPage`, dedicated module names and `/agent/chat`. Remaining brand references
are this removal record and links to it. Retired application API paths remain
only in absence-regression tests and this record. Storage/memory names, shared
provider protocol and package names above are intentional compatibility.
Dated evidence/plans in `release-consolidation.md`, `container-validation.md`,
`session-refresh.md`, `product-vision.md`, `senior-demo-*.md`,
`catalog-parking-holds-20261016.md` retain explicitly historical statements and
branch/commit identifiers. Older release/catalog/operations evidence may mention
chat-era journeys; these do not describe an active feature. Catalog source data
contains incidental words such as park unit code `chat`; it is left intact.

## PR55 integration required before release

PR55 currently imports `ChatPage` from `TripSetupPage.jsx`; its `setupMode` calls
`submit('trip_setup', ...)` on `useTripWorkflow.js`, which still sends a natural
language message to `/agent/chat/stream`. It also has a “Continue in chat” action.
A clean textual merge alone cannot produce a working guided setup.

1. Integrate this removal through `develop` under the coordinator's control.
   Keep the conversational files deleted when resolving PR55's delete/modify
   conflicts; do not restore `ChatPage`, its hook, composer or endpoints.
2. Keep PR55's `TripSetup`, `PreferenceProfile`, `setupModel`, `useSetupDraft`,
   styling and home/Studio improvements. Replace `TripSetupPage` with a standalone
   container and a structured planning adapter. Convert confirmed setup values
   directly to existing validated route/itinerary inputs; do not serialize the
   form as a message or restore the removed dispatcher. Retain explicit provider
   location confirmation and backend validation, traveler/room occupancy,
   departures/timezones, persona weights and shared preference extraction.
3. Use `services/routes.js`, `services/savedTrips.js` and current session transport
   where appropriate. Load saved IDs before allocating a new trip, create before
   updates, preserve owner scope, save route/itinerary snapshots, and retain
   existing saved rows. A dedicated preference-extraction endpoint, if needed,
   should use the preserved extraction/provider modules without a conversation.
4. Change “Continue in chat” to results/map/itinerary. Change Home's saved-trip
   link to `/trips`, retain its new `/plan` CTA, and keep `/chat` as a redirect.
   Merge the header's new Plan/AI Studio links with Saved trips, without the
   removed chat-driven logo progress. Allowlist `/plan` and `/trips` for login
   returns and default new planning to `/plan` after its adapter works.
5. Keep PR55's account-scoped setup-draft cleanup when resolving context/session
   conflicts, without restoring composer drafts or chat progress. Rewrite its
   browser fixture and workflow tests to exercise structured planning and confirm
   no conversational endpoint or branding returns. Re-run all required checks,
   saved-trip reload tests and the guided setup → map/itinerary flow.

## Verification

- Python 3.12, requirements installed; Ruff 0.16.7 format/check pass.
- Backend full suite: **1,656 passed, 128 skipped**, **79.23%** coverage (63% gate).
  Skipped suites include disposable integration probes needing their test stack.
- Focused backend shared-AI/auth/profile/planning/retired-endpoint run: **207 pass**.
  Both retired paths return 404 and do not read memory or create providers.
- Node 24 `npm ci`, format check, lint and build pass. **218 tests / 31 files**;
  coverage **92.90% lines/statements, 86.25% functions, 83.44% branches**.
  Thresholds unchanged. Existing Vite large-chunk warning remains.
- Development launcher: **5 pass**.
- Chromium local fixture: saved-trip list without transcript/composer, map and
  itinerary selection/reload, old bookmark redirect, mobile overflow and Studio
  navigation pass. No page errors, conversation calls or writes. Synthetic UI
  tokens/intercepted records/SVG map do not establish live Cognito/provider/DB
  acceptance. Evidence: `docs/evidence/chat-removal-browser.json`.
- **Blocked locally:** Compose image builds and `node tests/postgres/run.mjs`.
  Docker build pip cannot reach the package index (`Errno 101 Network is
  unreachable`, then no matching `annotated-types==0.7.0`). The source schema
  comparison passed before build. No test stack/volumes were created and no DB
  test executed. Smoke checks were attempted and both fail on refused 8002/8082
  connections because containers could not start. CI must clear these gates.
  The PR is draft while required container verification is blocked.

Browser reproduction uses a separate Vite process, never an existing preview:
install Playwright outside the repo, then run
`PLAYWRIGHT_MODULE=file:///tmp/roadtrips-removal-browser/node_modules/playwright/index.mjs node tests/ui-removal/browser-check.mjs`.
It expects Vite at `127.0.0.1:5179` with `VITE_BACKEND_SERVER=http://127.0.0.1:18999/`,
`VITE_COGNITO_ENDPOINT=http://127.0.0.1:18999`, `VITE_LOCAL_JOURNEY=true` and fixture
pool/client IDs. All API requests are intercepted; no server runs on 18999.
