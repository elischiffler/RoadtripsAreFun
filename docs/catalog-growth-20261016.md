# Twenty-seven additions and forty-two further source calendars

This proposal preserves every raw field and original attribution of the **576
released places**, adds **22 farmers markets and five Chicago beaches**, and
supplies **42 further NPS facility calendars**. The complete candidate has **603
places and 149 generation-bound calendar companions**, including all eighty
released companions. It awaits independent parent release clearance and exact-head
release gates. Saved trips and user tables are outside the import's write scope.

- [Twenty-seven normalized additions](data/catalog-growth-20261016/additions.preview.json)
- [California market decisions](data/catalog-growth-20261016/ca-market-decisions.json)
- [New York market decisions](data/catalog-growth-20261016/ny-market-decisions.json)
- [All Chicago facility decisions](data/catalog-growth-20261016/coastal-decision-ledger.json)
- [Chicago beach-specific holds](data/catalog-growth-20261016/coastal-beach-rejection-ledger.json)
- [NPS calendar decisions and holds](data/catalog-growth-20261016/nps-calendar-decisions.json)
- [Measured coverage, resource use and PostgreSQL proof](evidence/catalog-growth-20261016.json)

## Sources, rights and admission

| Kaggle dataset | Exact version | New places | Independent provenance and rights |
| --- | --- | ---: | --- |
| [U.S. Farmers Markets by State 2026](https://www.kaggle.com/datasets/harvestlymarkets/us-farmers-markets-by-state-2026/versions/4) | 4 | 11 CA + 11 NY | Harvestly's original CC BY 4.0 compilation and USDA provenance; exact canonical membership; current CDFA and New York agriculture visitor facts; OPEN-NY terms apply separately to its registry facts |
| [Chicago parks locations, facilities and features](https://www.kaggle.com/datasets/chicago/chicago-parks-locations,-facilities-features/versions/15) | 15 | 5 | Archived and current official Chicago metadata independently identify Chicago Park District factual data as PUBLIC_DOMAIN; current official park/beach access corroboration |

Kaggle labels alone do not establish reuse rights. Original archives, exact
versions, upstream registries, reuse notices, source bodies and hash receipts are
retained in the private portable source bundle. Published factual identities,
locations and schedules are used; PDF artwork, photographs and website creative
prose do not become destination fields. OPEN-NY's grant is not extended to the
regional PDF publications. [Public attribution](../frontend/public/catalog-attribution.html)
retains the source-specific grants and factual corroboration. The new, separately
published [coastal OSM derivative](../frontend/public/catalog-osm-coastal-arrivals.json)
uses ODbL; the previously released OSM derivative is preserved unchanged.

Every new market has an unknown native street field. This remains explicitly
unknown. The adapters independently verify all genuine published alternative
visitor-address forms against retained Census results. A successful form with
conflicting city, ZIP, nonliteral street or a point more than 100 m away vetoes
admission; a convenient passing form cannot override it. Native market points,
IDs, ZIP unknowns and source-update unknowns are preserved. Current public market
classification, fixed visitor location, all-source seasons and a complete two-hour
session are required. Actual OSRM destination arrivals must remain within 75 m.

California admission replays the complete 8,863-row Kaggle feed, 7,947 canonical
rows and 768 original CDFA PDF rows, plus all 225 genuine address queries/results.
New York also replays all 675 OPEN-NY rows and all 62 original regional PDF pages,
132 retained text columns and 124 genuine address queries/results. It holds all
35 specifically requested short mobile stops; 42 short-window records across the
full New York feed fail the complete two-hour requirement. Unknown native streets
are never filled using Census interpolation or agency addresses.

Chicago admission replays all 4,152 facility and 581 park-metadata rows. Five
native BEACH points uniquely reconcile with publisher-native GISOBJID identities:
Helen Doria, Marion Mahony Griffin, Lane, Leone and Rainbow. The native points are
unchanged. General shore access is 06:00–23:00, corroborated independently by the
current beach and park sources. Swim hours, ended 2026 swimming season, fieldhouse
clocks and closures remain separate restrictions; swimming eligibility is false.
Rogers, Fargo and Howard remain held for erosion closures. Oak Street is held
because the actual snap targets a motorway ramp despite meeting the distance
limit. Other unproved public arrival, component and campus identities remain held.
Source addresses and update dates remain unknown when absent.

Every addition is compared against all 576 parents and every other addition using
stable identities and the existing 250 m spatial collision guard. No collision
remains; the closest parent/addition or addition pair is 317.78 m apart. Rows are
not merged into or substituted for existing source identities.

## Calendar enrichment and remaining gaps

Forty-two additional NPS calendars use current original visitor-facility bodies
and four corroborating sources. The offline transformer compares native parent
hours, selected component tables, visible prose, holidays, lunch breaks and
closures. Its 45 held facilities and fourteen ambiguous dates receive no positive
availability. These calendars contain only explicitly dated 2026 windows through
December 31, without a 2027 or perpetual weekly fallback. Cabrillo, Giant Forest
and Lava Beds are among the California recoveries. The prior NPS/Kaggle place
identity and primary attribution remain unchanged.

The 27 additions have their own companions, giving 69 new updates and 149 total
companions. Market review policy remains October 15–November 13, with narrower
source seasons intersected. It is not a publisher's promise of operation. The
prior faithful expired Weaverville correction remains withheld for future trips.
Unknown prices, reservations, inventory and parking availability remain unknown.
Runtime discovery and final scheduling keep the existing candidate-local IANA and
complete two-hour checks; no scheduling limits are relaxed.

Overlapping query categories now include **85 food destinations, 17 beaches, 33
museums, ten amusement parks, five nightlife records and two roadside attractions**.
There are still five restaurant records; farmers markets do not enter restaurant
evening searches. CT and DE remain empty and VT retains one released market.
This batch supplies no new museum, amusement, unusual roadside or evening venue.

Separate licensed bulk research reconciled a 9,038-identity Kaggle brewery feed
with the primary Open Brewery DB MIT dataset and found 4,826 strict US source
candidates. None is admitted: present operator calendars, public arrivals and
identity conflicts still require evidence. Fifty-six CT/DE/VT native arrivals
were acquired, without converting road snaps into public access claims. Subsequent
Kaggle searches returned HTTP429 and were stopped. No suitable scalable source
for every missing category was established, and roughly 2,500 useful places is
not claimed complete. Source evidence, rather than verified database capacity,
currently limits further admissions.

## Resource use and actual PostgreSQL verification

The current import charges **45,005 source units and 52,019,955 bytes**, below the
unchanged **50,000 rows / 100 MiB** limits. Shared feeds are conservatively charged
again when independently replayed by separate adapters. Chicago's 4,733 primary
rows and its auxiliary current registry, OSM nodes/ways/relations and route bodies
are separately reported; every retained input byte is charged. The 32 KiB manifest,
256 MiB catalog and 512 MiB database guards remain unchanged. Actual production
allowance, current storage and retained generations are verified privately; no
upgrade or safety-limit change is needed for this proposal.

Actual disposable PostgreSQL 18.6 stores all 603 normalized records and all 149
companions. The 27 new composite rows occupy 100,588 measured datum bytes; the
candidate's companion composite data occupies 773,796 bytes. Physical catalog
tables/indexes across retained local generations occupy 11,583,488 bytes, including
999,424 bytes of place indexes and 65,536 bytes of companion indexes. Composite
datum sizes are not per-generation physical allocation estimates.

All eligible native-point queries return complete matching provenance and source
companions. Across 1,083 bounded corridor queries per generation, candidate p95 is
3.34 ms on loopback; candidate native-point p95 is 4.22 ms. These measurements
include application transport/deserialization and do not establish production
latency. Retained real OSRM route geometries give:

| Corridor | Released 576 | Proposed 603 |
| --- | ---: | ---: |
| LA–San Diego | 9 | 10 |
| SF–LA | 10 | 11 |
| SF–Boise | 4 | 5 |
| SF–Chicago | 5 | 7 |
| LA–Phoenix | 9 | 10 |
| Seattle–Portland | 3 | 3 |
| Ely–Reno | 0 | 0 |

These are structurally eligible source catalog hits within the existing five-mile
query radius and sixty-result bounds. They do not prove actual arrival-time
opening or a jointly feasible personalized itinerary. Stored-calendar arithmetic
passes 6,058 full two-hour acceptances, 3,029 one-minute-late rejections, 1,318
no-window date rejections and 221 explicit closed-date rejections. The aggregate
arithmetic uses a clearly labeled artificial UTC test zone; independent source
tests exercise explicit local IANA zones separately.

Backend validation passes 1,799 tests, with 56 optional PostgreSQL tests skipped
in that run and 82.20% coverage. A separate actual PostgreSQL run passes all 34
selected catalog and release-SQL regressions. Frontend format, lint, 319 tests
(90.23% coverage) and production build pass. Scoped independent source reviews
pass. Compiled, frozen SQL was executed twice for staging, activation and rollback
in a second newly created disposable PostgreSQL database, preserving all eighty
parent companions and all raw parent fields. Staging keeps the parent pointer;
the frozen receipt enables source-independent pointer rollback.

## Release boundary

No production write or activation of this candidate is authorized by this PR.
The parent must independently review the exact head and private source/SQL bundle,
then clear the release. Exact-main required checks, the established deployment
workflow, live revision/health checks, no-competing-writer inspection and the real
recovery freshness gate precede any atomic activation. No new backup-per-activation
rule is introduced. The 576 parent and earlier 557/500 generations remain rollback
targets. Catalog SQL never writes saved trips or user tables.

The portable bundle retains the unchanged released 576 source archive, this
import's authentic sources, full reviewed source snapshot, independent replay and
private SQL evidence. Windows-safe file names do not establish actual Windows
execution; the standalone NPS descriptor-based source replay explicitly requires
POSIX. Actual Windows execution, browser saved-trip verification and the user's
still-unknown failing route remain pending.
