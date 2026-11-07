# Sharing migration: read-only operator handoff

Prepared November 7, 2026, from `c6f8955a382a7b71bd6f59112e23f45e7d668acd`.
This is an inspection procedure, not approval or a command to apply a migration.
No hosted database, migration, grant, backup, restore or deployment was executed
while preparing it. The earlier bounded Neon inspection and its evidence remain
in `/workspace/sharing-migration-preflight-20261107/` in the review workspace.

## What remains unverified

The authenticated Neon MCP inspection used database-owner `neondb_owner`. Its
November 7 observation found compatible `public.chats` columns/primary key and
no sharing-object collisions. That principal is not an observation of the EC2
app's effective SQL role. The ready cloud `DATABASE_URL` is also not EC2 proof.

The fresh managed-runtime capability check still reports current observations,
enforced unrestricted HTTP, no outbound identities or secret bindings, no OIC
manifest, no VPN, and no TCP grants. No authorized SSH/AWS/SSM host-reading tool
is available. The previously observed ops endpoint returned 401; it was not
retried without new authorization evidence. The earlier denied Neon rollback
test was not retried. This is an access/configuration gap, not an approval-review
rejection of the sharing migration.

Resolve the gap by either:

1. Having an already authorized host operator run the bounded inspection below
   and provide its sanitized output plus the existing current recovery receipts.
2. Configuring a legitimate read-only host/ops identity in this task's environment
   settings, then rechecking readiness and using its supported inspection path.

Do not paste credentials into chat, expose protected environment files, reuse a
deployment token as a status credential, or change endpoint protection. No new
restore rehearsal is required by this handoff merely because the DDL is additive.
If existing recovery evidence is missing or stale, report that fact; any remedy
is a separate operator/release-owner decision.

## Attest the actual running backend connection

Use the authorized host shell and identify the **running Roadtrips API container**
through the established host runbook. Do not select a diagnostic/local-preview,
test image, another application, or a cloud workspace connection. Substitute the
actual full container ID below. These commands do not restart the container.

```sh
ROADTRIPS_INSPECT_CONTAINER='<actual-running-Roadtrips-API-container-ID>'
docker inspect --format '{{.Id}} {{.Image}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{.State.Status}}' "$ROADTRIPS_INSPECT_CONTAINER"
```

Keep that ID/image/revision/status with the SQL observation and its UTC timestamp.
Inspect only these fields; do not dump `.Config.Env`, `/proc/*/environ`, container
inspection JSON, the DSN, or host secret files.

The following process runs inside that container with its inherited runtime
configuration and the same `app.crud.chat_crud._get_conn()` factory used by the
app. It does **not** import `app.main`, start FastAPI, invoke lifespan hooks, call
providers, use a separately supplied URL, or select a different SQL role.
At the prepared revision, this module imports settings/models/helpers and lazily
opens a psycopg2 pool; it has no import-time DDL. The factory's initial `SELECT 1`
connectivity check is rolled back before the inspection starts. Verify this
module path/behavior against the actual deployed revision if it differs.

This is a fresh connection through the deployed factory/configuration, not an
attachment to an existing worker's pooled session. The inspected implementation
does not change roles per request. If the deployed implementation does, the
operator must attest that effective-role path instead and disclose the difference.

```sh
docker exec -i -e PYTHONDONTWRITEBYTECODE=1 "$ROADTRIPS_INSPECT_CONTAINER" python - <<'PY'
import json
import logging
import sys

logging.disable(logging.CRITICAL)
conn = None
factory = None
failure = None
try:
    from app.crud import chat_crud as factory
    from psycopg2.extras import RealDictCursor

    conn = factory._get_conn()
    conn.rollback()
    queries = {
        "session": """
            SELECT statement_timestamp() AS observed_at_utc,
                   current_database() AS database, current_user AS effective_role,
                   session_user AS login_role, current_setting('role') AS role_setting,
                   current_setting('server_version') AS server_version,
                   current_setting('transaction_read_only') AS transaction_read_only,
                   inet_server_addr()::text AS server_address,
                   inet_server_port() AS server_port
        """,
        "namespace": """
            SELECT current_schema() AS current_schema,
                   current_schemas(false) AS effective_schemas,
                   current_setting('search_path') AS search_path,
                   to_regclass('chats')::text AS resolved_chats,
                   to_regclass('public.chats')::text AS public_chats,
                   to_regclass('trip_shares')::text AS resolved_trip_shares,
                   to_regclass('trip_share_members')::text AS resolved_members,
                   to_regclass('public.trip_shares')::text AS public_trip_shares,
                   to_regclass('public.trip_share_members')::text AS public_members
        """,
        "named_objects_all_user_schemas": """
            SELECT n.nspname AS schema, c.relname AS name, c.relkind AS kind,
                   pg_get_userbyid(c.relowner) AS owner,
                   c.relrowsecurity AS rls, c.relforcerowsecurity AS forced_rls
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname IN ('chats', 'trip_shares', 'trip_share_members',
                                'trip_share_members_account')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
            ORDER BY n.nspname, c.relname
        """,
        "public_columns": """
            SELECT c.relname AS table_name, a.attnum AS position,
                   a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
                   a.attnotnull AS not_null, d.oid IS NOT NULL AS has_default,
                   coll.collname AS collation, coll.collisdeterministic AS deterministic
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
            LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
            LEFT JOIN pg_catalog.pg_collation coll ON coll.oid = a.attcollation
            WHERE n.nspname='public'
              AND c.relname IN ('chats', 'trip_shares', 'trip_share_members')
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY c.relname, a.attnum
        """,
        "public_constraints": """
            SELECT c.relname AS table_name, k.conname AS name, k.contype AS type,
                   k.convalidated AS validated, k.condeferrable AS deferrable,
                   k.condeferred AS deferred,
                   pg_get_constraintdef(k.oid) AS definition
            FROM pg_catalog.pg_constraint k
            JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public'
              AND c.relname IN ('chats', 'trip_shares', 'trip_share_members')
            ORDER BY c.relname, k.conname
        """,
        "public_indexes": """
            SELECT t.relname AS table_name, x.relname AS index_name,
                   i.indisprimary AS primary, i.indisunique AS unique,
                   i.indisvalid AS valid, i.indisready AS ready,
                   i.indimmediate AS immediate, pg_get_indexdef(x.oid) AS definition
            FROM pg_catalog.pg_index i
            JOIN pg_catalog.pg_class t ON t.oid=i.indrelid
            JOIN pg_catalog.pg_class x ON x.oid=i.indexrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public'
              AND t.relname IN ('chats', 'trip_shares', 'trip_share_members')
            ORDER BY t.relname, x.relname
        """,
        "migration_prerequisite_privileges": """
            SELECT has_database_privilege(current_user,current_database(),'CREATE')
                       AS database_create,
                   has_schema_privilege(current_user,'public','USAGE') AS public_usage,
                   has_schema_privilege(current_user,'public','CREATE') AS public_create,
                   CASE WHEN to_regclass('public.chats') IS NULL THEN NULL ELSE
                     has_table_privilege(current_user,to_regclass('public.chats'),'REFERENCES')
                   END AS chats_references
        """,
        "eight_actual_app_dml_privileges": """
            WITH targets AS (
              SELECT table_name, to_regclass('public.' || table_name) AS relation
              FROM (VALUES ('trip_shares'), ('trip_share_members')) t(table_name)
            )
            SELECT t.table_name, p.privilege, t.relation IS NOT NULL AS exists,
                   CASE WHEN t.relation IS NULL THEN NULL ELSE
                     has_table_privilege(current_user,t.relation,p.privilege)
                   END AS allowed
            FROM targets t
            CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE')) p(privilege)
            ORDER BY t.table_name, p.privilege
        """,
        "default_table_acl_metadata": """
            SELECT pg_get_userbyid(d.defaclrole) AS creating_role,
                   CASE WHEN d.defaclnamespace=0 THEN '(all schemas)'
                        ELSE n.nspname END AS schema, d.defaclacl::text AS acl
            FROM pg_catalog.pg_default_acl d
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid=d.defaclnamespace
            WHERE d.defaclobjtype='r' AND (d.defaclnamespace=0 OR n.nspname='public')
            ORDER BY creating_role, schema
        """,
    }
    output = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First statement in this transaction; no catalog query precedes it.
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        cur.execute("SET LOCAL lock_timeout='1s'")
        for name, sql in queries.items():
            cur.execute(sql)
            output[name] = [dict(row) for row in cur.fetchall()]
    parameters = conn.get_dsn_parameters()
    output["connection_identity"] = {
        key: parameters.get(key) for key in ("host", "port", "dbname", "user", "sslmode")
    }
except Exception as exc:
    # Never echo exception text, connection objects, settings or credentials.
    failure = {"ok": False, "error_type": type(exc).__name__,
               "sqlstate": getattr(exc, "pgcode", None)}
finally:
    if conn is not None:
        try:
            conn.rollback()  # Read-only cleanup, not a migration rehearsal.
            factory._put_conn(conn)
        except Exception as exc:
            failure = {"ok": False, "cleanup_error_type": type(exc).__name__,
                       "sqlstate": getattr(exc, "pgcode", None)}
if failure:
    print(json.dumps(failure))
    sys.exit(1)
print(json.dumps({"ok": True, "inspection": output}, default=str, indent=2))
PY
```

The output contains connection endpoint/db/role identity and system catalogs only.
It never selects customer rows, tokens, trip JSON, account identifiers, query
text/history, environment values or passwords. Preserve it in the approved private
operations evidence location; provide the sanitized JSON and container identity.
An SQL error must remain an unsuccessful observation, not be replaced by guessed
values. A read-only transaction prevents ordinary DDL/DML; its cleanup makes no
schema or permission changes. See [PostgreSQL transaction modes](https://www.postgresql.org/docs/18/sql-set-transaction.html).

## Compare the returned metadata

The last independently inspected control-plane target was project
`misty-mouse-24917066`, branch `br-noisy-forest-aqidrq92`, compute
`ep-silent-firefly-aqma935w`, database `neondb`. Its published endpoint was
`ep-silent-firefly-aqma935w.c-8.us-east-1.aws.neon.tech` (or its `-pooler` variant).
An authorized operator must correlate the observed endpoint to **current** Neon
project/branch/compute metadata; a matching database name or branch name alone is
insufficient. Do not substitute the cloud environment's URL for this observation.

Check `transaction_read_only=on`, actual effective/login roles, current schema and
search path, and unqualified resolution. The migration and app queries are
unqualified: they must resolve to the intended objects in `public`, with no
unexpected earlier namespace. Existing `chats.user_id/chat_id` must be nonnull
text with an eligible validated, nondeferrable composite primary/unique key and
valid immediate supporting index. Review any differently shaped existing sharing
objects; `IF NOT EXISTS` is not validation or repair.

There are eight separate app DML checks: SELECT/INSERT/UPDATE/DELETE on each new
table. If tables are absent, `exists=false` and `allowed=null` is expected: actual
future grants cannot be proven before those objects exist. Do not replace null
with true based on the MCP owner role. Existing schema privileges/default ACL
metadata inform a separate proposed migration principal; they do not prove that
a different application role will own or have DML access to future tables.
Any later authorized application needs post-application checks using that actual
app role. No migration/grant command is included here.

If objects exist, inspect exact columns, constraints/FK targets/cascades, uniqueness,
RLS and index definitions against `backend/sql/trip_sharing.sql`. Privileges alone
do not verify row-security policy behavior. Relevant catalog-function behavior is
documented in [PostgreSQL system information](https://www.postgresql.org/docs/18/functions-info.html)
and [index metadata](https://www.postgresql.org/docs/18/catalog-pg-index.html).

## Provide current recovery evidence without creating anything

The prior MCP observation reported a six-hour configured history retention, no
exact oldest/latest restorable timestamp or LSN, and only an October 5 snapshot.
Those are dated observations, not a fresh November recovery attestation. Do not
infer a valid PITR interval by subtracting the configured retention from now.

The established hosting-ops runbook names these installed units. An authorized
host operator can read their existing state without starting any job:

```sh
systemctl show roadtrips-neon-s3-backup.service roadtrips-neon-s3-freshness.service roadtrips-neon-s3-restore-check.service --property=Id,ActiveState,SubState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
systemctl list-timers --all 'roadtrips-neon-s3-*'
```

A successful unit state alone does not establish backup contents. Inspect the
existing private backup/manifest and restore receipts locally through the approved
operations workflow. Do not paste raw logs, dumps, environment files or signed
download URLs. Return these noncredential receipt fields, or explicitly mark each
unavailable field and why:

| Evidence | Fields needed |
| --- | --- |
| Recovery source/observation | Observation UTC; source project/branch/compute/database; source endpoint match; receipt/run identity and status. |
| Existing off-host backup | Dump completion UTC and source target; bucket/key/version or equivalent private object identity; object size; manifest SHA-256 and verified downloaded-object SHA-256 match; successful archive-list validation; latest freshness check UTC/status/age. ETag alone is not a SHA-256 verification. |
| Current PITR alternative | Current provider observation UTC; exact oldest and latest available restore timestamps and/or LSN bounds for this branch; proposed recoverable point within those bounds. If API/UI exposes only retention configuration, state that the actual interval remains unverified. |
| Most recent existing restore receipt | Run UTC/status; exact source object/hash or source branch/time/LSN; isolated destination identity/PG version; schema/constraint/sequence and application-data validation outcomes; observed duration. State whether the receipt covers the current backup/source version. Do not create a restore just to fill this field. |
| Limit and decision | Recovery-point age, scope, any missing/currentness mismatch and the release owner's assessment. Historical receipt existence does not prove a current tested restore. |

The [pinned hosting-ops runbook](https://github.com/elischiffler/hosting-ops/blob/62f9b64ddae0567b9a1f63a68040c0c9469fe541/scripts/roadtrips-s3/README.md)
documents historical schedules and a September 28 restore. It is not today's
receipt. No `systemctl start`, backup creation, restore, migration, role change,
rollback, deployment or customer-row query is part of this handoff.

## Preparation verification

The document's Python block was syntax-checked offline. All nine query strings
were then executed in a read-only transaction on an empty disposable PostgreSQL
18.6 container using a cached image, network disabled, no published ports and
ephemeral storage. No application DDL or customer rows were created. The session
reported read-only, all queries succeeded, and absent sharing tables produced
exactly eight privilege rows with null permission results. The isolated container
was removed. This checks query syntax and missing-object behavior, not deployed
connection-factory execution or a populated schema's compatibility.

No query was executed on a hosted or cloud-configured DSN. This preparation does
not verify production target, effective role, actual eight grants or current
recoverability; the authorized operator's result is the missing evidence.
