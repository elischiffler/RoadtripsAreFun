# Licensed Kaggle expansion: 619-place review candidate

This proposal adds **119 distinct destinations** to the preserved 500: **101
farmers markets, 16 entertainment venues, one museum and one roadside stop**.
All original normalized fields and provenance remain identical. It prepares a
complete replacement generation; activating an increment alone would discard
the existing coverage. This PR performs no production mutation.

The batch follows measured capacity and authentic source admission, rather than
a 500-place cap. Current Neon allowance, usage and row/index measurements are
recorded privately. They permit substantially larger catalogs. The limiting
factor here is current rights, identity, location and visitor evidence. The
existing **50,000 source rows / 100 MiB**, **256 MiB catalog** and **512 MiB
database** guards are unchanged. The complete recipe scans **29,751** source
records, admits **619**, and accounts for **89,064,337 bytes** of retained input
and evidence. Its explicit accepted-row budget is 20,000; no guard is raised.

Reviewable artifacts:

- [119 new normalized rows](data/catalog-expansion-kaggle-619-20261015/additions.preview.jsonl)
- [All 8,863 market source decisions](data/catalog-expansion-kaggle-619-20261015/market-source-admission-ledger.json)
- [All 2,105 park source decisions](data/catalog-expansion-kaggle-619-20261015/park-source-admission-ledger.json)
- [Validation, coverage and query measurements](evidence/catalog-expansion-kaggle-619-20261015.json)

## Sources and reuse rights

| Kaggle source | Pinned version and original archive | Admitted use |
| --- | --- | --- |
| [Harvestly U.S. Farmers Markets by State 2026](https://www.kaggle.com/datasets/harvestlymarkets/us-farmers-markets-by-state-2026/versions/4) | v4; 1,644,837 bytes; SHA-256 `dea363d2a400f008fa28c933dc6816af2bb7166bea5e5795adc9ec79989d30b1` | 101 markets: CA 98, CT 1, DE 1, VT 1 |
| [Ride in Park: Theme Parks of the World](https://www.kaggle.com/datasets/rideinpark/theme-parks-of-the-world/versions/1) | v1; 193,076 bytes; SHA-256 `5d611038b0e8ec2c1ed9a75d3e28822e8080eb6f8d6de7c9a0504501c9960059` | 18 independently reviewed destinations: CA 7, FL 6, MO/OR/TN/TX/WY 1 each |

Harvestly's [own reuse and source notice](https://harvestlymarkets.com/data-sources/)
grants CC BY 4.0, credits USDA, and identifies native USDA coordinates. Its
October 11 corrected snapshot corroborates membership and unchanged locations;
it does not replace the Kaggle input. Neither API enrichment nor a blank season
is treated as verified operation. Source descriptions are omitted, including
editorial content present despite the publisher's exclusion notice.

The Ride in Park compilation uses CC BY 4.0. Each selected native Q identity and
coordinate is separately corroborated against current
[Wikidata structured data under CC0](https://www.wikidata.org/wiki/Wikidata:Licensing).
The publisher does not identify the provenance of every dataset field; no
unverified attendance, prose, images or other fields enter the catalog. Current
operator records supply separate visitor evidence. An uploader label alone is
insufficient. Attribution identifies filtering and classification changes, with
the license texts served by the frontend. OSRM driving evidence separately
credits OpenStreetMap contributors / ODbL.

## Admission and access

The market producer re-extracts original government PDF tables using pinned
optional source dependencies. The ordinary importer needs no PDF library or
network connection. It verifies immutable originals, exact extracted-table
hashes, current canonical membership, literal name/street/city agreements,
published weekdays and seasons from **every** feed, and genuine OSRM destination
responses within the unchanged 75-metre limit. Source coordinates are never
replaced by road snaps. Complex calendars and unresolved location shifts fail
closed. Matching ordinary records is bulk validation, with explicit profiles
only for the sparse-state exceptions.

Corroboration uses the [October 1 CDFA registry](https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf),
[Connecticut's 2026 official list](https://portal.ct.gov/doag/-/media/doag/adarc/farmers-markets/2026/2026-farmers-markets-and-farm-stands.pdf),
[Delaware's 2026 guide](https://agriculture.delaware.gov/communications-marketing/farmers-markets-guide/)
and the [Burlington market operator](https://burlingtonfarmersmarket.org/).
Lewes retains separate summer-park and fall-school-location statements. Only
the native 820 Savannah Road fall point is selected; the summer point is held.
USDA portal and Vermont state-page HTTP 403 responses were respected.

Markets are daytime **food destinations**, with `food_destination` rather than
the restaurant `food` query group. They cannot silently become evening restaurant
results. Their exact published market days/hours remain source restrictions;
scheduler intervals, prices, parking availability and future operation remain
unknown. Native market points are corroborated public destinations, without a
claim of a surveyed parking entrance or current vehicle entry during market hours.

The park adapter pins the archive, metadata and independent review profiles,
rechecks current Wikidata closure claims and each original operator/road receipt,
and applies admission-date, weekday or seasonal gates. Park visitor points and
parking evidence are distinguished. Four entertainment destinations also have
publisher-supported evening components and the `nightlife` query group.

Component restrictions remain separate: Confusion Hill's train is seasonal and
its snack-bar feeds conflict; neither is admitted. Castle Park's mini golf and
arcade differ from ride/water-park operation. Boardwalk rides are closed on the
snapshot day while arcade/bowling operate. LEGOLAND's water park is closed.
Snow King's evening/night operation and several seasonal activities are closed.
The complete separately attributed restrictions travel in provenance.

**Boardwalk and LEGOLAND admission relies on October 15 evidence and intentionally
fails replay after that date.** Snow King's reviewed season ends October 25.
Genuine acquisition and review are required when evidence no longer supports
admission. Editing a receipt date is not a refresh. The existing 30-day source
freshness guard remains active. Actual Windows execution is unperformed;
filenames and producers use portable paths, UTF-8 and LF.

## Coverage and remaining source holds

| Exclusive reporting category | Preserved 500 | Proposed 619 |
| --- | ---: | ---: |
| Nature | 287 | 287 |
| Historic/landmarks | 122 | 122 |
| National parks | 38 | 38 |
| Museums | 30 | 31 |
| Beaches | 12 | 12 |
| Food destinations | 5 | 106 |
| Entertainment | 4 | 20 |
| Roadside | 1 | 2 |
| Nightlife | 1 | 1 |

Exclusive reporting counts each place once. Nightlife discovery groups increase
from one to five, overlapping entertainment. Coverage reaches **all 50 states
plus DC**, including one market in each previously empty CT/DE/VT. California
has 148 entries. Regional concentration and beach/roadside/nightclub gaps remain;
this is not nationally sufficient coverage.

All six requested missing areas were searched on Kaggle. No new scalable,
licensed, current beach or general museum destination feed was established.
The one added museum is an individually reviewed Ride in Park record. Sources
were not silently replaced with unrelated datasets:

| Candidate | Hold |
| --- | --- |
| [IMLS museums v1](https://www.kaggle.com/datasets/imls/museum-directory/versions/1) | Retired source; commercial contributor/geocoding fields cannot be separated in the mirror. Existing rights hold remains. |
| [SF beach water v1](https://www.kaggle.com/datasets/jboysen/sf-beaches-water/versions/1) | Historic measurement/station codes, without destination coordinates or visitor arrivals. |
| [California Coastal Trail v1](https://www.kaggle.com/datasets/artemiosgeromitsos/california-coastal-trail-cct/versions/1) | Reuse rights and public arrival suitability unresolved. |
| [LOC roadside photographs metadata v4](https://www.kaggle.com/datasets/headsortails/us-roadside-attractions-photographs/versions/4) | Historical subjects lack coordinates/current arrivals. Existing Corn Palace remains preserved; no photos imported. |
| [Rollercoasters v2](https://www.kaggle.com/datasets/robikscube/rollercoaster-database/versions/2), [RCDB mirror v13](https://www.kaggle.com/datasets/mcpenguin/rollercoasters/versions/13) | Ride-level stale data and unresolved upstream rights; cannot imply current park operation. |
| [Top 100 clubs v2](https://www.kaggle.com/datasets/bhavyadhingra00020/top-100-night-clubs-2024/versions/2) | DJMag scrape, unresolved upstream grant and no native coordinate fields. |
| [US breweries v1](https://www.kaggle.com/datasets/brkurzawa/us-breweries/versions/1) | Stale directory scrape, no coordinates and no established upstream redistribution grant. |
| [US Local Business Atlas v1](https://www.kaggle.com/datasets/valeriiserko/us-local-business-atlas/versions/1) | Actual files contain aggregate counts, not 318,000 venue-level records. |

The private reproducible source/research bundle retains exact metadata, primary
rights evidence, all selected originals, and full candidate/rejection reports.
Raw operator HTML remains private audit evidence. No credentials, private trip
data or public operational metadata are included in this PR.

## Actual PostgreSQL discovery and verification

These are the actual five-mile repository queries along the same retained real
driving geometries as the 500-place comparison:

| Corridor | 500 daytime hits | 619 daytime hits |
| --- | ---: | ---: |
| LA–San Diego | 0 | 17 |
| SF–LA | 1 | 24 |
| SF–Boise | 2 | 13 |
| SF–Chicago | 4 | 15 |
| Ely–Reno | 0 | 0 |
| Seattle–Portland | 4 | 5 |
| LA–Phoenix | 2 | 16 |
| Olympic Peninsula | 7 | 7 |
| South Fork–Creede–Gunnison | 8 | 8 |
| Juneau local roads | 4 | 4 |

PostgreSQL 18.6 ran 2,166 bounded discovery queries per generation. Expanded
execution p95 was **0.84 ms**, compared with **0.70 ms** for 500, on this local
test machine; full query plans and authentic row/index footprint are retained
privately. This does not measure Neon/network latency. Eight typed probes cover
both source namespaces, the sparse states, museum/roadside/entertainment and
evening discovery. Original provenance survives, scheduler hours remain unknown,
and markets are excluded from evening restaurant results. Actual rollback to
the retained 500 and reactivation pass.

Backend validation passes **1,215 tests / 87.53% coverage**, including real
PostgreSQL cases. The new market, park and release-SQL suites contribute 39, 29
and five meaningful regressions. Frontend format/lint, **319 tests / 90.23% line
coverage**, and production build pass. Existing coverage thresholds and the
large-bundle warning remain. Exact-head remote checks and final portable replay
are separate release receipts.

Nearby hits are not promised detours, itineraries, opening-hour compatibility or
solver success. The user's exact failing route is unknown. Browser saved-trip
verification remains pending; neither is claimed fixed.

## Rebuild and release

Replay the immutable 500 source bundle first. Rebuild the two new source children
with `catalog_markets_manifest.py` and `catalog_parks_manifest.py`, then pass
their artifacts to `catalog_expansion_release.py` with the preserved 500 recipe.
The producer refuses existing output and publishes `completion.json` only after
all sources and preserved rows pass. The canonical 619 serialization SHA-256 is
`f1ad0f99106c1442f07526f614e6df7759e3cd5227d5f87b7e43f95975119e9f`.

`catalog_expansion_discovery.py` accepts only a specifically named disposable
loopback PostgreSQL database. `catalog_release_sql.py` compiles inert guarded
staging and separate activation/rollback transactions for authorized connector
execution. They serialize catalog mutation, reject an unexpected active
generation or changed baseline/content, retain the storage guards and preserve
every existing row. Only the active pointer changes during cutover/rollback.

Independent parent review is required before merge or activation. Then verify
current recovery freshness and exact restored backup evidence under the existing
policy, exact-main CI, serialized deployment, unchanged expected live generation,
atomic activation, live SHA/count/provenance discovery and health. The prior 500
is the rollback target. Application rollback does not undo catalog activation.
No fresh-backup-per-activation rule, paid upgrade or safety-limit change is added.
