# Trip Planning Studio access

`/studio` is available without account login. `/algorithm` redirects to it.
The password is `cp-sat`, compared case-insensitively on the backend, never
checked in frontend code. The algorithm gear menu is removed.

`POST /studio/access` accepts `{ "password": "cp-sat" }` and returns a signed
session token with an eight-hour expiry. Presets, live runs, run history and saved
map/itinerary results require `X-Studio-Session`. Every unlock creates a random
`studio:<uuid>` experiment identity. Queries retain their existing owner scope;
this does not expose Cognito account history or other visitors' records.
The token cannot authenticate private chat or the original owner-only Lab API.

The browser keeps the session in sessionStorage for that tab, including reload.
Expiry or server rejection restores the password form and aborts pending display
updates. Closing the tab or unlocking a new session creates a fresh history;
old records remain stored but are not automatically shared with the next session.
All runs continue through the existing validated live provider planner.

For deployment, configure backend-only `STUDIO_SESSION_SECRET` with at least 32
random characters, consistently across workers and restarts. Never use a VITE
variable for it. With no configured secret the local server generates a random
process key, so restart requires entering the password again. No database
migration, Cognito change, or deployment is performed by this change.

Verification covers case variants, wrong passwords, missing/invalid/expired
sessions, visitor history isolation, private API rejection, and live planner
handoff. Existing private owner API tests remain applicable.

## October 5 local validation

Implementation: `21e708d` on `codex/production-release`, included in draft PR #34.
Frontend format/lint, 287 tests (89.91% line coverage), and build passed. Backend
Ruff format/lint and 695 tests passed (86.94% coverage, unchanged 63% gate).
The existing Vite large-bundle warning remains. No dependencies changed; the
locked dependency installations already completed for this release were reused.

Rebuilt preview containers passed both smoke checks. Disposable PostgreSQL
project `roadtrips-crud-c3a15f779e` passed CRUD, ownership, saved-result storage,
connection recovery, recreation and backup/restore; containers stopped and both
volumes plus the private backup were retained.

Browser checks rejected `wrong`, accepted mixed-case `CP-SaT` and `cP-sAt`,
and reached Studio from a fresh visitor tab. A real coastal-nature visitor run
completed in 60.74 seconds with 21 API attempts, 2/2 attractions, and a saved
118-mile route. The saved map and dated itinerary opened from its own history.
This is one actual live acceptance run through the new visitor boundary; the
nine earlier owner preset runs remain separate evidence. No production release
or main merge occurred.
