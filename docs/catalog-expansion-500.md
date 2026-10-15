# Complete 500-place review proposal

This branch prepares **500 distinct, source-admitted places**, adding **257** to
PR44's reviewed 243. All prior 243 normalized row serializations and provenance
are preserved byte-for-byte. The new increment comprises **251 USFS destinations
and six Overture venues**. It is a complete 18-child replacement recipe, not an
append-only activation instruction. Production activation is outside this PR.

Main was inspected at `0c73b06`, with PR42 already merged. The task branch
explicitly merges PR44's reviewed head
`5f17b994f719b9e9d342bd0d17f1bde9e339ffa6`. PR44 itself is unchanged. Its corrected
source ZIP version 1 and the frozen portable 214 ZIP are retained unchanged.
Actual Windows execution and independent review of those dependencies remain
separate acceptance work; this PR does not claim either is complete.

- [Actual 500-row preview](data/catalog-expansion-500-20261015/reviewed-500.preview.jsonl)
- [Preserved 243-row baseline](data/catalog-expansion-500-20261015/reviewed-243.expected.jsonl)
- [New 257-place review](data/catalog-expansion-500-20261015/new-257.review.json)
- [Every USFS source record and non-admission reason](data/catalog-expansion-500-20261015/usfs-source-admission-ledger.json)
- [Reviewed source holds](data/catalog-expansion-500-20261015/usfs-reviewed-holds.json)
- [Venue acquisitions and holds](data/catalog-expansion-500-20261015/venue-acquisition-and-holds.json)
- [Machine-readable validation and discovery report](evidence/catalog-expansion-500-20261015.json)

## Blocking admission findings corrected

The October 15 review at `9d3f7c429642dd3fe93cdfba6b7e55e1e9a5eae1`
found that public-feed season dates did not participate in admission and that
public-only restrictions/hours were omitted. Both are corrected here.

- **Withheld:** Stoney Creek (`usfs:6499`, May 20–September 12) and Kettle Crest
  (`usfs:67862`, December 1–March 31). OPEN enums and road snaps cannot establish
  seasonal access. Complete recurring month/day intervals are checked against
  the current UTC admission date, inclusively across year boundaries.
- **Replacements:** Swan Observatory (`usfs:79043`, AK) and Eastern Sierra Visitor
  Center (`usfs:20698`, CA). Both have the retained open public record, native
  facility point, directions and parking evidence. Driving destination distances
  are 62.67 m and 69.25 m. Eastern Sierra's exact daily gate-time statement was
  inspected: daily 08:30–16:30 opening and a 16:15 entrance cutoff are access
  qualifications, not an all-day closure. The exception matches only those exact
  two feed statements; a changed or additional closure still fails admission.
- **Attribution:** every selected USFS row carries separate `construction_feed`
  and `public_feed` access facts with its own URL, snapshot hash, acquisition
  time and native record ID. All **32 public-only restrictions** survive.
  Columbine (`usfs:84460`) retains the warning against vehicles/trailers over
  22 feet and its summer/weekend/volunteer qualification. These remain source
  facts; no scheduler opening intervals or prices are invented.

The count stays **500**, with **257 additions**. The serialized first **243 rows
and their provenance remain byte-identical**. Seventeen additional regression
cases cover dates, wraparound/boundary days, the admission clock, literal source
attribution, and narrow daily-gate interpretation. The 30-day source freshness
guard, arrival distance limit, importer/database ceilings and schema are unchanged.

## Coverage and practical limits

| Exclusive primary reporting category | Total |
| --- | ---: |
| Nature/scenic/trailheads | 287 |
| Landmarks/interpretive/historic | 122 |
| National parks | 38 |
| Museums | 30 |
| Beaches | 12 |
| Food | 5 |
| Entertainment | 4 |
| Roadside | 1 |
| Nightlife | 1 |
| **Distinct places** | **500** |

Reporting categories use explicit source-adapter rules, rather than AI ratings.
Query groups can overlap: the new bowling venue also has a publisher-supported
`nightlife` group for its sports bar. It remains one entertainment destination
in the exclusive table. Unknown scheduler hours and prices are not filled in.

Coverage is **47 states plus DC**. CT, DE and VT remain empty. The largest
regional concentrations are WA 66, CO 63, CA 43, AZ 31, OR 31, UT 20 and MT 18.
Alaska has 15 total and Hawaii six. The Alaska additions are local road-network
clusters; travel to those networks from the lower 48 can require a flight or
ferry. No continuous lower-48 driving access is asserted.

Nature dominates this release. Beaches, entertainment, roadside and nightlife
remain sparse, and the original category allocations are not met. This proposal
meets the requested total without claiming nationally sufficient coverage.

The six new venues are the Museum of Jurassic Technology, GLBT Historical
Society Museum, Martin Auto Museum, Japanese Friendship Garden in Phoenix,
Lucky Strike Mar Vista, and Castles N' Coasters. They improve the California and
Phoenix clusters. Publisher facts retain GLBT's October 17 gala closure, museum
weekly/holiday differences, Martin's on-site parking, the garden's west-side lot,
and the two amusement/bowling frontages' **unverified parking**. No parking lot is
invented for either frontage. Lucky Strike's evening sports-bar discovery is
actually exercised through the existing typed evening provider, with unknown
opening intervals.

## Bulk source and admission

USFS's official [constructed recreation-site service](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0)
contributes unchanged native facility latitude/longitude, stable native site IDs,
types, published status, parking and driving directions. The separately retained
[public recreation service](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0)
corroborates its native public identity and open status. Its older point is used
only to detect identity disagreements within 500 metres; it never replaces the
facility coordinate. Website URLs come unchanged from that public record.

The bulk scan retains **5,824** eligible-type source facility records, plus **891**
public corroboration records from bounded identity lookups. These are raw source
records, not accepted destination counts. Only the frozen 251 selected
identities count. Multiple facility records sharing one public recreation ID
cannot inflate the count. All new FS destinations were also compared against the
prior catalog and each other within 250 metres; an unresolved shared arrival
was withheld rather than merged into preserved rows.

Each selected record requires published `OPEN` and public-feed `open`, existing
development, current source receipts, documented parking and driving directions,
valid native coordinates, a uniquely determined US state, and a real OSRM
**destination** result within 75 metres. Raw driving bytes, query coordinates,
response hashes, destination role, road name and distance are revalidated. The
query origin is an offset network probe, not a claimed trip start. Source road
snaps are not imported as replacement coordinates.

Published rough-road, low-clearance/four-wheel-drive and winter-only warnings
fail closed. Inspected holds additionally cover conflicting September/October
seasons, a private-road approach requiring an access call, and parking half a
mile from the native trailhead point. Johnston Ridge's construction-feed `OPEN`
was insufficient: its public feed says `unreachable`, so it is excluded. Missing
or `none` public status stays unknown and is not admitted. The full ledger
separates missing/unreviewed evidence from explicit negative evidence.

State codes are a documented point-in-polygon derivation from the retained
[Census ACS 2025 States 500K service](https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2025/State_County/MapServer/7),
not a nearby town or forest headquarters. Cartographic boundaries are not legal
jurisdiction surveys. Other classifications are explicit mappings from native
facility types. No model supplied locations, operation status, access, licensing,
hours or prices. Published season qualifications, restrictions and fee-charged
flags remain distinct source facts in provenance; a fee flag is not a price.

The [agency factual-data notice](../frontend/public/licenses/LicenseRef-US-Agency-Factual-Data.txt)
credits USFS and Census. Agency ownership and source metadata are retained.
Only agency factual fields are emitted under the original-government-work
framework described in [17 USC 105](https://www.copyright.gov/title17/92chap1.html#105).
Photographs, creative descriptions, logos and third-party works are omitted from
rows. Driving evidence credits OSRM and
[OpenStreetMap contributors / ODbL](https://www.openstreetmap.org/copyright).
The six venues preserve licensed Overture coordinates and upstream attribution;
operator pages independently establish their visitor facts. Existing reviewed
Kaggle source children remain intact. Previously unresolved museum/coaster
mirror rights and current-arrival issues remain holds.

## Actual discovery measurements

The repository's actual five-mile `repository.nearby` queries were executed
against separate **243** and **500** generations in disposable PostgreSQL 18.6.
The test database contains public catalog data only. Route vertices come from
retained real OSRM driving responses; additional city endpoints are retained
Nominatim geocodes. No invented road or venue coordinates are used.

| Driving geometry | 243 daytime hits | 500 daytime hits |
| --- | ---: | ---: |
| LA–San Diego, short-day benchmark | 0 | 0 |
| SF–Boise, medium/tight-budget geometry | 1 | 2 |
| SF–Chicago, long benchmark | 2 | 4 |
| SF–LA, dense benchmark | 0 | 1 |
| Ely–Reno, sparse benchmark | 0 | 0 |
| Seattle–Portland | 4 | 4 |
| LA–Phoenix | 1 | 2 |
| Olympic Peninsula via Hoodsport and Port Angeles | 1 | 7 |
| South Fork–Creede–Gunnison | 1 | 8 |
| Juneau–Lena Beach, local Alaska roads | 0 | 4 |

Counts are unique catalog hits near sampled geometry, not promised detours,
itineraries, schedules, hotel budgets or CP-SAT success. The unavailable failing
route cannot be declared fixed. Additional typed attraction probes preserve
native USFS IDs and provenance in CA, WA and AK. The typed evening probe returns
Lucky Strike with `opening_intervals=None`.

## Rebuild and release bounds

[The producer](../scripts/catalog_500_manifest.py) takes retained originals and a
fully re-admitted 243 baseline. It checks the pinned source inventory and exact
251-ID selection, re-admits the six venue profiles, flattens all 18 children,
compares all 243 preserved rows, and checks all 500 against the published preview.
It refuses existing output directories. `completion.json` is the completion
marker; a failed work directory is not a release artifact.

```sh
python -X utf8 scripts/catalog_500_manifest.py \
  --sources <materialized-new-sources> \
  --baseline-bundle <replayed-243>/reviewed-243.json \
  --output <new-output-directory>
```

Use explicit **500 rows / 64 MiB** for the complete recipe. Measured evidence at
the first complete replay is **64,006,741 bytes**, below 67,108,864. Recipe paths
can change aggregate bytes and generation fingerprints slightly after relocation;
normalized rows/provenance remain identical. The canonical 500-row serialization
SHA-256 is `804b0854158423d44917e7ed27e2ea9b00ce21ec4048f8520ec7cc158678a896`.
The importer hard ceilings remain **50,000 rows / 100 MiB**; database ceilings and
schema are unchanged. Mixed input count remains below its 30-child limit.

The corrected private portable bundle is **version 2**, replacing the blocked
version 1 proposal. Its exact archive hash, size, immutable code snapshot and
fresh offline replay are recorded in the
[portable replay receipt](evidence/catalog-expansion-500-portable-replay.json).
The original 214/29 ZIPs and all original 333 driving receipts remain unchanged;
one genuinely acquired Eastern Sierra driving response is appended. Original
USFS source/driving inventories are retained alongside the corrected inventories.
No otherwise qualified record remains outside the exact 500-row selection.

Install Python 3.12 and the two pinned replay dependencies, psycopg2-binary 2.9.9
and lxml 5.3.0, before offline use. Interpreter and installers are not bundled.
Raw operator HTML remains private audit evidence; its prose, embedded reviews
and logos are not licensed for public redistribution. The replay validates source
freshness and current UTC seasonal admission; a later closure can appropriately
withhold a row and stop the frozen release rebuild. Descriptive or reduced-service
seasons stay attributed qualifications and never become scheduler intervals.
Actual Windows execution remains pending.

The source inventory SHA is
`c86b01c905c80c2e878acac0fd4cffe38e9ad781960a4de4181737c0af4ae914`.
Source evidence has the existing **30-day** freshness guard. After that window,
strict re-admission requires genuine acquisition and review; editing dates is not
a valid refresh. Saved expected rows remain historical evidence.

Current fix validation passes **1,137 backend tests, 87.42% coverage** (five
opt-in PostgreSQL cases skipped), Ruff format/lint, and **348 focused catalog
cases**. All five opt-in cases subsequently pass against a newly created isolated
`catalog_test`. Frontend format/lint, **319 tests / 90.23% line coverage**, and
build pass; the existing large-bundle warning remains. Exact-head remote CI and
the final bundle replay are tracked in the machine-readable receipts. Historical
pre-fix validation is retained separately and does not validate these new rows.

Fresh PostgreSQL 18.6 discovery measurements on the corrected 500 preserve the
counts above, including both zero-hit benchmark corridors. The corrected public
catalog dump and isolated restore each retain **743 rows** (243 + 500) and the
**500** active pointer, with content MD5 `7eb0b30a138d00c20c0a61162a1be352`.
The custom dump is **263,516 bytes**, SHA-256
`66c06f8eb3472c26abb83aa45f28d376dc57912e517bc87511f5075a64b2fff4`.
This is disposable public-data recovery evidence, not production backup acceptance.

Production backup/restore acceptance, independent re-review, merge, deployment
and activation remain with the separate rollout owner. This fix task performs
no production database write, credential change, trip deletion, paid-service
purchase, main push or merge. Coverage completion is not claimed.
