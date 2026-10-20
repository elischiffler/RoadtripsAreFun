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

## Workspace and History popup (October 19, 2026)

History opens a modal with saved runs. **Open trip** restores a saved route into
Studio without calling planning providers. Escape and **Close history** dismiss
it and return focus to the trigger.

The current inputs, selected result tab, result and active job UUID are kept in
sessionStorage, scoped to the exact visitor token and backend. Reloading or
navigating away and back in the same tab restores them. If a large route exceeds
the browser quota, the job reference is retained and the saved result is fetched.
Starting a trip requires storing that reference first.

`POST /studio/jobs` accepts `{id: <UUID>, run: <LabRun>}`. Reconnecting uses the
same UUID; it does not repeat provider work. `GET /studio/jobs/{id}` returns the
latest progress or result. `DELETE /studio/jobs/{id}` explicitly cancels work.
These routes retain signed visitor ownership and private no-store responses.
Leaving Studio only stops polling; the server continues running the trip.

Workers live in one API process, with one active trip per visitor and four total.
Use one API worker for these endpoints; a distributed queue is not implemented.
The latest progress is bounded, and completed in-memory jobs expire after an hour
or beyond 16 retained jobs. Completed results remain available from run storage.
An API restart interrupts active work; reconnect reports the interruption rather
than automatically repeating paid calls. Stable `STUDIO_SESSION_SECRET` remains
necessary to keep visitor tokens valid across API restarts. Tab closure, session
expiry or a new unlock ends access to the previous private workspace.

Browser acceptance used `tests/studio-persistence/fixture.py`, an isolated fake
planner and in-memory storage on port 8004 with a separate Vite server. Reload
and home/Studio navigation during a run produced exactly one execution; completed
results and the selected tab survived reload, and History reopened the saved trip.
No paid providers or production database were used for this check.
