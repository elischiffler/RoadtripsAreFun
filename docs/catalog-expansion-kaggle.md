# Licensed Kaggle expansion: 557-place review candidate

This proposal adds **57 distinct destinations** to the preserved 500: **46
farmers markets, nine entertainment venues, one museum and one roadside stop**.
All 500 original normalized fields and provenance remain identical. The complete
replacement generation retains the prior catalog for rollback. This PR performs
no production mutation; independent parent review precedes merge and activation.

The batch follows verified capacity and authentic source admission. Current Neon
allowance, usage, row/index measurements and guarded cutover statements are
recorded privately. Capacity permits substantially larger catalogs. Source rights,
identity, current visitor evidence and practical arrivals limit this batch. The
**50,000 source rows / 100 MiB**, **256 MiB catalog** and **512 MiB database**
guards are unchanged. The complete recipe scans **29,751 primary source records**,
admits **557**, and accounts for **91,647,833 bytes** of retained input/evidence.
Canonical, government roster and address corroboration feeds have separate pinned
counts and bounds. The explicit accepted-row budget is 20,000; no guard is raised.

Reviewable artifacts:

- [57 admitted normalized rows](data/catalog-expansion-kaggle-20261015/additions.preview.jsonl)
- [All 8,863 market source decisions](data/catalog-expansion-kaggle-20261015/market-source-admission-ledger.json)
- [101 market candidates and address corroboration](data/catalog-expansion-kaggle-20261015/market-coordinate-review.json)
- [All 2,105 park source decisions and reviewed holds](data/catalog-expansion-kaggle-20261015/park-source-admission-ledger.json)
- [Selected OSM arrival evidence, under ODbL](../frontend/public/catalog-osm-arrivals.json)
- [Validation and actual discovery measurements](evidence/catalog-expansion-kaggle-20261015.json)

## Sources and reuse rights

| Kaggle source | Pinned version and original archive | Admitted use |
| --- | --- | --- |
| [Harvestly U.S. Farmers Markets by State 2026](https://www.kaggle.com/datasets/harvestlymarkets/us-farmers-markets-by-state-2026/versions/4) | v4; 1,644,837 bytes; SHA-256 `dea363d2a400f008fa28c933dc6816af2bb7166bea5e5795adc9ec79989d30b1` | 46 markets: CA 45, VT 1 |
| [Ride in Park: Theme Parks of the World](https://www.kaggle.com/datasets/rideinpark/theme-parks-of-the-world/versions/1) | v1; 193,076 bytes; SHA-256 `5d611038b0e8ec2c1ed9a75d3e28822e8080eb6f8d6de7c9a0504501c9960059` | 11 destinations: CA 2, FL 5, MO/OR/TN/TX 1 each |

Harvestly's [own reuse and source notice](https://harvestlymarkets.com/data-sources/)
grants CC BY 4.0, credits USDA, and identifies native USDA coordinates. Its
October 11 corrected snapshot corroborates membership and unchanged locations;
it does not replace the Kaggle input. Blank seasons or enrichment flags never
establish operation. Source descriptions are omitted, including editorial content
present despite the publisher's exclusion notice.

Ride in Park's compilation uses CC BY 4.0. Each selected native Q identity and
coordinate is independently corroborated against current
[Wikidata structured data under CC0](https://www.wikidata.org/wiki/Wikidata:Licensing).
The publisher does not identify the provenance of every field; unverified prose,
attendance, images and other fields are omitted. Current operator sources supply
separate visitor facts. An uploader label alone is insufficient.

Census address-range corroboration has its own
[government factual-data notice](../frontend/public/licenses/LicenseRef-US-Census-Geocoder.txt).
OSM road, parking and entrance evidence retains native element IDs, source
receipts, changes and **ODbL 1.0** attribution. The selected factual subset is
published with the frontend; operator HTML/images remain private audit evidence.
Existing source/license files are unchanged. Frontend attribution identifies
filtering and classification changes, with no endorsement or warranty implied.

## Bulk admission and location corrections

The market producer re-extracts original government PDF tables with pinned
optional source dependencies. Ordinary import preparation requires no PDF library
or network. It checks immutable originals, exact extracted rows, canonical
membership, literal names/streets/cities and separately attributed seasons from
**every** feed. Official visitor records are the
[October 1 CDFA registry](https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf),
[Connecticut's 2026 list](https://portal.ct.gov/doag/-/media/doag/adarc/farmers-markets/2026/2026-farmers-markets-and-farm-stands.pdf),
[Delaware's 2026 guide](https://agriculture.delaware.gov/communications-marketing/farmers-markets-guide/)
and the [Burlington operator](https://burlingtonfarmersmarket.org/).
USDA portal and Vermont state-page HTTP 403 responses were respected.

An independent official Census batch checks all 101 preflight market candidates
using **202 genuinely published address forms**, benchmark **8 / Public_AR_ACS2026**.
Every successful form participates: exact city/state/native ZIP, literal street
agreement, no official ZIP conflict and no result more than **100 metres** from
the native point. A convenient match cannot override another conflicting match.
Tie/No_Match alone stays unknown. Census interpolates address ranges; its points
never replace the unchanged Kaggle coordinates or establish surveyed entrances.

This holds **55** preflight markets: 23 excessive distances, 17 official ZIP
conflicts, seven without a literal unambiguous match, four returned component
conflicts, two known wrong native points and two unresolved shared-arrival rows.
East Palo Alto and California Avenue's native points disagree with their address
results; the latter differs by about 4.9 km. Two Paso Robles records share the
same point/address despite different weekly calendars. Both are held. Seymour CT
returns Tie; Lewes DE's fall address is about 275 metres from its native point.
CT/DE remain empty. Summer and fall Lewes facts remain separately retained.

Market collision checks and complete-catalog proximity review use a bounded
3-D spatial grid, including poles and the antimeridian. Unresolved shared arrivals
cannot inflate the batch. The remaining nearby pair, Fun Spot Kissimmee and Old
Town at 190.46 metres, has different operator addresses and genuinely separate
admission/directions; neither is a company-level duplicate.

The park adapter verifies pinned source, Wikidata, original operator pages/maps,
actual OSRM destination bytes, and public road/parking/building geometry. A street
snap alone is insufficient. **Seven** preflight points are held: LEGOLAND,
Discovery Cove, Snow King, SkyPark, Balboa, Castle Park and Santa Cruz Boardwalk.
Their native points are interior, inconsistent with the published arrival, or
associated with different/closed components. Coordinates are never repaired by
inventing or substituting an entrance.

Confusion Hill admits its Gravity House while separately retaining the seasonal
train and conflicting snack-bar statements; neither component is admitted. All
other source restrictions remain separately attributed. Current date, weekday,
season and the existing **30-day** source freshness gates still apply. Genuine
acquisition and review are required to refresh evidence; editing dates is invalid.

Markets are daytime **food destinations**, not restaurant `food` query-group
entries. They cannot enter evening restaurant results. Three new entertainment
venues support evening discovery. Published hours/restrictions remain source
facts; scheduler intervals, prices, parking availability, future operation and
market-day vehicle entry remain explicit unknowns. Actual Windows execution is
unperformed; filenames and producers use portable paths, UTF-8 and LF.

## Coverage and unresolved sources

| Exclusive reporting category | Preserved 500 | Proposed 557 |
| --- | ---: | ---: |
| Nature | 287 | 287 |
| Historic/landmarks | 122 | 122 |
| National parks | 38 | 38 |
| Museums | 30 | 31 |
| Beaches | 12 | 12 |
| Food destinations | 5 | 51 |
| Entertainment | 4 | 13 |
| Roadside | 1 | 2 |
| Nightlife | 1 | 1 |

Exclusive reporting counts each place once. Overlapping nightlife query groups
increase from **two to five**; the original bowling venue already belongs to that
group. Coverage reaches **48 states plus DC**, adding Vermont. California has
90 entries. CT/DE, sparse corridors and beach/roadside/nightclub gaps remain.
This is not nationally sufficient coverage or additional restaurant coverage.

All six requested missing areas were searched on Kaggle. No new scalable,
licensed, current beach or general museum destination feed was established.
The one added museum is an individually reviewed Ride in Park record. Sources
were not silently substituted:

| Candidate | Hold |
| --- | --- |
| [IMLS museums v1](https://www.kaggle.com/datasets/imls/museum-directory/versions/1) | Retired source; commercial contributor/geocoding rights cannot be separated in the mirror. |
| [SF beach water v1](https://www.kaggle.com/datasets/jboysen/sf-beaches-water/versions/1) | Historic measurement/station codes without destination coordinates or arrivals. |
| [California Coastal Trail v1](https://www.kaggle.com/datasets/artemiosgeromitsos/california-coastal-trail-cct/versions/1) | Reuse rights and public arrival suitability unresolved. |
| [LOC roadside photo metadata v4](https://www.kaggle.com/datasets/headsortails/us-roadside-attractions-photographs/versions/4) | Historical subjects lack coordinates/current arrivals. No photos imported. |
| [Rollercoasters v2](https://www.kaggle.com/datasets/robikscube/rollercoaster-database/versions/2), [RCDB v13](https://www.kaggle.com/datasets/mcpenguin/rollercoasters/versions/13) | Ride-level stale data and unresolved upstream rights. |
| [Top clubs v2](https://www.kaggle.com/datasets/bhavyadhingra00020/top-100-night-clubs-2024/versions/2) | DJMag scrape, unresolved upstream grant and no native coordinates. |
| [US breweries v1](https://www.kaggle.com/datasets/brkurzawa/us-breweries/versions/1) | Stale scrape, no coordinates or established upstream redistribution grant. |
| [US Local Business Atlas v1](https://www.kaggle.com/datasets/valeriiserko/us-local-business-atlas/versions/1) | Actual files contain aggregate counts, not venue-level records. |

The private reproducible source/research bundle retains metadata, primary rights
evidence, selected originals and full rejection reports. Public previews omit raw
operator text, images and personal contact columns. No credentials, saved-trip
data or production operational metadata are included in this PR.

## Actual PostgreSQL discovery and release checks

These are actual five-mile repository queries along the same retained real
driving geometries used for the 500-place comparison:

| Corridor | 500 daytime hits | 557 daytime hits |
| --- | ---: | ---: |
| LA–San Diego | 0 | 9 |
| SF–LA | 1 | 10 |
| SF–Boise | 2 | 4 |
| SF–Chicago | 4 | 6 |
| Ely–Reno | 0 | 0 |
| Seattle–Portland | 4 | 5 |
| LA–Phoenix | 2 | 9 |
| Olympic Peninsula | 7 | 7 |
| South Fork–Creede–Gunnison | 8 | 8 |
| Juneau local roads | 4 | 4 |

PostgreSQL 18.6 ran **2,166 bounded discovery queries per generation**. Local
expanded execution p95 was **0.74 ms**, compared with **0.90 ms** for 500; timings
include ordinary run variance and do not measure Neon/network latency. Full
query plans and row/index footprint are retained privately. Six typed probes
cover both source namespaces, CA/VT, museum/roadside/entertainment and evening
discovery. CT/DE probes explicitly remain absent. Provenance survives, scheduler
hours remain unknown, and markets are excluded from evening restaurant results.

Backend validation passes **1,256 tests / 87.29% coverage**, including six opt-in
real PostgreSQL cases. Market, park, proximity and release-SQL suites pass
59, 43, seven and five meaningful cases. Frontend format/lint, **319 tests /
90.23% line coverage**, and build pass; the existing large-bundle warning remains.
Exact-head remote checks and final portable replay have separate receipts.

Actual guarded staging, idempotence, activation, rollback and reactivation pass
against public data in disposable PostgreSQL. Wrong active generation, storage
ceiling, tampered content and bad cutover fingerprints fail atomically. Exact
custom dump/restore preserves all three catalog tables, including **1,057 rows**
across the 500 and 557 generations. This is local public-data recovery evidence,
separate from the production off-host recovery gate.

Nearby hits do not promise detours, itineraries, compatible hours or solver
success. The user's exact failing route is unknown. Browser saved-trip
verification remains pending; neither is claimed fixed.

## Rebuild and activation

Replay the immutable 500 source bundle, rebuild the two new source children with
`catalog_markets_manifest.py` and `catalog_parks_manifest.py`, then pass them to
`catalog_expansion_release.py` with the preserved 500 recipe. Producers refuse
existing outputs. `completion.json` appears only after source and preservation
checks. The canonical 557-row serialization SHA-256 is
`a96cb3e5a12020778d744c023d12f8c111c64162c31e4a9e4006b9dcee901c60`.

`catalog_expansion_discovery.py` accepts only a named disposable loopback PG18
database. `catalog_release_sql.py` compiles inert guarded staging and separate
activation/rollback transactions for authorized execution. They serialize catalog
mutation, reject unexpected generations/content, retain storage guards and
preserve all prior rows. Cutover/rollback changes only the active pointer.

The private version 1 source/review ZIP is **45,663,274 bytes**, SHA-256
`a580bf9449b5f37c8216e88035d05471d6b936579fd87c7a038bd460668d8176`.
Its code snapshot is `a2e7048ca623bba7e262d357e977f675275a0f6a`; subsequent
commits update documentation/evidence only. A fresh authorized Library download
matches those exact bytes. Fresh ZIP extraction verifies **823 inventoried files**
and replays all **557** rows with network/database connections forbidden. The
relocated recipe uses **91,650,476 bytes**, below the unchanged 100 MiB guard.
See the [portable replay receipt](evidence/catalog-expansion-kaggle-portable-replay.json).

The exact implementation also passes the network-disabled backend container
(**1,250 tests / 86.66% coverage**, six opt-in PG cases skipped), both running
container smoke tests and actual served license/OSM-evidence byte checks. The
full disposable CRUD/ownership, recreate, outage/readiness and backup/exact-restore
lifecycle passes, including populated-target refusal. Source and restore volumes
remain preserved. A local disk-space initialization failure was resolved by
reclaiming rebuildable cache before the successful full rerun. Standard Docker
builds and exact-head checks remain in remote CI.

Independent parent review is required before merge or activation. Then verify
current recovery freshness and exact restored backup evidence under existing
policy, exact-main CI, serialized deployment, unchanged expected generation,
atomic activation and live SHA/count/provenance discovery/health. Prior 500 is
the rollback target. Application rollback does not undo catalog activation.
No fresh-backup-per-activation rule, paid upgrade or safety-limit change is added.
