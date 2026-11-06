# Stage 2 settings and reusable preferences

Task branch: `feat/stage2-settings-profiles`, based on develop `614de8d`.

Settings replaces trip-planning redirects with browser light/dark appearance and
account-scoped reusable profiles. Research workspace links retain the existing
server-verified owner capability. No inferred account persona is fetched, edited,
or exposed. Profiles contain the final traveler-reviewed interest vector, daily
scheduling policy and optional car. Profile edit/delete does not change saved trips.

The setup picker explicitly loads a profile into the current draft, preserving
addresses, departure date/time, stop count, traveler/room inputs and budget. The
interest vector becomes editable manual weights with no second comparison blend.
On successful trip persistence, each distinct preference set is saved; identical
sets are reused. A stable UUID makes save retries idempotent. Profile-save failure
does not fail trip persistence and has its own retry action. Existing version-1
drafts and old trip records remain readable. Trip-specific car controls remain in
the setup flow and the car remains in the trip snapshot.

## API and storage

- `GET /preference-profiles`
- `PUT /preference-profiles/{uuid}` with `{ name, choices }`
- `DELETE /preference-profiles/{uuid}`

All routes derive the subject using existing verified Cognito authentication,
return `Cache-Control: no-store`, and use bound SQL parameters. Every storage
operation scopes to `user_id`, `chat_id=''`, `mem_type='preference_profile'` and
UUID `mem_key`. PUT is an idempotent upsert; DELETE is idempotent. A transaction
advisory lock serializes account writes and limits collections to 100 profiles.
Payloads forbid unrelated fields and validate complete canonical finite interest
weights, car consistency and the existing authoritative scheduling model.

Storage reuses the existing `chat_memory` JSONB table and pool with a new row kind.
There is no schema migration, runtime DDL or production write in this task.
The integration follow-up used read-only PostgreSQL system-catalog metadata on
project `misty-mouse-24917066`, branch `br-noisy-forest-aqidrq92`, database
`neondb` (November 6, 2026). `chat_memory` has the expected text/JSONB columns,
composite primary key `(user_id, chat_id, mem_type, mem_key)`, `confidence=1.0`
and `updated_at=now()` defaults, no discriminator CHECK, no user triggers and no
row policies. Thus `preference_profile` needs no schema change. `chats` also has
the expected `(user_id,chat_id)` primary key and JSONB columns. No user rows were
queried. Application subject scoping remains authoritative for isolation. Profile storage stays separate from `fact`, `trip`
and `summary` rows, so inferred account memory and existing trips are untouched.

Frontend `protectedRequest` allows bounded verifier-rejection retries for these
routes. Profile calls have 15-second timeouts. Session guards prevent late profile
results or a lookup-to-save account change from publishing another account's data.
Theme stores only light/dark on this browser; profiles never use localStorage.

## Integration ownership

Onboarding work may overlap `TripSetup.jsx`, `TripSetupPage.jsx` and their tests.
Keep the `PreferenceProfilePicker` at the beginning of trip setup, the reusable
choice allowlist and save-after-trip hook. Other files are dedicated settings,
profile API/client tests and theme tokens. The trip-page worker owns saved-trip
cards/deletion, maps and itinerary editing; this branch does not alter those.

Deploy backend before frontend so the profile API is available. Frontend deployment
is separate from the EC2 API deployment. Missing profile service is recoverable:
users can still enter new trip choices and save trips. No live Mentro or provider calls, production mutations, prior denied Neon test
retries, or deployment were performed. Only authorized read-only production
metadata was inspected during the integration follow-up.

## Offline verification

Frontend format/lint/build pass; final full frontend coverage suite: 54 files,
411 tests passed, 92.34% lines/statements, 87.86% branches, 87.63% functions.
The focused profile/backend contract suite passes 12 tests. Full backend
format/lint pass. The first backend coverage run identified 14 catalog PDF test
failures because this cloud environment lacked the already pinned
`pypdf==6.10.0`; installed that exact requirement and reran the full suite.
The final backend suite passes 2,511 tests with 147 skipped, one warning and
80.94% coverage (required threshold 63%). The final generated-name and retry
changes also pass the focused 22 frontend tests and the production build.

These are offline unit/fixture results, not production two-account acceptance,
real-database validation, responsive screenshot approval or live trip acceptance.

## Post-creation trip car settings

Settings now provides a trip selector and car editor after creation. It reads
structured `tripProfile.car` and legacy `carDetails`; explicit skip takes priority.
`PUT /chats/{chat_id}/car` validates the car server-side and updates only
`carDetails`, `tripProfile.car`, `tripProfile.car_status` and clears `carBudget`.
The SQL statement preserves all other trip fields, route geometry references,
itinerary, visit state and chat log. Owner and expected `agentChatId` are part of
the atomic update predicate; stale/deleted/replaced trips return 404. This editor
does not invoke a model, car provider or route regeneration. Reusable profiles
remain unchanged. Existing route totals are not represented as fuel estimates.

The dedicated disposable PostgreSQL 18.6 test uses the pinned local image and
checked-in schema. All three tests pass: discriminator/profile CRUD round-trip,
same-UUID account isolation, idempotent profile operations, and legacy/structured
trip-car updates with owner/identity rejection and unrelated data preservation.
`tests/settings_postgres_tests.py` never falls back to DATABASE_URL: its explicit
URL gate permits only the known local disposable credentials/hosts. The existing
`tests/postgres/run.mjs` runner now includes it for future CI validation.

Browser fixture harness: `tests/ui-settings/browser-check.mjs`. Run Vite on 5189
with `VITE_BACKEND_SERVER=http://127.0.0.1:18999/` and VITE_LOCAL_JOURNEY=true.
Install playwright-core and @axe-core/playwright under `/tmp/roadtrips-ui-browser`
and use Chromium. All non-local traffic is intercepted or blocked. Eight audits
(390x844, 320x568, 1365x900, 390x844 at 200% root text; each in light/dark) pass
with zero axe WCAG A/AA violations, horizontal overflow or browser exceptions.
The harness verifies legacy car load, edit/reload, theme persistence, profile
creation/deletion and confirms only three expected fixture mutations. Report and
mobile screenshots are in `docs/evidence/stage2-settings/`. This is browser-fixture
acceptance; live Cognito, provider trips and production writes remain untested.
