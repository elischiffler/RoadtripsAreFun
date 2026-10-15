# Licensed Kaggle expansion: 557-place source-calendar review candidate

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
venues support optional evening discovery; unverified suggestions remain unscheduled.
Published source calendars now constrain automatic timed visits. Prices, ticket
inventory, reservations, parking availability, future operation and market-day
vehicle entry remain explicit unknowns. Actual Windows execution is
unperformed; filenames and producers use portable paths, UTF-8 and LF.

## Hard source-calendar constraints

The review correction adds a separate CP-SAT temporal model with hard opening
windows and full **7,200-second** policy dwell. It permits waiting for a published
opening within the travel day's cutoff. A conflict removes that candidate and
reselects from the same bounded, road-checked pool. Actual final Mapbox legs run
the same hard calendar check; a later arrival triggers bounded reselection and
rerouting. There is no hours penalty that can permit a closed visit, nor a blanket
market exclusion. This remains staged selection/scheduling, not joint global
optimization of hotels, travel days and every alternative attraction order.

Weekdays, intersected native/canonical/operator seasons, exact dated overrides,
annual closures, overnight windows and local IANA/DST clocks participate. Verified
fixed starts constrain allowed starts **inside** a containing published window;
a start alone cannot establish the visit's end. Each solved window retains its
source receipts. The two-hour duration is existing planner policy, not a source
claim or a booking. Saved and date-overridden itineraries revalidate, retain the
window proof and display any wait. Timed stops require an explicit arrival IANA
zone; inheriting the origin zone is insufficient.

**41 markets and five parks have usable calendars; five markets and six parks
remain explicit unknowns.** The five park calendars cover Belmont, Dezerland,
Dinosaur World Florida, Old Town and Gatorland. South Berkeley, Cambria, Fortuna,
Lancaster and Weaverville have unresolved clock forms/qualifiers. NASCAR's dated
calendar images, Oaks' exact season/holiday rules, Precious Moments' component
admission cutoff, and clocks for Confusion Hill, Fun Spot and Kemah remain unknown.
All 57 rows remain in the raw catalog, but these 11 records cannot become automatic
timed stops. Existing food/culture/nightlife candidates also require usable
source calendars: **163** original records currently lack one and are withheld
from new automatic selection. The other **337** ordinary outdoor legacy records
retain explicitly unknown opening hours and are never labeled verified-open.
All original 500 normalized records and saved trips remain preserved.

Authentic Burlington source facts require Saturday **09:00–14:00**, intersected
with native June–October and operator 2026 dates. Thursday October 15 at 10:00,
Saturday October 17 at 16:00, and a Saturday 13:00 two-hour visit are rejected.
Saturday 10:00 is accepted; an 08:00 arrival waits until 09:00. These results pass
both focused routing tests and typed discovery from actual PostgreSQL. Broader
regressions cover full dwell, unknowns, closure/season precedence, midnight,
multiday hotel restart, changed local dates/timezones, DST, omitted saved policy,
fixed event starts and final actual-leg reselection. See the
[calendar proof receipt](evidence/catalog-source-calendars-20261015.json).

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

These are actual five-mile **raw catalog** repository queries along the same
retained real driving geometries used for the 500-place comparison. They are
not counts of schedule-feasible stops; calendar gates apply afterward:

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
expanded execution p95 was **0.79 ms**, compared with **0.78 ms** for 500; timings
include ordinary run variance and do not measure Neon/network latency. Full
query plans and row/index footprint are retained privately. Six typed probes
cover both source namespaces, CA/VT, museum/roadside/entertainment and evening
discovery. CT/DE probes explicitly remain absent. Provenance and normalized
calendars survive, and markets are excluded from evening restaurant results.
Among added raw hits, nine LA–San Diego records and eight SF–LA records have
usable calendars; their chosen visit dates/times still require a feasible solve.

Backend validation passes **1,374 tests / 87.75% coverage**, including seven opt-in
real PostgreSQL cases. Calendar-focused routing regressions pass **30** cases;
market/park source-calendar and adapter suites pass **122 / 64** cases.
Proximity and release-SQL suites retain seven and five meaningful cases.
Frontend format/lint, **319 tests / 90.23% line coverage**, and build pass; the existing large-bundle warning remains.
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

## Automatic discovery eligibility correction

Independent review found that unknown timed calendars could consume every
shortlist slot before the later selection filter. The corrected implementation
filters them before raw/category pools, AI-rating budgets, discovery completion
and the shortlist. Automatic live SQL also applies a structural prefilter before
its unchanged 60-row limit, followed by strict application calendar validation.
The full-dwell CP-SAT and final actual-road checks remain active. Regression
fixtures cover 18 unknown timed records hiding an eligible outdoor stop,
refinement after an unknown-only first search, and 61 unknown SQL rows ahead of
two usable places. No source-admitted row or stable identity changes.

The [eligibility receipt](evidence/catalog-discovery-eligibility-20261015.json)
separates raw geographic hits from calendar-policy eligibility. The preserved
500 has **494 daytime records**, of which **337** pass this policy; the 557
candidate has **551 daytime records**, of which **383** pass: 46 timed records
with usable calendars and 337 ordinary outdoor records with unknown hours.
Six of the 163 withheld baseline records were evening-only already, so the
baseline daytime loss is 157. All 30 baseline museums are currently withheld.

| Corridor | 500 before policy | 557 before policy | 557 after calendar policy |
| --- | ---: | ---: | ---: |
| LA–San Diego | 0 | 9 | 9 |
| SF–LA | 1 | 10 | 8 |
| SF–Boise | 2 | 4 | 1 |
| SF–Chicago | 4 | 6 | 2 |
| Seattle–Portland | 4 | 5 | 0 |
| LA–Phoenix | 2 | 9 | 8 |
| Colorado scenic | 8 | 8 | 4 |

These counts isolate the calendar policy with controlled positive utility and
zero detour inputs. They are not full-trip selection promises. For example,
individual full two-hour timed visits after a controlled 10:00 local arrival,
with waiting allowed only until 20:00, are feasible for four LA–San Diego records
on Thursday October15 and two on Saturday October17. SF–LA has two and three,
respectively. The source-window models run in an explicit test IANA context;
actual provider timezones, road timing and joint trip scheduling remain required.
Outdoor unknown hours do not become verified-open. Actual SELECT-only filtered
PostgreSQL queries reproduce the policy-eligible IDs; local p95 is 0.86ms for500
and 0.94ms for557 across 1,083 queries each, without pointer changes.

Hours enrichment is being prepared separately, prioritizing Seattle–Portland,
SF–Boise and Colorado. Authentic NPS tables for all122 withheld NPS facilities,
current official venue pages and USFS factual feeds are retained privately.
A fresh Weaverville operator source ends its 2026 season October14, conflicting
with the retained CDFA October21 listing. It already remains excluded from
automatic selection; it cannot count as a recovered current-season calendar.
No prospective enrichment or the roughly2,500-place expansion target is admitted
by this PR or its source bundle.

## Rebuild and activation

Replay the immutable 500 source bundle, rebuild the two new source children with
`catalog_markets_manifest.py` and `catalog_parks_manifest.py`, then pass them to
`catalog_expansion_release.py` with the preserved 500 recipe. Producers refuse
existing outputs. `completion.json` appears only after source and preservation
checks. The canonical 557-row serialization SHA-256 is
`f09f0a85a5dbf0cf586c637ffeb99b1472a2098e75127fdc8ee7fb1b4ccf0ce2`.

`catalog_expansion_discovery.py` accepts only a named disposable loopback PG18
database. `catalog_release_sql.py` compiles inert guarded staging and separate
activation/rollback transactions for authorized execution. They serialize catalog
mutation, reject unexpected generations/content, retain storage guards and
preserve all prior rows. Cutover/rollback changes only the active pointer.

The private version 3 source/review bundle supersedes the calendar-blocked
version 1 and the discovery-starved version 2. Its immutable implementation snapshot is
`f3fe4b1cd6c5e8c2313922e7ec57a43c4487404c`; later commits update documentation
and evidence only. The [portable replay receipt](evidence/catalog-expansion-kaggle-portable-replay.json)
records the **46,878,068-byte** ZIP, SHA-256
`f89dbd292df2ee3169ab0a8cc50a80c86043769c91271f42fbc7cdc78d99d36a`,
fresh authorized Library download and **878-file** Windows-safe inventory. Fresh
extraction replays all 557 rows with network/database connections forbidden; the
relocated recipe uses **91,646,936 bytes**, within the unchanged guard.
Actual Windows execution is pending.

The exact implementation passes all four remote CI workflows, including standard
Docker builds and disposable PostgreSQL recovery. Its network-disabled backend
container passes **1,367 tests / 87.15% coverage** with seven opt-in PG cases skipped.
Local running-container and full CRUD/recovery gates have separate private receipts.
Initial local image-copy disk exhaustion was resolved by reclaiming unused build
cache and superseded task images; all database volumes and source artifacts remain
preserved. No production write was used to pass a local gate.

Independent parent review is required before merge or activation. Then verify
current recovery freshness and exact restored backup evidence under existing
policy, exact-main CI, serialized deployment, unchanged expected generation,
atomic activation and live SHA/count/provenance discovery/health. Prior 500 is
the rollback target. Application rollback does not undo catalog activation.
No fresh-backup-per-activation rule, paid upgrade or safety-limit change is added.
