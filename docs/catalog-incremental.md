# Source calendars and nineteen licensed additions

This proposal preserves all **557 released places** and their original fields and
provenance, adds **17 New York farmers markets and two cultural destinations**,
and supplies **80 separately attributed calendar updates**. The complete candidate
contains **576 places**. Its companion table lets original source records remain
immutable. Saved trips and user tables are outside the import's write scope.
Independent parent review, exact-main checks and deployment precede activation.

The new cultural destinations are Watts Towers Arts Center's gallery campus in
Los Angeles and Philipse Manor Hall in Yonkers. Watts' gallery schedule does not
establish access to the separate guided towers. Philipse has only the affirmative
**October 31, 2026, noon–16:00** self-guided event window; unspecified holiday
closures prevent a perpetual weekly opening claim.

- [Nineteen normalized additions](data/catalog-incremental-20261015/additions.preview.json)
- [All 8,846 withheld market source records](data/catalog-incremental-20261015/ny-market-source-decisions.json)
- [All 71 cultural decisions](data/catalog-incremental-20261015/cultural-source-decisions.json)
- [Calendar decisions and remaining unknowns](data/catalog-incremental-20261015/calendar-source-decisions.json)
- [Coverage, limits and validation](evidence/catalog-incremental-20261015.json)

## Exact sources and admission

| Kaggle source | Version | Accepted here | Rights and corroboration |
| --- | --- | ---: | --- |
| [U.S. Farmers Markets by State 2026](https://www.kaggle.com/datasets/harvestlymarkets/us-farmers-markets-by-state-2026/versions/4) | 4 | 17 | Harvestly's own CC BY 4.0 notice and USDA provenance; unchanged native points, current canonical membership, New York agency identity/location/season facts under OPEN-NY terms |
| [Los Angeles cultural centers, theatres, sites and galleries](https://www.kaggle.com/datasets/cityofLA/la-cultural-centers-theatres-sites-galleries/versions/25) | 25 | 1 | City of Los Angeles publisher's CC0 compilation; original city registry and current operator facts |
| [NYS State Historic Sites](https://www.kaggle.com/datasets/new-york-state/nys-state-historic-sites/versions/9) | 9 | 1 | State publisher's CC0 compilation, current agency registry and OPEN-NY terms; affirmative operator event/access evidence |

The source bundle retains original archives, exact versions, publisher metadata,
upstream registries, licenses, terms and raw access evidence. Kaggle listing alone
never establishes reuse permission. Operator prose/images remain private evidence;
normalized rows use factual identities, native coordinates and attributed access
constraints. [Public attribution](../frontend/public/catalog-attribution.html)
and the selected [OSM factual subset](../frontend/public/catalog-osm-arrivals.json)
retain credits and licenses, including the two new public road ways under ODbL.

Every market must match the independent agency's normalized name, city, complete
numbered street and ZIP, with no alternate official address conflict. Native and
agency points must be within **100 m**, and an actual OSRM driving destination
within **75 m**. Every feed's seasonal restriction participates. Twenty-eight
prospects yield seventeen admissions after point, ZIP, location and arrival checks.
All 8,863 native market records receive an explicit accepted/withheld decision.

Cultural admission replays all 71 native records and both current registries.
The two retained native points agree with their current native identities; public
road geometry and operator arrival evidence establish practical access. Sixty-nine
other records remain held for incomplete access/calendar proof, component or
coordinate conflicts. A global 250 m spatial collision check compares additions
with every preserved source and with one another. Native IDs and coordinates are
never invented or replaced.

## Calendar gains and source conflicts

The 61 updates to existing places comprise **35 NPS facilities**, **11 venues**,
**nine positive recoveries from the prior eleven unknown entries**, **five USFS
facilities**, and **one expired-season correction**. The nineteen new places have
their own calendars, bringing the total to eighty. Weaverville's current operator
season ended October 14, conflicting with a later agency end date; the intersection
allows no upcoming October 15 visit. This correction is not counted as a gain.

Adapters retain each source's restrictions separately. Native schedules, current
pages, component differences, event exceptions, lunch breaks, party conditions and
last-entry limits are intersected rather than silently overwritten. For example,
Phoenix's inline dated event list participates alongside visible hours; its
November 13 member preview cannot become a public visit. GLBT's October 17 gala
closure remains effective. Closed-only calendars cannot occupy automatic discovery
slots before usable records. Expired seasons, sessions shorter than a full visit,
and fixed starts that cannot fit their source window are also rejected before
raw-pool, rating, discovery-completion and shortlist budgets.

Venue, market and most recovered/USFS evidence has a conservative dated review
scope of **October 15–November 13**. This is an interpretation policy, not a
source-published season or a promise of future operation. NPS calendars stop at
source boundaries or the end of the acquired source year; ambiguous exception dates
have no positive window. Prices, ticket inventory, reservations, actual parking
availability and unresolved hours remain explicit unknowns. Actual arrival IANA
zones and complete two-hour dwell remain hard runtime requirements.

The companion is generation-scoped and immutable. Repository discovery joins it
before its bounded result limit and projects its effective calendar while keeping
superseded source facts separately attributed. Later additive calendar credits
cannot replace a place's original primary attribution.

Automatic planning supplies a request-local departure instant and resolves each
timed candidate's own IANA zone. It checks whether any permissible trip day has a
complete two-hour source window. PlanOptions has no trip end date, so this
necessary check uses the scheduler's existing sixty-overnight bound; it does not
promise that an itinerary can reach the place on that day. Future seasons and
later trip days remain eligible. Actual scheduling and final road timing retain
their stricter full-dwell checks. Database reads use distance/source-ID keyset
pages of at most sixty rows, pinned to one immutable generation. Rejected rows
consume no usable result slots, even when activation occurs between page reads.

## Capacity, coverage and measured discovery

The unchanged import accounts for **45,764 source records and 79,470,070 bytes**,
below **50,000 rows / 100 MiB**. The 32 KiB manifest, 256 MiB catalog and 512 MiB
database guards also remain unchanged. Actual Neon allowance, current usage and production
row/index measurements are verified in private release evidence. Capacity permits
substantially more places. Suitable licensed records with practical arrival and current source
contracts are the present constraint; 500 is not a cap.

Query categories overlap: **63 food destinations, 33 museums, 12 beaches,
10 amusement parks, five nightlife records and two roadside attractions**. There
are also five restaurant records; markets do not enter restaurant evening queries.
No new beach or evening category record is admitted in this proposal. Connecticut
and Delaware remain empty, and Vermont retains its one released market. Separate
research has five Chicago shore candidates and eleven California alternative-address
proposals; neither is included here or treated as a completed admission.

Actual application discovery was exercised in disposable PostgreSQL 18 against
retained real OSRM route geometries. Every query uses the five-mile/60-result
bounds and full calendar eligibility. Across **1,083 queries per generation**, the
final p95 was **2.64 ms** on loopback. SF–LA eligible hits increase
**8 → 10**, SF–Boise **1 → 4**, SF–Chicago **2 → 5**, Seattle–Portland **0 → 3**,
and LA–Phoenix **8 → 9**. LA–San Diego remains **9 → 9** and Ely–Reno remains
**0 → 0**. These are structural catalog eligibility counts, not evidence of opening on a
particular trip date, jointly feasible itineraries or production-provider latency.
Weaverville retains a faithful expired-season calendar and has zero supported
windows in the current review period; its source contract never establishes an
upcoming visit. Final evidence pins exact code and query timings.

## Staging and recovery

Apply the additive [companion DDL](../backend/sql/places_catalog_calendars.sql)
before deploying the enrichment-aware API. Production DDL compatibility and the
current active pointer must be inspected separately. The importer defaults to
validation only. Staging clones the verified parent and inserts typed additions,
metadata and companion facts in one transaction, preserving the active pointer.
Activation verifies complete parent/candidate rows, metadata and calendars before
an atomic pointer-only transition. Actual source preparation retains freshness
checks and unchanged limits.

After verified staging, `--freeze-rollback` emits a bounded recovery receipt of
actual PostgreSQL fingerprints. Save and independently pin its SHA-256. Recovery
uses that receipt instead of re-admitting source data:

```sh
python scripts/catalog_incremental_import.py artifact/catalog.enrichment.json
python scripts/catalog_incremental_import.py artifact/catalog.enrichment.json --target local --stage
python scripts/catalog_incremental_import.py artifact/catalog.enrichment.json --target local --freeze-rollback > rollback-receipt.json
python scripts/catalog_incremental_import.py rollback-receipt.json --target local --rollback --receipt-sha256 REVIEWED_SHA256
```

Rollback checks both immutable generations' full row/metadata/companion
fingerprints and preservation of all parent source facts, then restores only the
parent pointer. It needs no source connection or freshness extension. Both the
released 557 and original 500 remain available as reviewed rollback generations.
No saved-trip or user-data deletion is part of staging, activation or recovery.

The private portable bundle includes the unchanged released557 source archive,
all new originals, source adapters and offline replay. Historical replay after
source expiry is isolated from database access and cannot authorize current
admission. Actual Windows execution, live browser saved-trip verification and the
user's still-unknown failing route remain unverified.
