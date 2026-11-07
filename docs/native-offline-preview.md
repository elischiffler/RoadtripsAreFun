# Native offline Stage 2 preview

Use a clean worktree without any `.env` or `.env.*` files (the checked-in
`.env.example` is fine). This runs the actual Stage 2 frontend, API, solver,
itinerary and local PostgreSQL persistence. **Login, locations, roads, hotels,
attractions and AI responses are synthetic. No live Mentro requests are made.**
This does not show production trips, real map tiles or real provider availability.

Install the normal Node 24/frontend and Python 3.12/backend dependencies described
in the README. A native PostgreSQL installation with `initdb`, `pg_ctl`, `psql`
and `createdb` is also required. On Apple Silicon with Homebrew PostgreSQL 17:

```sh
PG_BIN=/opt/homebrew/opt/postgresql@17/bin node scripts/dev-offline.mjs
```

If those tools are already on PATH, omit `PG_BIN`. Open
<http://localhost:5173/login> and sign in as `traveler@example.test` with password
`fixture-only`. These are public fixture constants, not real account credentials.
Use **Boulder → Fort Morgan** for a short trip or **Boulder → Synthetic overnight
destination** for a long trip. Choose a future departure date. The alternate
fixture identities are `participant@example.test` and `overnight@example.test`,
with the same fixture password. Do not enter real account credentials.

The API is <http://127.0.0.1:8003>; fixture login is on 8998, providers on 9010 and
PostgreSQL on 6544. All listeners bind only to loopback. The normal container gate
and older native gate use different ports and are not changed or stopped. The
launcher refuses occupied ports instead of killing another process. It refuses
root dotenv files and starts child processes with an explicit environment
allowlist. The fixture also rejects hosted database URLs and blocks nonlocal
Python DNS/socket connections. Its read-only `/fixture/report` exposes synthetic
work counters and any blocked network attempts.

Ctrl+C stops the preview processes and its own database. Synthetic saved trips
remain in `.artifacts/native-preview/db` and survive restart. No schema is applied
to another database. If interrupted initialization leaves a partial database, the
launcher fails rather than deleting it; inspect the local log and preserve that
directory before choosing a fresh worktree. Never use this fixture as production
migration or backup evidence. The mandatory container release gate remains
`tests/guidedjourney/run.mjs`; this development preview does not replace it.

The component imports explicitly include `.jsx` where similarly named lowercase
`.js` helper modules exist. This avoids case-insensitive macOS resolution choosing
`placeTiming.js` instead of `PlaceTiming.jsx`, or `dailyRhythm.js` instead of
`DailyRhythm.jsx`.
