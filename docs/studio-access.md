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
