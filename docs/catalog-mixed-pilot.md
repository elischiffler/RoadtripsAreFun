# Authentic mixed-source catalog pilot — October 15, 2026

The current **local evaluation catalog contains 400 unique records**, across 30
states and DC. No production catalog schema, import, activation or deployment
has occurred. The 69 Boulder/NPS records have documented facility or car-parking
arrival evidence. The 331 Overture records are source-admitted test candidates;
independent current public-access and arrival review is incomplete. Do not treat
400 as a count of places cleared for production.

The [aggregate receipts](evidence/catalog-mixed-pilot-20261015.json) record the
actual import, rollback, separate restore, category/state counts and gaps. The
[earlier five-archive intake](catalog-kaggle-intake.md) retains the original
Kaggle schemas, hashes and upstream rights findings. Raw archives, source
snapshots, detailed selection receipts and the database dump remain outside Git.

## Actual coverage

Each record receives one reporting category here; other supported taxonomy
labels remain available for discovery. Categories do not double-count parks that
are represented by a museum facility.

| Primary category                | Local evaluation records | Documented Boulder/NPS arrivals |
| ------------------------------- | -----------------------: | ------------------------------: |
| Dedicated niche/roadside intake |                        0 |                               0 |
| Entertainment                   |                       56 |                               0 |
| Nature/gardens/trailheads       |                       33 |                              12 |
| Beaches                         |                       12 |                              12 |
| Landmarks                       |                       31 |                               0 |
| Museums                         |                      231 |                               8 |
| National parks                  |                       37 |                              37 |
| **Unique total**                |                  **400** |                          **69** |

This is 100 below the approximate 500-place target and is museum-heavy. It has
urban clusters rather than national corridor coverage; no food/nightlife batch
is claimed. Alaska has seven test records and Hawaii eleven. Missing states are
AL, AR, CT, DE, IA, ID, KS, LA, MI, MO, MS, NC, NE, NH, OK, PA, RI, VT, WI and WV.
The aggregate receipt includes exact counts for all represented states/DC.

| Source                                                       | Local records | Admission basis and remaining limits                                                                                                                                                                                                                                                |
| ------------------------------------------------------------ | ------------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Overture Places 2026-09-23.1                                 |           331 | Approved upstream provenance/retained licenses, explicit US/state, point taxonomy, source open status and existence confidence at least 0.9, reviewed identity/address/website selection, driving-network proximity. Current operator/public arrival review remains incomplete.     |
| Kaggle Boulder v1, current City evidence                     |            12 | Native trailhead IDs, CC0, retained City pages matching name, Open status, car parking and directions point. Two Flagstaff Summit access points count as one destination.                                                                                                           |
| Kaggle NPS park-biodiversity v3, current official facilities |            45 | One selected visitor facility per parent park, agency-published facility coordinates, directions/car-access evidence and nonempty weekly schedule. Eight facilities are reported as museums; 37 as national parks. No park-center coordinates or species observations are imported. |
| Official NPS beach parking                                   |            12 | Named beach destinations represented by positive-capacity car-parking lots in three inspected single-state units. Alternate lots are retained as source references rather than extra destinations.                                                                                  |

## Measured source review

The Overture pool contained 795 source-admitted points in bounded regional
extracts. Explicit identity review selected 342 with source street addresses and
websites, withholding rides/sub-exhibits, suppliers, duplicate/old names,
misplaced entries and unresolved visitor access. Twenty-six ordinary Mapbox
**driving directions** requests returned waypoint results for all 342; seven
points over 100 metres from the driving network were withheld. Four more were
withheld after website/access review, leaving 331 test candidates. Original
coordinates were never replaced by road snaps. Road proximity does not establish
parking, legal access, the correct entrance or future opening.

One ordinary request to each of 335 exact source websites followed only server
redirects. Results: 36 HTTP 200, seven 403, one 404, one timeout, one proxy error,
and 289 HTTP 503. Thirty-one bounded HTML snapshots were retained. No denied
endpoint was retried through another protocol/host/route. A live website alone
is not independent confirmation of its visitor address or arrival. Operator
review must continue before these candidates enter a production cutover.

The NPS enrichment inspected all 56 actual Kaggle v3 park identities and retained
current official structured-data snapshots. Eleven parks have no selected
arrival: eight require non-driving park access (Channel Islands, Dry Tortugas,
Gates of the Arctic, Glacier Bay, Isle Royale, Katmai, Kobuk Valley and Lake
Clark); Hot Springs lacks the required car-arrival evidence; North Cascades and
Wrangell–St. Elias have no passing published facility schedule in these snapshots.
These exclusions do not assert that a park is permanently closed.

Beach admission scanned 60 parking records: 32 were not named beach arrivals,
one lacked positive car capacity, and 15 alternate lots collapsed into retained
destinations. The result is 12 beaches across California (six), Florida (one)
and Indiana (five). A parking feed's `liveStatusIsActive` flag is retained as a
feed flag, **not** interpreted as open/closed status. Road/seasonal restrictions,
reservations, fees and future access remain unknown.

Dedicated roadside intake remains zero. The [roadside follow-up](catalog-roadside-review.md)
locates the actual LOC archive-rights statement; current visitor/arrival evidence
still blocks an intake. Its historical LOC-derived metadata has
no coordinates and does not establish a surviving visitor destination. IMLS
still lacks contributor flags needed to distinguish commercial contributions
and geocoding; no blanket government-work clearance is claimed. Rollercoaster
rides are not park arrival points. The large GeoNames mirror was not downloaded
outside the approved bound; its mirror/upstream license discrepancy remains open.

## Preserved implementation

The existing importer, tables and atomic activation/rollback remain in place.
New explicit schemas handle NPS visitor facilities, official beach arrivals and
a complete mixed generation. A mixed bundle references original artifacts and
hash-pinned child manifests; each child is re-admitted through its own adapter.
It rejects nested mixed bundles, namespace/rights/release conflicts, oversized
inputs and unresolved exact-name colocated identities. Explicit reviewed merge
mappings retain donor identities, provenance, release and attribution. No generic
Kaggle row can enter as an arbitrary normalized place.

`scripts/catalog_nps_manifest.py` builds the reviewed enrichment manifest from
local archive, snapshot index and explicit native visitor-center selections.
`scripts/catalog_mix.py` builds one complete replacement generation from original
inputs and sidecars. Both refuse existing output paths and perform no downloads
or database calls. The Overture combiner remains Overture-specific; its optional
explicit ID selection preserves original source features and pins the retained
regional manifests rather than repeating oversized extraction receipts.

The extractor handles both inspected official STAC asset layouts and retains the
workspace's configured proxy/CA verification. It validates the exact serialized
GeoJSON (including Shapely tuple coordinates), supports bounded category/open/
confidence filters and explicit reuse of retained release metadata. Overture-signals
is admitted only for operating-status processing under CDLA Permissive 2.0,
alongside an independently approved upstream identity; it cannot clear unknown
provenance. Public source notices include the NPS factual-data rights statement;
photographs, logos and third-party creative material are excluded.

Repository results preserve source-specific IDs, source release/attribution,
upstream provenance and the active generation. Those fields use the existing
candidate/itinerary/Studio contracts. The generation is evidence of the actual
stored snapshot, not a live availability or popularity claim.

## Authentic database and recovery proof

The final evaluated generation is
`644b404dd237d07fba916a6bc636decf66d31056c7898668921acf6be1e33aa3`.
Its input manifest SHA-256 is
`de3a32b49bbe0241dad8e48e6faf2f52fe5e161217b85a7fb8a2ffab8c68d381`.
The dated recipe release is `pilot-2026-10-15.1`; the immutable generation/hash,
not that release label alone, identifies this exact reviewed iteration.

All operations used isolated PostgreSQL 18.6 and authentic public records, with
no production application data. Repeated staging was idempotent. Activation,
rollback to the retained 12-place generation and return to the final generation
passed. Two generations total 412 stored rows, with an indexed catalog footprint
of 876,544 bytes and an observed database size of 8,869,567 bytes. These local
measurements are not a forecast of production growth.

The custom dump is 67,419 bytes, SHA-256
`11564a87269eca7da32f3e290695f5bd3e3ad15ae462d41bdec08a3ce8712d9e`.
An initially empty separate PostgreSQL database restored it successfully. Exact
row-content digests matched for all three catalog tables, import metadata and
the active pointer. The aggregate receipt contains each comparison.

Actual legacy, persona and evening discovery adapters returned imported records
while HTTP transports were set to fail on use: zero discovery HTTP calls and
zero Tripadvisor calls. Samples include `nps:arch` and native Overture IDs in
the aggregate receipt. This is authentic **local** adapter evaluation, not a
production website journey. Mapbox routing/geocoding remain separate services.

Backend validation: 902 passed, 87.49% application coverage including five real
PostgreSQL cases; unchanged 63% floor. Frontend: 314 passed, 90.23% line/statement
coverage; format/lint/build passed. All four workflows passed for the first expansion commit `eb382d2`. Its first
substantive CodeRabbit review produced seven comments. Follow-up fixes validate
coordinates before catalog access, extend HTTP transport guards, make script
inclusion explicit, preserve context-copy modes with streaming I/O, update mixed
rollout guidance, and reject dirty or mismatched prebuilt-image runs. Docker test
images now carry the revision label used by that check. Exact follow-up-head CI
and re-review are checked separately; the earlier draft status was a skipped
review, not approval.

## Remaining production gates

Read-only production verification at approximately 00:52 UTC on October 15 found
all three catalog tables absent. No production DDL, staging, activation, merge or
deployment has occurred. Current off-host backup/freshness/isolated-restore proof
must come through an existing authorized host/status path; GitHub and Neon
connectors cannot inspect those host artifacts. No new credentials or broader
security permissions are requested. Operational identifiers remain private.

Finish current arrival/public-access review, address the category/geographic gaps,
then follow the existing [rollout and rollback gates](neon-places-catalog.md).
Repository review/protection, exact-main CI and the established serialized release
path precede production acceptance. Capture the actual deployed revision and
live chat/Studio, route/scheduling, attribution and saved-history flows with
catalog IDs/provenance and zero Tripadvisor discovery calls. PR #41's separate
evaluation work is not modified by this catalog branch. Neither the local test
catalog nor a preview fulfills the requested production completion.
