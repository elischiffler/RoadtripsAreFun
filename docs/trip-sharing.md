# Read-only trip sharing

This implementation starts from integrated Stage 2 `3a5494d`. It adds no provider,
AI, email, invitation, tracking or editable-member capability. Sharing is separate
from owned chats: recipients read the owner's current saved trip, not a copied
trip added to their owned workspace.

## Traveler flow

Open an owned saved trip, expand **Share this trip**, and create a sharing link.
The disclosure before creation says anyone with that link can view the route,
trip addresses, dates and schedule for 30 days. The link is a bearer capability:
send it only to intended viewers. Creating/replacing a link checks the saved
trip's current opaque revision; a stale or reused trip snapshot must be reloaded.
Sharing metadata does not change the trip or invalidate its owner edit revision.

A viewer may open the read-only outline and schedule without an account. They
may explicitly sign in, choose a display name for the owner, and **Connect my
account**. Names are traveler-chosen labels, never verified emails or authority.
Only the backend-verified Cognito access-token subject grants the connection.
After connecting, **Saved trips → Shared with me** reopens the same trip without
the link. Refresh reads the owner's latest saved content. No owner edit, visit,
arrival assistance or car controls are mounted in these pages.

Owner controls have distinct meanings:

- **Replace sharing link** invalidates the prior link and retains existing members.
- **Stop link** prevents anonymous viewing and new connections through that link;
  existing connected accounts retain their independent read-only access.
- **Remove connection and stop link** removes that account and disables the link
  they may already know. Other connected accounts retain access. Creating a new
  link is an explicit owner action; sharing that new link can grant access again.
- **Stop all sharing** deletes the share identity and every connected membership.
- Deleting the owner trip cascades both tables. Recreating the same chat number
  creates no connection to an old share or token. A stale sharing panel cannot
  revoke a newly created sharing identity.
- A member may **Leave shared trip**, affecting only their own connection.

Revocation applies to subsequent server requests. A response already authorized
and in flight can complete; downloaded/copied content cannot be recalled. Shared
pages refresh explicitly, without claiming instantaneous remote erasure. At most
32 accounts can connect to one trip; the account list shows the latest 100
connections. The owner can remove a connection to free a place.

## Privacy and token handling

Tokens are generated with 256 bits of cryptographic randomness. PostgreSQL stores
only a SHA-256 digest; only a freshly created response contains the plaintext.
The owner copies a URL fragment, `/share#token=...`. The public page captures it
into ephemeral process state and removes the fragment from the address bar before
paint. Token use is a POST body to a fixed API path, not a path/query parameter.
There is no token in router return state, local/session storage, errors or logs.
In-app sign-in returns to plain `/share` using that ephemeral memory. A hard
refresh after fragment removal loses it; reopen the original link or use an
already connected account. No token recovery from PostgreSQL is possible.

Public requests use a separate HTTP client with no account headers or cross-origin
credentials. Authenticated operations retain the existing narrowly bounded retry
for the verifier's exact initial rejection; transport errors or application errors
never replay mutations automatically. Account switches discard late account data.

Shared payloads explicitly allow only endpoint display labels, route coordinates,
driving totals, and bounded itinerary names/times/types/meal windows. They exclude
ChatLog, private trip profile/inferred weights, source/rating blobs, car/budget/
price/room details, visit presentation, live or historical user position, member
identifiers and owner identifiers. A shared content revision hashes only that
public projection, not private account fields. Normal owner write revisions remain
separate. No external map SDK, links, images or third-party telemetry is mounted
by the shared view. Route outlines are a simple local SVG, reduced to at most 4,096 points for long routes;
this is an overview rather than turn-by-turn navigation.

Every geometry read includes the share's stored owner, chat and route identity;
recipients never choose those identities. Authorization, trip JSON and segmented
geometry use a read-only repeatable-read transaction, so a concurrent owner edit
cannot combine old metadata with new coordinates. Link join, rotation and
revocation serialize on the sharing row. A stopped token cannot add a membership
when revocation wins. Ownership uses the verified subject on every management
operation; client account/email/role fields are rejected.

All sharing responses are `Cache-Control: no-store, private`. Share-link API
responses also specify `Referrer-Policy: no-referrer`. The global operational
logger already excludes request paths, headers and bodies.

## Prepared migration and release boundary

**A new explicit migration is required. It has not been applied to any hosted
database.** The authoritative forward file is
[`backend/sql/trip_sharing.sql`](../backend/sql/trip_sharing.sql). It creates only:

- `trip_shares`: one UUID per owner/chat, nullable unique token digest/expiry,
  foreign key to the existing `(chats.user_id, chats.chat_id)` primary key with
  `ON DELETE CASCADE`.
- `trip_share_members`: verified subject, opaque connection UUID, chosen display
  label and connection time; unique `(share_id, account_id)`, indexed account
  lookup and cascading share foreign key.

There is no startup DDL, migration auto-apply or modification to account
permissions, existing owner data, catalogs or source/calendar safeguards. Existing
`/ready` remains unchanged. Missing/incompatible sharing tables fail sharing
endpoints with fixed 503 responses; existing saved-trip reads/writes continue.
`IF NOT EXISTS` makes repeated application idempotent on the expected schema, not
a repair of incompatible tables with the same names.

Before a production release, the release owner must present and obtain approval
for the concrete database/branch/name and role, verified schema/constraints,
recovery point and migration file. No production target is inferred from a local
fixture. Confirm the existing chats primary key/type and migration-role privileges.
Take and verify the approved backup; inspect existing `trip_shares`/
`trip_share_members` names to reject incompatible preexisting tables. Apply the
reviewed file transactionally through the established database operations process:

```sh
# libpq must already select the explicitly approved target; no URL printed here.
psql -X --set ON_ERROR_STOP=1 --single-transaction --file backend/sql/trip_sharing.sql
```

Verify the two tables, unique constraints, owner/chat foreign key, cascading
membership foreign key and account index. Then verify sharing with approved
synthetic accounts/trips on that target: create/read/connect, owner rotate/remove,
member read rejection after revocation, and owned trip behavior. That acceptance
requires its own authorization and is not supplied by the offline tests.

### Rollback and recovery

The safest application rollback leaves the two additive tables in place; older
application code ignores them and existing chat deletes still cascade. Disable
sharing endpoints before metadata rollback. The separate reviewed
[`backend/sql/trip_sharing.rollback.sql`](../backend/sql/trip_sharing.rollback.sql)
drops only the two sharing tables; it permanently revokes all links/connections
and preserves chats, coordinates, logs, profiles and catalogs. Apply it only to an
explicitly approved target with the corresponding backup, using the same
transactional operations procedure. No rollback has been applied to a hosted DB.

Backup/restore must include sharing tables and their related owner chats together.
Restoring an older backup can resurrect tokens or memberships revoked after that
backup. Before reopening any restored environment, the safe default is an
explicitly approved reset of sharing metadata (delete `trip_shares`, cascading
members) and fresh owner-issued links/connections. Do not claim revocations survive
an arbitrary old snapshot. An intact, verified current-state recovery may retain
metadata only under a reviewed recovery plan that accounts for revocation history.

The disposable PostgreSQL recovery probe preserves a synthetic share and member
through its existing restart/backup/restore checks to detect storage loss. That
proves data round-trip behavior, not the operational decision to reuse recovered
capabilities. The test schema and canonical-source comparison include the new
DDL; this does not authorize a hosted migration.

## Validation

Focused offline tests cover signed authentication before storage, no client account
trust, fixed error redaction/cache policy, secret representation, strict output
projection, geometry ownership and transaction cleanup. Frontend tests cover the
public disclosure, distinct revocation actions, ephemeral/stripped fragments,
token-free sign-in return, account-switch isolation, read-only pages, and audited
transport/auth retry boundaries.

The dedicated `trip_sharing_postgres_tests.py` lane uses the existing disposable
settings database guard and actual signed JWT verification, API/CRUD, foreign-key
cascades, JSON and coordinate storage. It checks owner/member isolation, repeated
connect, stale owner revisions, rotation/expiry/stop/remove/leave, deletion and
same-ID recreation, coherent geometry during a real concurrent update, in-flight
revocation boundaries, missing-table sharing-only 503, and actual row-lock
stop/rotation races against joins. It is skipped unless that known disposable DB
is explicitly selected. No provider, hosted DB or live Cognito acceptance is
claimed. Full-suite results and any browser verification are reported in the
worker handoff, not assumed here.
