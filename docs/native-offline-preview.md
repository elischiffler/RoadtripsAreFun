# Native offline Stage 2 preview

Use a clean isolated worktree without `.env` or `.env.*` files (the checked-in
`.env.example` is fine). This runs the actual frontend, API, solver, itinerary and
local PostgreSQL persistence. **Login, locations, roads, hotels, attractions and
AI replies are synthetic.** It does not show production trips, real map tiles or
real provider availability. No live Mentro request is authorized by this command.

Install the Node 24/frontend and Python 3.12/backend dependencies described in the
README. Native PostgreSQL tools `initdb`, `postgres` and `psql` must be available.
For example, with Homebrew PostgreSQL 17 on Apple Silicon:

```sh
PG_BIN=/opt/homebrew/opt/postgresql@17/bin node scripts/dev-offline.mjs
```

If those tools are on PATH, omit `PG_BIN`. Open
<http://127.0.0.1:5173/login> in a fresh browser profile/private window. Sign in as
`traveler@example.test` with password `fixture-only`. These are public fixture
constants, not real account credentials. The alternate fixture identities are
`participant@example.test` and `overnight@example.test`, with the same fixture
password. Do not enter real credentials or copy a production browser session.

Use **Boulder → Fort Morgan** for a short trip or **Boulder → Synthetic overnight
destination** for a long trip, with a future departure date. The fixture data is
small and synthetic; arbitrary real-world destinations are not supported.

## Isolation and lifecycle

The frontend binds 127.0.0.1:5173; the API, fake identity and fake providers bind
127.0.0.1 ports 8003, 8998 and 9010. PostgreSQL binds only 127.0.0.1:6544. All
clients use TCP; native PostgreSQL Unix sockets are disabled so long Mac checkout
paths cannot exceed the socket pathname limit. The mandatory container journey
keeps its original ports and ephemeral signing keys. Its additional launcher
integrity preflight needs the native preview ports free, so stop your own preview
before running that gate locally. Occupied ports are refused, never cleared by
killing another process.

The launcher refuses dotenv files and starts children with a narrow environment
allowlist, without inherited provider credentials or PG selectors. The fixture
rejects nonlocal database targets, query/fragment overrides and wrong synthetic
credentials. Both fixture modes force their fixed local CORS origins instead of
inheriting an ambient origin. Python DNS/socket guards reject nonlocal provider
connections. `/fixture/report` exposes synthetic counters and blocked attempts,
not authorization headers or browser authentication state.

This is an explicit test entry point: `dev-offline.mjs` invokes
`tests/guidedjourney/fixture.py`. The ordinary production `app.main` does not
import or switch to it; these root test fixtures are not copied into the
production image. Normal development commands are unchanged.

Preview state is under `.artifacts/native-preview/`. The owned private directory
and marker, database and signing-key paths must not be symlinks or belong to
another user. The parent may be ordinary owned 0755, but cannot be writable by
other users. An exclusive per-invocation lock prevents concurrent launchers from
claiming the same preview. PostgreSQL runs as a retained foreground child;
cleanup signals that invocation's process group, never an arbitrary postmaster
found by port or data-directory name. Each SQL session checks its server's data
directory before initializing schema.

Ctrl+C stops the preview services and its own database. Synthetic saved trips and
the private fixture signing key persist in the owned state, so an unexpired local
browser session can survive a restart. The normal CI fixture remains ephemeral.
No production refresh-token behavior is added; expired fixture sessions need a
new synthetic sign-in. Do not commit or share the state directory or its key.

If initialization or a crash leaves partial state/a lock, the launcher fails
rather than deleting it or stopping an unverified process. Inspect and preserve
that isolated state, or choose a fresh worktree. No schema migration, native
PostgreSQL upgrade or recovery of production data is performed.

## Verification and limits

The required journey driver runs four cheap Node lifecycle probes and 20 Python
configuration/observer tests before fixture startup. The lifecycle probes use
only temporary fake foreground-process helpers: concurrent-start refusal after
port reservation release, foreign-postmaster survival on failed startup,
writable-parent refusal and long-path/TCP-only arguments. They do not pretend to
be a native PostgreSQL server test. Config tests include stable native signing,
unchanged ephemeral CI signing, hostile CORS, and unsafe state/data/key paths.

Cloud verification on the `5ebb6f6` application baseline plus this fixture change
used the actual native-mode Python fixture, Vite app, Chromium/SDK login, signed
JWT verifier and CRUD with a fresh owned PostgreSQL 18 container. Signed CREATE
and browser reload returned 200. After stopping/restarting the fixture API, the
same browser session reloaded the unchanged route/revision without another login
(the restarted identity's login counter stayed zero). A presentation update
returned 200 and rotated its revision. Provider/road/model/hotel calls were zero,
and browser/Python external-attempt/error lists were empty. API/Vite/Chrome,
container networks and owned test state were removed; all five ports were closed.
A separate real-PostgreSQL probe verified the launcher's exact SQL guard template:
matching data-directory initialization succeeds; a mismatch refuses writes.

Host native PostgreSQL tools were unavailable in that cloud environment. These
checks **do not establish full native Mac PostgreSQL launcher acceptance**. No
container-to-native library shim, live Cognito/Mentro/map service, hosted database
or production state was used. The separate backend tests cover legacy hydration;
this restart smoke used a modern saved route with no initial geometry. The full
mandatory container trip-creation gate on the final integrated revision remains
required and is not replaced by this development preview.

The frontend component imports explicitly include `.jsx` where similarly named
lowercase `.js` helpers exist. This avoids case-insensitive macOS resolution
choosing the helper instead of the component; the separate import portability
lane owns those frontend changes.
