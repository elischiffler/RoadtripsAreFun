# Cloud catalog integration, October 22, 2026

The complete twelve-commit cloud history through
`5e139b5a5b42bbe44a4904294491ee80b6b02987` is reconciled with Mac develop
`f3ed00795e0631572704104f4d54a70c93c7f2a4`, preserving the session cache and
research dashboard changes. This integrates code and historical research; it
does not import a catalog, migrate a database, deploy main or change the app's
Neon-backed runtime to a local mock database.

The Library bundle and audit ZIP were transferred onto the Mac and verified
against their supplied sizes and SHA256 hashes. The bundle passed Git integrity
checks and required only the existing base
`3e7010ca5361b752f3e65255190dec249994de26`. Independent inspection covered all
207 new-history blobs: no live credentials, restricted operator response bodies,
media or database dumps were found. Private original evidence, source/research
archives and recovery artifacts remain outside publication.

## Historical records and current exclusions

The four distinct browse batches contain 129 + 24 + 41 + 27 = **221 historical
T2 identities**. Their preview rows, null/unknown fields, attribution, license
partitions, original decisions and provenance remain unchanged. They are not
automatically eligible now: admission expires and later holds override approval.

The retrospective audited the earlier 194 identities and imposed **133 release
holds**. The remaining 61 had no observed pacing hold under the retained evidence;
that finding does not clear factual, rights, current-access or release gates.
The latest 27 were audited separately. Thus 88 of the historical 221 are outside
this retrospective hold list, without blanket approval. There are **zero new T3
conversions**. The separate earlier 93 USFS records are outside this audit and
retain their historical claims without new certification.

`backend/app/catalog/release_holds.json` preserves the supplied sidecar exactly.
`release_holds.py` pins its SHA256 and validates all 133 unique identities; a
missing/corrupt list fails startup. Removing or amending a hold requires an
explicit evidence review and a reviewed change to the list and pin. Renewed
approval timestamps, T3 markers, alternate provider fields and retained aliases
cannot clear it.

Python admission and SQL discovery exclude held identities before browse/routing
limits. Authoritative current-record reads also exclude them. Ordinary staging,
incremental calendar staging and activation refuse held rows before writes.
Activation checks old staged generations too; frozen recovery refuses a held
target without modifying the historical receipt. Other recovery integrity and
arrival/calendar gates remain in force. The local proof tool refuses held inputs.
Historical data stays available for duplicate detection and review, rather than
being silently filtered out of an otherwise approved generation.

## Data release remains blocked

No production catalog/calendar query, import, migration, activation or write was
performed during integration. A fresh complete live-parent fingerprint and
identity/alias/name/spatial/campus reconciliation are still required. The bundle
intentionally lacks private original source evidence required by typed replay;
preview JSON must not replace it. Each selected hold needs permitted evidence and
review, followed by ordinary staging, recovery and coordinated release gates.
Neither 917 in a historical local diagnostic nor a previously observed 608 live
rows establishes current net-new coverage. No additional records are claimed to
be visible in the live app by this integration.

## Verification boundaries

Offline tests strip ambient credentials and dotenv loading, and block external
DNS/sockets. The offline runner now uses the application's normal CORS defaults
instead of supplying a JSON string to a comma-separated configuration field.
Disposable PostgreSQL tests use synthetic rows in a task-owned tmpfs container,
not Neon or a persistent local runtime catalog. Tests cover all 133 holds,
alias filtering before SQL limits, retained source facts, staging refusal and
activation/recovery refusal. Final verification and exact published-SHA CI are
recorded separately from the dated cloud validation reports.

Final local checks: backend Ruff formatting/lint, 2,137 offline tests passed
(143 skipped; 80.04% coverage); 43 disposable PostgreSQL 18 checks passed.
The final network-disabled container passed the same 2,137 tests with 80.40%
coverage. Frontend formatting/lint, 293 tests (92.58% coverage) and build passed.
The temporary PostgreSQL fixture was removed and created no persistent volume.
Container import-path configuration and a comparison test's dependency on a
real research artifact were corrected without changing runtime source facts.

See [audit and per-batch counts](data/catalog-release-audit-20261022/mac-integration.json),
[original audit summary](data/catalog-release-audit-20261022/audit-summary.json) and
[per-record remedies](data/catalog-release-audit-20261022/per-record-audit.json).
