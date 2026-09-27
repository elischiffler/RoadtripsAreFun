# Self-hosted PostgreSQL connection

The live database remains Neon. The target is PostgreSQL on the future cloud Docker
server; no production connection, schema or data has changed in this PR.

The shared operational owner is [hosting-ops](https://github.com/elischiffler/hosting-ops).
Its `postgres/compose.yaml` and `docs/postgres-migration.md` own the database image,
volume, isolated network, credentials, backups and cutover/recovery procedure.
Do not duplicate that stack or migration scripts here.

After source version/extension inventory and a verified restore, attach the backend
container to the external `roadtrips_database` Docker network. Set `DATABASE_URL`
through the runtime secret mechanism to the `roadtrips` database/user on
`postgres:5432`. Set `DATABASE_SSLMODE=disable` only for that private same-host
network. PostgreSQL still requires the application password. Do not publish port
5432 or use plaintext connections over a public/cross-host network.

`DATABASE_SSLMODE` defaults to `require`, preserving current Neon behavior for both
pooled connections and reconnection. Supported explicit values are `require`,
`verify-ca`, `verify-full`, and `disable`. Invalid or opportunistic modes fail at
startup. For cross-host deployments use configured TLS/certificates; prefer
`verify-full` with a trusted root certificate via libpq's `PGSSLROOTCERT`.

The user permits maintenance downtime but requires all data preserved. Freeze all
writers, export and restore the final copy, validate all application tables and
sequences, then test login, trips, chat and memory before reopening writes. After
new writes occur, reverting to Neon needs reconciliation; changing a URL alone
would lose data. Cognito and Mentro stay external dependencies.

## Verification

From `backend/` with Python 3.12 and `requirements.txt` installed:

```sh
pytest tests/database_config_tests.py
pytest --cov=app --cov-report=term-missing --cov-fail-under=63
```

The new tests mock connections and verify TLS defaults, invalid configuration and
reconnect behavior; they do not contact Neon. Full CI retains its existing 63%
coverage requirement. Database container persistence and recovery are tested in
hosting-ops. No production deployment is configured by this connection change.
