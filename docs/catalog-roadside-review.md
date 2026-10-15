# Roadside source follow-up — October 15, 2026

The [subsequent current-arrival review](catalog-arrival-review.md) validates a
72-arrival generation, adding two independently reviewed Overture venues to the
70-arrival proof below. All earlier generations and the 400-record evaluation
remain preserved. Dedicated roadside intake still contains one destination.

Dedicated Kaggle roadside intake now has **one documented destination: Corn
Palace**. It is validated in a separate 70-arrival local generation, including
the previous 69 Boulder/NPS arrivals. The 400-record local evaluation catalog
and its immutable generation remain unchanged. Neither dataset is in production.
The [aggregate receipt](evidence/catalog-arrival-review-20261015.json) records
original-response hashes, admission/exclusion decisions and database recovery.

## Actual LOC archive statement located

The Kaggle v4 description links the original
[LOC rights statement](https://www.loc.gov/rr/print/res/723_marg.html). That URL
now redirects to the [LOC rights guide](https://guides.loc.gov/p-and-p-rights-and-restrictions/rights#723_marg.html).
The guide initially shows a loading placeholder: its published page script reads
[this public rights table](https://guides.loc.gov/ld.php?content_id=76336558).
Following that publisher-provided data reference required no account, API key or
alternate network route.

The retained table is **1,105,202 bytes / 689 statements**, SHA-256
`3c7ad29bc2ad742dc3b0b37145b71ce9b3aadeab19bbbdc359b2190a22b9f43c`.
Exactly one row matches the archive: ID `723_marg.html`, title **John Margolies
Roadside America Photograph Archive**, prepared by the Prints and Photographs
Division and last revised April 28, 2017. That row explains that LOC purchased
photograph intellectual-property rights with the archive and reports no known
copyright restrictions. It separately cautions about privacy/publicity rights
and copyright in depicted sculpture or artwork. This is the archive-specific
statement; the generic redirect alone did not establish it.

The table contains invalid UTF-8 in an unrelated record. Parsing preserved those
bytes with surrogate escapes; every field of the selected Margolies row passed
strict UTF-8 validation. No bytes were silently discarded or replaced. Original
bytes, page/data receipts and the selected statement are retained outside Git.
No photographs, depicted artwork or descriptive website prose are imported.
The mirror's CC0 metadata label is not relabeled as a blanket LOC CC0 grant.

## Current arrival review

The authentic Kaggle CSV contains historical leads for Teapot Dome (index 1),
Corn Palace (including index 279), Blue Whale (including index 2404), and Cabazon
Prehistoric Museum (including index 2450). Multiple photographs are not multiple
destinations. Titles/year/image references contain no arrival coordinates and do
not establish current operation or the current location of moved structures.

A bounded official Overture source inspection near Corn Palace read 135 source
features / 191,225 decoded bytes and matched two names. One is the gift shop,
which must not replace the attraction. The other is the venue at the published
physical street address, with source identity
`bb5dda13-ffd0-4791-8715-7b82aed55d42`, source open status and confidence about
0.920. Its source category is `stadium_arena`, outside the conservative Overture
admission taxonomy. That original feature/category remains intact. The separate
`kaggle-loc-roadside-arrivals/1` adapter's explicit `corn-palace/1` profile verifies
the historical identity, original coordinate provenance, current public visitor
address and driving frontage before assigning a roadside category. The generic
Overture taxonomy has not been broadened. No coordinates were guessed.

The canonical official [Corn Palace visitor page](https://www.cornpalace.com/31/Visiting)
and [parking page](https://www.cornpalace.com/173/Parking) now both returned HTTP
200 to ordinary downloads, with original snapshots retained. They document public
visiting at 604 North Main Street and parking a short walk away. An ordinary
Mapbox driving check placed the unchanged licensed point 16.262 metres from
North Main Street. The point role is **venue frontage at the published visitor
address**, not car-park coordinates or a guarantee of future availability.
The gift shop at 603 North Main Street is excluded.

The adapter pins the actual 11,710-row CSV and current source evidence with
bounded reads. Twenty-six matching photo records collapse to `kaggle-loc:279`;
25 are alternate references, and 11,684 other historical records remain outside
this site review. It retains the native Overture ID, upstream licenses, LOC
archive notice and CC0 metadata notice. Arbitrary normalized rows and unreviewed
site profiles are refused. Current visitor/parking evidence must be no more than
30 days old. Closure, wrong venue/address, uncertain rights or failed driving
checks prevent staging. No opening schedule is invented.

`scripts/catalog_roadside_manifest.py --bundle <retained-bundle.json>` validates
the original evidence and writes a new sidecar without downloads/database calls
or overwriting an existing sidecar. `scripts/catalog_mix.py` re-admits that child
alongside the other original source artifacts. The regional combiner still
accepts Overture inputs only.

## Recovery and remaining leads

The separate local generation contains **70 unique arrivals across 24 states**:
one roadside, 12 nature, 12 beaches, eight museums and 37 national parks. No
eligible entertainment or landmark batch has been added. Its immutable
generation is `7c5bc43052ab34703ca890563a1c5a427dcc2ff426b135a9e38e13f4a92302df`,
manifest SHA-256 `2de2c789b169f2fad016eeb8d9c73f372ccaafb2e136ec1f43ad0a5b6d51ad69`.
The 69-arrival baseline and 70-arrival generation occupy 425,984 indexed catalog
bytes in an isolated PostgreSQL 18.6 database. Idempotent staging, activation,
rollback (Corn Palace disappears), and return to the final generation pass.

The 32,021-byte custom dump has SHA-256
`25435cdf04e01a3af30b0d0a3e11cf754f320b9ce68a815052336a1c9d6983df`.
An empty separate database restored all three tables, exact row-content digests
and active pointer. Actual legacy, persona and evening discovery adapters return
`kaggle-loc:279` while HTTP request/send transports raise on use: zero HTTP and
Tripadvisor discovery calls. The original 400-record evaluation database's table
digests and active pointer were checked unchanged. These are local results.

Full validation passed: 922 backend tests including five real PostgreSQL cases,
87.54% application coverage above the unchanged 63% floor; 314 frontend tests,
90.23% line coverage, format/lint/build. Twenty synthetic roadside cases cover
uncertain evidence, wrong venues, native identity, rights, closure, driving
checks, bounded input, mixed revalidation and regional-combiner refusal.

The current [Zillah city page](https://www.cityofzillah.us/visitors/zillah_teapot.php)
confirms the Teapot moved to 117 First Avenue in 2012; its historical highway
address must not become today's arrival. Current place-specific schedule and
practical coordinate review remain open. Catoosa's publisher returned 403, so
that access attempt stopped. City-office hours do not describe Blue Whale access.
The [Cabazon publisher](https://www.cabazondinosaurs.com/) gives visitor facts
but states restrictions on commercial use of names/media; its rights and practical
arrival require further review. Neither lead is imported.

Sixteen current primary visitor/parking pages were retained for candidate review.
The [Museum of Illusions Denver contact page](https://moidenver.com/contact-us/)
reports a temporary closure, corroborated by its FAQ. That candidate is withheld
from the usable bundle even though its older Overture status says open. Other
reviews retain off-site parking, entrance ambiguity, party/activity restrictions
and unknown future access explicitly. The 331 evaluation candidates are not
promoted as a group. Category/corridor gaps and the roughly 500-place goal remain
open; production recovery, review and release gates still apply.
