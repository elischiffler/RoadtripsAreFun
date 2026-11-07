# Stage 2 completion candidate — November 7, 2026

This document tracks the local integration after reviewed PR67 head
`3a5494d5e7b1d7121982d86522e66045b2af3cb9`. Earlier verification and the four
original feature heads are recorded in `stage2-integrated-handoff.md`; that report
is a historical checkpoint, not evidence for the newer combined head.

Local pre-push report recorded **November 7, 2026**, for application source freeze
`8715eee7dbc4259f4a77ba514e51747cd0dccb66`. This documentation update changes no
application or tests. Combined backend/frontend gates and the complete native
overnight journey passed as recorded below. The four hosted workflows had not
yet run when this local report was recorded; verify the final exact head's checks
on [PR67](https://github.com/elischiffler/RoadtripsAreFun/pull/67) for current CI
authority. Older green checks do not establish acceptance for a newer head.

The later 24-record semantic-context reconciliation is recorded separately below.
Its focused checks do not relabel this earlier full-suite/native snapshot or any
older hosted CI as acceptance for the new registry/head. Fresh combined checks
must be associated with the final exact PR67 head after integration.

Production was held at this pre-push snapshot. No sharing migration, production
deployment or live provider/Mentro trip was performed by this follow-up. Read-only migration
preflight found the target compatible with the proposed additive migration;
this does not mean the migration is applied or sharing tables are ready. The
effective EC2 application role remained unverified, and current recovery evidence
was unavailable to preflight. Release needs current recovery evidence, including
a sufficiently recent verified backup/restore receipt or validated PITR point;
preflight did not establish that a new restore exercise is mandatory for every
additive migration. Local or hosted test fixtures do not supply this evidence.
The [read-only operator handoff](sharing-readonly-operator-handoff.md) supplies
the actual app-connection/schema/privilege queries and existing recovery-receipt
fields needed to resolve these access gaps without exposing credentials.

## Current follow-up scope

The current backend supports practical multi-day trips with wrapped driving and
daytime sleep. The shape remains exactly one cyclic driving block and one cyclic
sleep block in 24 hourly slots, with rest elsewhere. Structurally valid rhythms
are not rejected merely for time of day; actual roads, visit calendars, full
meal intervals, hotel quote coverage and bounded trip length can still make a
particular trip infeasible. The strict one-day rule remains complete aware UTC
elapsed time below 12 hours, with no silent hotel insertion or proof from a
road-only estimate.

Driving cycles/deadlines are recomputed in the verified next known stop's IANA
zone. This is a next-known-stop planning clock, not a timezone survey of every
road point. Positive driving cannot acquire another day from a timezone change
or continue through rest/sleep. UTC elapsed arithmetic preserves DST duration;
relevant ambiguous or nonexistent local boundaries return fixed typed conflicts
rather than silently choosing an offset. These checks apply to estimated
scheduling as well as actual final-road timing, rebuild and edit preview.

For explicit rhythms, meal windows shift by local sleep-end hour minus 07:00;
full 30/45/60-minute breaks must fit awake intervals and never overlap sleep.
For sleep 08–16, breakfast is 16–18, lunch 21–23 and dinner 03–05 on the following
calendar date, belonging to the preceding awake cycle. Meals reserve time only:
no dining venue or safe roadside stopping place is verified. Legacy no-rhythm
windows and policy serialization remain unchanged.

Overnight planning obtains actual full dated quotes through the existing hotel
provider contract, with exact per-room occupancy and complete check-in/check-out
coverage. Daytime/after-midnight rest can require prior or additional quoted
nights. The cost sums verified whole-stay quotes once; it does not multiply a
one-night rate into an invented multi-night price. The budget remains advisory
per room/night. Quoted dates and planned physical arrival/departure are displayed
separately; check-in, checkout and continuous room access require confirmation.
They are hotel options, not bookings or guaranteed daytime access. Separate
room inventory and current live provider markup remain unverified by fixtures.
The 18:00/09:00 booking coverage envelope is an application planning convention,
not published hotel hours. See [the complete rhythm/quote contract](unrestricted-daily-rhythm.md).

Early preparation uses known road geometry, departure-wall-clock estimates and
the shared meal policy to produce at most three **tentative stay search areas**.
It makes at most six bounded admitted-catalog reads and publishes unscheduled
ideas progressively. There are no early AI or hotel quote requests. Sparse
catalog samples can omit places; travel-date opening hours, arrival-local clocks,
availability and trip eligibility are not established by preparation. Actual
candidate progress distinguishes discovered ideas, solver-selected proposals and
rerouted checking scenes; every scene is provisional. Geometry projection
supports both native models and legacy attribute/mapping containers without
serializing private fields or altering actual planning inputs. Session/input
keys, a 400 ms debounce, cancellation and stale-response guards protect the UI;
already-running synchronous catalog work can finish after abort. Confirmation,
cache/retry ownership and no-save-before-explicit-confirmation remain intact.
See [progressive preparation](progressive-route-preparation.md).

### Sharing policy resolved

The user's **"Anyone can view"** decision resolves the sharing policy: anyone
holding the opaque revocable link can view the minimal trip projection without
an account. Connecting an authenticated account is optional and grants read-only
access to that same shared trip. This does not grant editing, live GPS, private
arrival/visit history, inferred preferences or chat access. No invitation or
message is sent. Stopping a link preserves already connected accounts; stopping
all sharing revokes both. Removing a connected account also stops link access,
with stale membership changes rejected. Owner authorization, revocation,
delete/recreate identity and geometry isolation remain server-enforced. The
privacy allowlist shares actual rest/sleep rows and literal trip mode while
omitting raw recurring policy, cached proof and private lodging metadata. See
[sharing semantics](trip-sharing.md).

### Research reconciliation resolved

The supplied 24-record artifact has now been reconciled in semantic-context
commit `2971b00`, integrated as `3e6e3e5`: **all 24 incoming native identities and full source-row
fingerprints match the read-only current catalog inspection**. The static display
registry contains **31 bindings**: the original seven and their credited local
photo are preserved unchanged, plus 24 new text-only bindings with no overlap.
No new photo was added. The [24-record reconciliation report](data/semantic-context-24-20261107/README.md)
is authoritative for the per-record source/rights decisions and current-catalog
receipts; the [initial seven-binding review](data/place-context-20261107/README.md)
is the historical baseline, not the current registry total.

At the report's **November 7, 2026, 03:41:23.291 UTC** inspection, **11 incoming
records** passed existing admission/calendar policy. The other **10 T2 browse-only
records and 3 without required calendars remain suppressed**. These are dated
results for the incoming batch, not a claim that all 31 bindings currently serve
or that any place is selected, open for a trip date or newly admitted. Production
retains current identity refresh, the real clock, admission/holds and calendars;
optional context has no AI/network fallback. No source facts, admission contracts,
calendar approvals, arrival coordinates, ratings, active generation or schema
were changed by this display-only reconciliation.

The current read-only catalog receipt identifies active generation
`5186c0bc2dc667dcdc36d1594e1640be46c42a86e3ae9ce3546b0e8d474c9660`,
release `04-overture-a75-2026-11-04`, with **1,142 declared rows** in Neon project
`misty-mouse-24917066`, branch `br-noisy-forest-aqidrq92`, database `neondb`.
That is distinct from the older 1,067-row reference archive. The MCP owner-session
observation is current-catalog evidence, not proof of the effective EC2 app role,
sharing migration or recoverability.

The lane reports **167 focused/adjacent tests passed**, including **42 frozen
evaluation cases**, plus Ruff/format checks. Independent source/rights and
catalog-equality reviews approved `2971b00`. Fresh combined exact-head CI remains
pending and is separate from those focused results and the earlier full/native
snapshot below. The optional original November 4 reference archive is not needed because
all 24 full-row fingerprints match the current canonical rows. **No research
user action is needed**. Effective EC2-role/current recovery evidence remains a
separate unresolved release boundary.

## Local verification snapshot — November 7, 2026, source freeze `8715eee`

| Required evidence | Status when this local report was recorded |
| --- | --- |
| Combined offline backend coverage and full lint/format checks | **PASS**: 2,995 passed, 180 skipped, 81.89% coverage; Ruff lint and all 335 format checks passed |
| Combined frontend coverage, format, lint and build | **PASS**: 617 tests / 78 files, 92.79% lines, 88.11% branches, 89.90% functions; format, lint and build passed |
| Actual native overnight/wrapped-drive/daytime-sleep browser → API → CP/timing → disposable PostgreSQL journey | **PASS**, exit 0 on `6de80a4cba2e1e1a37b1ed718f294525bbc1365a`, with the same application trees |
| Observer integrity checks and forbidden-network detection in the mandatory journey | **PASS**: seven observer tests; browser errors, blocked origins and Python blocked attempts all empty |
| All four hosted workflows on the final candidate | Not yet run at this November 7 pre-push snapshot; verify the final exact PR67 head. Old `4074181` CI is not acceptance |
| Effective EC2 application-role sharing privileges | **UNVERIFIED** |
| Current recovery evidence for the migration target | Unavailable to preflight: obtain a sufficiently recent verified backup/restore receipt or validated PITR point |
| Later 24-record research reconciliation | Resolved by the separate `2971b00` follow-up above; its focused evidence is not part of this earlier full-suite snapshot |
| Hosted sharing migration and deployment | **NOT PERFORMED** |

These results are tied to backend tree
`0dbe7243a7da44e8b4ddd0130793ef2c7efc1c5b` and frontend tree
`1b9bbf656c03c5ea8f697f4de1fddd0e733c5e6c`, both present in `8715eee`.
Backend coverage took 105.54 seconds and exceeded its 63% gate. The frontend tree
was unchanged through this source freeze. Backend evidence:
`/tmp/stage2-corrected-backend-coverage.log` in the implementation workspace.

The complete native gate passed on `6de80a4cba2e1e1a37b1ed718f294525bbc1365a`,
using the same backend/frontend application trees above. It exercised the full
strict primary journey and actual overnight candidate/confirmation, scheduling,
quote coverage, itinerary, save and reload through the browser, API and disposable
PostgreSQL. Two hotel stays each retained a full two-night USD 250 quote (USD 500
total), full 08:00–16:00 sleep intervals and wake-relative full meal breaks. The
final edited trip ran from November 15 at 20:00 to November 18 at 01:18. These
are actual computed fixture outcomes, not synthetic eligibility/proof metadata.

Six real bounded preparation sections and the ready UI were observed; provisional
planner progress was observed at its actual execution seams. Short-awake meal
infeasibility and an edit exceeding driving availability returned 422 and left
stored state unchanged. A distinct feasible late alternative, with an actual
source calendar and 120-minute visit, passed UI preview, explicit save and reload
without extra AI or hotel searches. All seven observer tests passed; browser
errors, forbidden-origin observations and Python blocked-network attempts were
empty. Temporary services and dependency links were cleaned up. External road,
hotel, model and authentication responses remained explicit local fixtures.

The native owner maintains [the detailed journey validation record](../tests/guidedjourney/VALIDATION.md);
its actual local provider seams, assertions and cleanup results determine the
scope of that acceptance. No fixture result attests live hotel inventory,
live third-party map rendering, physical-device GPS, real Cognito service
behavior or production recovery.

## Historical reviewed histories retained

| Lane                                                       | Exact reviewed head                        | Local integration                |
| ---------------------------------------------------------- | ------------------------------------------ | -------------------------------- |
| Selected route-pin branding and themed authentication      | `f5f3ab33e68bf65f7f92ce564856f14cc7fea24f` | Retained from the parent's merge |
| Source-reviewed place context and credited local imagery   | `18fa070f3b8e911f833c5cf9a24227fe4c966266` | Retained from the parent's merge |
| Complete one-day candidate choice and daily rhythm backend | `befbefce61c089635c0cd7690ab8217c9a544bb4` | No-fast-forward merge `9fb1f42`  |
| Trip sharing and safe saved-mode display                   | `fa8c76e290605b4d9ad3f0012c9c72d2cda65591` | No-fast-forward merge `75d32af`  |
| Reconciled foreground arrival tracking                     | `cd41ae4aba7a1c5ca6fae7ca8407fc61fe0f6282` | No-fast-forward merge `cbaddaf`  |
| Onboarding, candidate map and daily rhythm controls        | `1c6b51749ff5abfd8a1f7d13eef66b6b879f5966` | No-fast-forward merge `d07f6f7`  |

The initially verified combined application checkpoint is
`d07f6f75fc3b099e73ad120ffbafdc57df5ba2b2`. The earlier native journey checkpoint is
`48204ece680feb2a10aff6f4692976717cf5a754`, adding the independently reviewed
sharing readiness prerequisite and shared-only Home entry. The latter preserves
owned-route priority, checks connected trips only after a verified empty owned
list, rejects stale account results and offers recovery on lookup failure. Its
reviewed two-file head `bd7015f8467727e63324600987a9a8c715a3f2f2` was merged without
conflicts; 15 owner and 10 independent focused tests passed.
The reconciled arrival merge retains both original implementation parents rather
than dropping either history. Original feature branches remain untouched.

## Retained implementation boundaries (with current follow-up above authoritative)

The one-day backend verifies actual final roads, visits, published opening waits,
reserved meal breaks and local driving availability before offering eligibility.
The limit is strict aware UTC elapsed time below 12 hours. The road-only preview
is not proof. Explicit request registration, owner/input binding, bounded cache,
fixed error codes, idempotent reuse and cancellation prevent an uncertain response
or cache miss from silently repeating model work. One-day requires no hotel
provider or room occupancy; allowing overnights retains the existing room/provider
contract and does not force a hotel where none is needed.

Daily rhythm now supports the wrapped/multi-day/daytime-sleep behavior described
above. The earlier restriction to conventional overnight hotel clocks is
superseded. Hotel rows retain actual rest/sleep intervals, wake-relative meals,
full dated quote prices and explicit access-confirmation wording. The legacy
no-rhythm hotel clock remains unchanged.
A saved one-day route is revalidated on itinerary
rebuild and edit preview; copied proof metadata is never authority. See
`one-day-candidates-and-daily-rhythm.md` for exact endpoint, policy and limitation
contracts.

Place context is optional reviewed display data outside physical stop dictionaries.
It is attached after authoritative admission and timing, without changing source
facts, calendars, registry pins or persona ratings. Missing context has no model or
network fallback. See the place-context source registry and its review handoff.

Arrival assistance uses one foreground tracker and account/trip/session guards.
The reconciled flow retains strict dwell/accuracy/closest-target checks, handles
visibility and departure state, and shares explicit visit/Undo persistence with
scoped revision checks. No physical GPS or background tracking acceptance is
claimed. See `foreground-arrivals.md`.

Sharing uses its own reviewed minimal projection and member/owner boundaries.
Actual rest/sleep rows and literal trip mode can be shared; raw recurring policy,
proof, inferred preferences, chat history and private arrival state are omitted.
See `trip-sharing.md` and `trip-sharing-validation-20261107.md`.

The automatic merge preserved `Route.place_context`, `trip_mode` and proof fields,
both candidate and sharing routers, itinerary context refresh and mode validation.
No hand-written conflict resolution was needed for the backend/arrival merges.
The sole onboarding conflict combined the exact reviewed candidate and sharing
protected-request allowlists, preserving verifier classification, retry counts,
sharing/session return paths and safe return-path validation. Independent source
review approved this combined application checkpoint.
Compared with PR67 head `3a5494d`, the exact blobs for `catalog/hold_resolution.py`,
`catalog/admission.py` and the frozen evaluation scenario fixture remain unchanged;
no path under `backend/data` changed. The only additional catalog paths are the
reviewed optional place-context module and its display registry.

## Historical verification — November 7 preceding checkpoints

These checks apply only to the named earlier trees/lanes. They are retained as
regression history; none replaces the current verification table.

| Earlier checkpoint | Recorded acceptance |
| --- | --- |
| Original one-day backend lane `befbefc` | 2,848 passed, 151 skipped, 81.83%; later 109 focused tests after a bounded guard |
| Original sharing lane through `fa8c76e` | 2,817 backend and 492 frontend tests; signed disposable-PostgreSQL authorization/revocation cases |
| Reconciled arrival lane `cd41ae4` | 523 frontend, final 69 focused frontend and 27 backend cases; mocked browser acceptance |
| Original onboarding lane `1c6b517` | 495 full frontend before final deltas; 97 final focused tests and two mocked browser journeys |
| Combined `d07f6f7` | 2,891 backend passed, 163 skipped, 81.62%; 591 frontend / 75 files, 92.65% lines; format/lint/build passed |
| Combined primary native journey `d07f6f7` | Actual complete candidate pipeline, save/edit/reload, visit CAS, settings, expired-date rejection; synthetic provider leaves and actual signed local API/CP/timing/PostgreSQL |
| Readiness prerequisite `3b313fc` | 47 focused tests and 17 actual disposable PostgreSQL privilege/schema/isolation cases; each privilege revoked individually and a SELECT-only effective role rejected |
| Earlier native journey `48204ece` | Primary flow plus second synthetic participant using the real Cognito SDK with local token/JWKS fixtures; shared-only Home/read-only access without extra owned rows or model work |
| Earlier explicit hotel-meal correction | 116 focused tests, including 42 frozen evaluation cases; this preceded the newer unrestricted-rhythm policy |
| Earlier `4074181` hosted checks | Four green workflows on that older candidate; not current-source acceptance |
| Isolated preparation lane `846837f` | 603 frontend / 76 files, 92.66% lines; format/lint/build; subsequent geometry compatibility correction passed 96 focused backend tests |

An intermediate follow-up backend run failed (2,949 passed, 9 failed, 180 skipped,
81.87%) because preview serialization assumed a Pydantic geometry. The reviewed
correction preserved frozen fixtures; 96 focused tests and the current full
2,995-test backend pass supersede that failed run. Known-stop cycle and typed
DST-conflict corrections are included in the current freeze.

Native acceptance also found an integer-second versus ISO timestamp precision
assertion (50,400 versus 50,400.001 seconds). A peer-reviewed test-only tolerance
below one second corrected that representation boundary; application clocks and
hard scheduling checks were unchanged. The subsequent complete native pass above
includes both the infeasible-edit rejection and a genuinely feasible successful
edit, rather than loosening the planner to force acceptance.

The earlier primary native fixture had no hotels, so it did not establish
full-date hotel quote behavior. Its real computed candidate elapsed time was
18,000 seconds, assessment left SQL trip count zero and progress below completion,
and final fixture counters were solver 3, ratings 4, durations 2, gateway 6,
hotels 0, stored trips 1. Temporary services/dependency links were removed.
Historical hosted/local green results cannot be relabeled as current overnight
or live-provider evidence.

## Current migration, release and preview boundary

The additive sharing migration is checked in with rollback and validation notes.
It has **not** been applied to production. The normal disposable schema includes
it for local/CI acceptance; successful local SQL does not establish hosted schema
readiness. The complete-release `/ready` guard requires both sharing tables,
11 required column names/types and each individual CRUD privilege through the
actual application role. It uses only read-only checks and fixed 503 responses;
it does not attest foreign keys, indexes, backup/recovery or account acceptance.
Keep the parent-coordinated backend/migration-before-frontend order.

Read-only preflight found the target compatible with the proposed migration,
not proof of applied sharing schema or of each privilege through the effective
EC2 application role. That role remained unverified and recovery evidence was
unavailable to preflight. Obtain current recovery evidence, including a
sufficiently recent verified backup/restore receipt or validated PITR point;
a new restore exercise for each additive migration is not an established gate.
Use the [read-only operator handoff](sharing-readonly-operator-handoff.md): an
authorized operator can provide sanitized results through the running app's
connection factory plus existing current recovery receipts, or a legitimate
read-only host/ops identity can be configured in environment settings. No
credentials in chat and no fresh restore are required by that handoff.
No hosted migration, role grant, schema mutation or deployment is authorized by
this handoff itself or performed here. Keep production held until the concrete target,
recovery evidence, final checks and coordinated release authorization are settled.

Historical frontend previews pointed at production backend revision
`42d5068bb4c8804a8024df0e4463fb05e0a7e275`, which lacked the candidate/sharing APIs.
That observation is not a fresh deployment inspection. Verify actual frontend
and backend targets during release; a standalone frontend preview cannot prove
a working combined release. The local browser/API/PostgreSQL journey passed on
the recorded source trees. Hosted workflows had not yet run at this November 7
pre-push snapshot; the final exact [PR67 head's checks](https://github.com/elischiffler/RoadtripsAreFun/pull/67)
are the authority for current CI status. No preview protection change, extra
public service, direct main push or approval bypass is part of this documentation
update.

Real Cognito, physical-device arrival behavior and the separately approved single
post-deployment live Mentro/provider check remain distinct acceptance boundaries.
That live check is unused and requires an authorized application session after a
coordinated deployment. No previously denied Neon test is retried here.
