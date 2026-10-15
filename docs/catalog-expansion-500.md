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
regional concentrations are WA 67, CO 63, CA 43, AZ 31, OR 31, UT 20 and MT 18.
Alaska has 14 total and Hawaii six. The Alaska additions are local road-network
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
the first complete replay is **64,003,549 bytes**, below 67,108,864. Recipe paths
can change aggregate bytes and generation fingerprints slightly after relocation;
normalized rows/provenance remain identical. The canonical 500-row serialization
SHA-256 is `a52fbe12bdba5f7e20669614367331d6d05e496f964d4546291d502c33fefffb`.
The importer hard ceilings remain **50,000 rows / 100 MiB**; database ceilings and
schema are unchanged. Mixed input count remains below its 30-child limit.

Portable source bundle **version 1**, `roadtrips-reviewed-500-portable-source-v1.zip`,
**28,487,243 bytes**, SHA-256
`c43abc122b15316d4cc79ad44d7c642d3119492b078e1413b5a73621f0f25718`,
is saved privately in Library for the task owner. It includes the unchanged
214/29 ZIPs, the exact code snapshot at
`302f39910e660fb2e34cea16d2ecc9ab0d4880d6`, all original new-source/rights
receipts, an inventory, and `rebuild.py`. A fresh extraction to paths containing
spaces verifies **931 inventoried files** and reproduces all **500** rows with
network and database connections forbidden. The outer ZIP has 932 files, including
the inventory itself. Windows filename preflight finds zero invalid/reserved
names. Actual Windows execution remains pending.

[One otherwise qualified source candidate](data/catalog-expansion-500-20261015/otherwise-qualified-not-selected.json)
is excluded by the exact 500-row release selection. The separate source ledger
records all other exclusions and unresolved shared arrivals.

The [portable replay and isolated restore receipt](evidence/catalog-expansion-500-portable-replay.json)
records those measured checks. Install Python 3.12 and the two pinned replay
dependencies, psycopg2-binary 2.9.9 and lxml 5.3.0, before offline use; interpreter
and dependency installers are not bundled. Raw operator HTML remains private
audit evidence; source-data notices do not grant rights to republish its prose,
embedded reviews or logos. Normalized row facts and their source attribution are
the public review deliverable.

The source inventory SHA is
`cc24c5f3474c5f27f742a148fb9164a52d59425ac51b0eb81b7e3fd4e240bf6b`.
Source evidence has the existing **30-day** freshness guard. After that window,
strict re-admission requires genuine acquisition and review; editing dates is not
a valid refresh. Saved expected rows remain historical evidence.

Final network-disabled container validation passes **1,120 tests, 86.60% coverage**; five skipped
opt-in PostgreSQL cases subsequently pass against a separate newly created
`catalog_test` database. The 35 new catalog cases pass. Ruff and diff checks pass.
Frontend format, lint, **319 tests / 90.23% line coverage**, and build pass after
`npm ci` replaces the preloaded obsolete SDK with the lockfile version. The
existing large-bundle build warning remains. The fresh offline ZIP replay, container smoke (2/2), and complete disposable
PostgreSQL CRUD/recreate/readiness/backup/restore pass. Container dependencies were
installed offline using the repository's `cloud_build.py` and ordinary verified
workspace downloads; runtime security settings were retained. Direct nested
Docker egress was unavailable. Its initial buildx/cache path error is recorded
in the validation report.

A first container full-suite run under concurrent validation load passed 1,119
cases and failed the existing parallel-speed timing assertion (0.779 seconds,
required below 0.688 seconds); five PostgreSQL cases were skipped there. The
isolated timing recheck and serial full-suite rerun pass (**1,120 passed**, five
skipped, **86.60% coverage**). Exact pushed-head CI is checked separately. No
assertion or threshold changed.

The separately isolated public catalog dump/restore preserves **743** retained
rows (243 + 500), the **500** active pointer, and database-content MD5
`e4a7ffbc7ca0bc1c4cb3621ba6ba196a`. The custom dump is 217,958 bytes, SHA-256
`9de83da593bcda96e06f47861ddfde20b1420365e9b6040713e8a76009d2ecd2`.
This is local public-data recovery evidence, not production backup acceptance.

Production backup/restore acceptance, review, merge, deployment and activation
remain with the separate rollout owner. Activating only one increment would
replace retained coverage. This task performs no production database write,
credential change, trip deletion, paid-service purchase, main push or merge.
