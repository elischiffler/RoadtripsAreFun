# Bounded cloud catalog expansion — October 21, 2026

This task branch adds **93 source-admitted public visitor facilities in 24 states**,
each with a deterministic persona and a bounded source calendar. The existing
incremental importer replays their original evidence. All 93 were staged, queried
through the application repository, and rolled back in disposable PostgreSQL 18.6.
**No production import, activation, deployment, push, account creation or paid AI
request occurred.** These are development additions pending a current-parent
comparison; this report does not claim complete factual or physical verification.

The branch starts at current develop `3e7010ca5361b752f3e65255190dec249994de26`.
The original saved `work` branch at `5cd24eb` is preserved. The newer develop
architecture uses a licensed PostgreSQL catalog, source calendars and the
14-attribute `LocationProfile`; the older desktop Tripadvisor findings do not
describe this baseline. Geographic scope remains the 50 US states plus DC,
including Alaska/Hawaii in baseline reporting; territories remain excluded.

## Deliverables and scope

- [93 normalized additions](data/catalog-expansion-20261021/additions.preview.json)
- [93 complete structured profiles](data/catalog-expansion-20261021/personas.json)
- [93 source calendars and constraints](data/catalog-expansion-20261021/calendars.json)
- [Coverage and resource measurements](data/catalog-expansion-20261021/completion.json)
- [Adapter decisions and rejection reasons](data/catalog-expansion-20261021/source-reports.json)
- [Independent exclusion-only arrival review](data/catalog-expansion-20261021/arrival-review.json)
- [Ten-source research and rights ledger](data/catalog-expansion-20261021/source-decisions.json)
- [Actual PostgreSQL proof and blocker record](evidence/catalog-expansion-20261021.json)

The configured hosted database resolves, but its TCP connection fails with
`OSError: [Errno 101] Network is unreachable`. The catalog-only snapshot operation
failed before producing a snapshot; no writes were requested. The reproducible
coverage baseline therefore consists of the **603 checked-in complete records**.
The five later documented additions in the October 19 release are excluded by
their explicit native identities. Their complete rows and 189 inherited calendar
companions are unavailable here. The missing five rows cannot receive complete
name/spatial checks, so a full current-parent comparison remains required before
any release. **603 → 696** below is a repository comparison, not a live catalog
count. The documented 608-place production generation was neither read nor changed.

## Source selection, rights and freshness

The accepted data comes directly from the USDA Forest Service's
[constructed recreation-site service](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0),
independently checked against its
[public recreation feed](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0),
official publication metadata, Census ACS 2025 state boundaries and real OSRM
destination receipts. Original response bytes, exact URLs, status, SHA-256 and
October 21 acquisition timestamps are retained. Publisher update dates remain
unknown where absent; acquisition time is never substituted for an upstream update.

US government factual-data reuse and the source-specific publication contract are
replayed using the existing pinned notices:
[agency factual-data notice](../frontend/public/licenses/LicenseRef-US-Agency-Factual-Data.txt)
and [ODbL](../frontend/public/licenses/ODbL-1.0.txt). Original agency works are not
claimed as Roadtrips copyright and no agency endorsement is asserted. Existing
[public attribution](../frontend/public/catalog-attribution.html) already covers
USFS, Census, OSRM and OpenStreetMap. Native agency points are unchanged; OSRM is
arrival corroboration, not a coordinate replacement. Raw routing receipts retain
their OSM/ODbL attribution and applicable redistribution obligations. No photos,
logos, reviews or user data were acquired for destination profiles.

The ten-source ledger independently investigates Kaggle, Hugging Face, original
publishers and government catalogs. Platform hosting alone does not clear rights:

| Source | Finding and decision |
| --- | --- |
| [Official Wikimedia HF linked dataset](https://huggingface.co/datasets/wikimedia/linked-openstreetmap-wikidata-wikipedia-wikivoyage) | September 15 snapshot, exact revision retained. Three explicitly CC0 structured files are useful future museum/landmark leads. They are 174/435/957 MB; no full download under this batch's 100 MiB ceiling. OSM and article files have separate ODbL/CC-BY-SA terms. |
| [HF Overture embeddings](https://huggingface.co/datasets/pvv5385/overture-usa-places-embeddings) | Older 13-city mirror with unclear retention of per-record upstream source/NOTICE. Hold; prefer the existing primary Overture pipeline. |
| [HF itinerai places](https://huggingface.co/datasets/itinerai/us_places) | Tripadvisor-derived text/reviews/photos lack cleared rights; metadata API returned 401. Excluded, no authentication changes. |
| [Kaggle road-trip pairs](https://www.kaggle.com/datasets/meetnagadia/road-trip-dataset) | 2021 origin/destination pairs, vague original provenance and copyrighted contents; not distinct verified attractions. Excluded. |
| [Kaggle breweries](https://www.kaggle.com/datasets/brkurzawa/us-breweries) | 2019 scraped directory; GPL uploader label and claimed scraping permission do not establish downstream source rights. Held. |
| [Primary Open Brewery DB](https://github.com/openbrewerydb/openbrewerydb) | MIT notice supports a future pinned/provenance-audited lead extraction. Retain copyright/permission notice. Current operator calendars and arrivals remain unproved; no admissions. |
| [Connecticut historic districts](https://geodata.ct.gov/maps/ctmaps::ct-public-historic-districts) | Original metadata specifies NC/ND restrictions; incompatible automatic commercial intake. District polygons also do not establish public entrances. |
| Vermont recreation and older government leads | Rights reconciliation, stale source information or unavailable original distributions remain unresolved. The ledger preserves exact primary URLs, terms and 404 outcomes. No records admitted. |

A bounded NPS acquisition also retained 49 successful unit snapshots and one
failed unit, inspecting 55 visitor facilities. None enters this batch: source
access/state/calendar rules or the native road-destination distance fail. These
are explicit holds, not proof that those regions have no useful attractions.

## Admission and quarantine

The first sixteen corridor acquisitions selected 102 USFS facilities but admitted
none. Parking/directions, clocks, source conflicts and two >75 m destination snaps
remain held. The already acquired **7,776-row** inventory then supplied a fixed
150-prospect shortlist, round-robin by state starting with sparse repository
coverage. The new optional `site_ids` selector changes prospect selection only;
all existing source admission rules still run. No unbounded crawl occurred.

The 150 prospects yield **93 accepted and 57 held** after original-source replay
and independent textual review. Positive admission requires:

- An explicit publisher-native identity, supported facility type, publication
  status and unchanged finite WGS84 point.
- Census state-polygon agreement and no conflicting publisher state.
- Documented parking and driving directions; independent legacy-feed identities
  and points must agree where present. Missing legacy records remain unknown.
- Complete literal daily clocks, intersected with every applicable source clock
  and seasonal restriction. Unknown/qualified windows do not become guessed hours.
- An authentic destination response within the unchanged 75 m limit.
- Identity, name/region and 250 m collision checks against all available parent
  records and other additions. Coordinates are never moved to pass a check.

Automated checks alone initially yielded 102 provisional rows. Independent review
of all 102 found nine further conservative holds: Bear Canyon's walk-in/shuttle
approach, Powwow's permit requirement, Ohio View's contradictory GPS text, two
distant Baker trailheads with indistinguishable directions, Gorge Ponds' directions
to a different arrival, Sand Camp's unresolved parking/point relationship, and
two Beartooth Highway approaches pending precise seasonal road-segment review.
The code now conservatively rejects shuttle/walk-in, mandatory-permit and explicit
unreconciled GPS qualifications. A compact, hash-bound review ledger separately
excludes unresolved identities. Its positive review label only means that no
additional conflict was observed in the retained text; it cannot grant admission.

All final calendars cover **October 21–November 19, 2026**. This thirty-day
review policy is neither a publisher promise nor a future operating-status claim.
Current weather/road conditions, every operator alert, parking inventory, costs,
reservation inventory and accessibility are not comprehensively verified. Source
identity/coordinate validation is not a field survey. Native truncated names are
preserved rather than silently repaired.

## Profiles and application integration

`app/catalog/personas.py` builds the existing typed `LocationProfile` with all
14 canonical attributes. The factual description uses source name, facility type
and checked state. Character, interests and suggested activities are explicitly
inferred. Unmeasured attributes retain an explicitly labeled **0.5 uninformative
prior**; these are not measured reviews. Generic trailheads do not establish hiking
permission, family suitability or crowd levels. Costs, accessibility, current
operating status and parking/reservation availability remain null.

Examples from the delivered profiles:

- **Homer Stone Trailhead, VT:** publisher-listed trailhead with its native arrival
  and source calendar. Character: trail gateway; nature fit 0.9 is a category
  inference. Activity suggestion: check permitted trail activities. Hiking, family
  friendliness and crowd avoidance remain unmeasured 0.5 priors.
- **East Gateway Information Site, WY:** publisher-listed interpretive site.
  Character: interpretive stop; history/culture fit 0.8/0.7 are recommendations.
  Retained original approach/parking constraints supply practical context.
- **Laurentian Divide Overlook Parking, MN:** native source identity and viewing
  point; scenic-stop character and scenery/nature fit are explicitly inferred.
  No guaranteed sightings, surveyed gate or current parking capacity is claimed.

New source manifests explicitly opt into versioned persona enrichment. Original
source files and earlier manifests are preserved. The typed source adapter
regenerates profiles during ordinary incremental preparation and stores them in
place provenance. `repository.nearby` projects the factual description/activities
and carries the labeled ratings/fit metadata through `source_provenance`.
No schema migration is needed. Existing trip-scoring and visit-duration AI behavior
is outside this batch; no AI request was made while acquiring/enriching/testing it.

## Measured coverage

The repository's 603 full parent records become 696 diagnostic records with this
batch. All states/DC with baseline coverage remain represented. CT and DE remain
empty. The additions are **82 trailheads, five interpretive sites, three viewpoints
and three picnic sites**. Eighty-eight carry nature classification and five culture.
The batch does not improve the 33 museums, ten amusement parks, five restaurants,
five nightlife records or two roadside-attraction records.

| Region | Before | After |
| --- | ---: | ---: |
| Vermont | 1 | 9 |
| Minnesota | 3 | 11 |
| Idaho | 5 | 12 |
| South Dakota | 4 | 11 |
| Pennsylvania | 5 | 10 |
| Louisiana | 1 | 2 |
| Kentucky | 13 | 23 |
| Wyoming | 15 | 22 |

The [sixteen initial broad highway comparisons](data/catalog-expansion-20261021/broad-corridors.json)
show no new nearby hits from the final regional batch. Eight additional fixed scenic corridors were captured once to
measure local route relevance. All route receipts are real OSRM road geometries;
approximate city centers are diagnostic endpoints, never attraction entrances.
Continuous five-mile road buffers give:

| Scenic corridor | Before | After |
| --- | ---: | ---: |
| Bennington–Rutland | 0 | 3 |
| Slade–Stanton | 1 | 5 |
| Duluth–Grand Marais | 0 | 2 |
| Marienville–Warren | 0 | 1 |
| Missoula–Hamilton | 2 | 4 |
| Cody–Red Lodge | 0 | 0 |
| John Day–Baker City | 0 | 0 |
| Lead–Spearfish | 0 | 0 |

These are spatial diagnostics. They do not establish sampled runtime quotas,
date-specific opening at an actual arrival, seasonal road usability or a jointly
feasible personalized itinerary. OSRM requests remain serialized at <=1/second;
source HTTP/body/time limits and all importer ceilings remain unchanged.

## Reproduction and resource proof

Use Python 3.12 and the pinned backend requirements, including `pypdf==6.10.0`.
All paths below stay in the isolated cloud environment. Each output must be new.

```sh
python scripts/catalog_expansion_campaign.py routes --output /workspace/NEW/routes
# Existing bounded acquisition (no database or AI access):
PYTHONPATH=backend python - <<'PY'
from pathlib import Path
from app.catalog.usfs_current import acquire
acquire(Path('/workspace/NEW/usfs-discovery'), parent_rows=[],
        routes_index=Path('/workspace/NEW/routes/index.json'),
        route_root=Path('/workspace/NEW/routes'))
PY
python scripts/catalog_expansion_campaign.py shortlist \
  --source-dir /workspace/NEW/usfs-discovery \
  --limit 150 --output /workspace/NEW/shortlist.json
PYTHONPATH=backend python - <<'PY'
import json
from pathlib import Path
from app.catalog.usfs_current import acquire
acquire(Path('/workspace/NEW/usfs-selected'), parent_rows=[],
        routes_index=Path('/workspace/NEW/routes/index.json'),
        route_root=Path('/workspace/NEW/routes'),
        site_ids=json.loads(Path('/workspace/NEW/shortlist.json').read_bytes())['site_ids'])
PY
```

Reacquisition may produce different holds and requires a fresh independent review;
do not reuse this ledger on a changed source bundle. For the retained acquisition:

```sh
python scripts/catalog_expansion_campaign.py profile-source \
  --source /workspace/catalog-expansion-20261021/usfs-national/bundle.json \
  --arrival-review /workspace/catalog-expansion-20261021/research/arrival-review.json \
  --output /workspace/catalog-expansion-20261021/usfs-national/NEW-profiled.json
python scripts/catalog_expansion_campaign.py replay \
  --source usfs-current /workspace/catalog-expansion-20261021/usfs-national/NEW-profiled.json \
  --routes-index /workspace/catalog-expansion-20261021/scenic-routes/index.json \
  --output /workspace/NEW/review
```

Offline replay is deterministic and refuses existing outputs. Original bodies,
research receipts, initial holds and final sources are retained under
`/workspace/catalog-expansion-20261021/`. The portable **development-only** import
is `local-proof/portable-import/`; its parent is explicitly one synthetic row,
so it is not a production replacement artifact. The final selectors are
`final-review/addition-inputs.json` for an eventual permitted current-parent build.

Before downloads, the workspace had approximately 30 GiB free. The final source
directories retain approximately 36 MiB; unused discovery bodies are charged as
retained evidence. Raw source acquisition is capped at 64 MiB per USFS bundle;
aggregate retained imports stay under 100 MiB / 50,000 files. Original discovery
has 7,776 records; the final adapters consume 487 source units including held NPS
inputs, not 487 total research rows. The local import additionally charges the
complete 7,776-row discovery scan and reports 7,974 units with its synthetic parent.
Its portable evidence is 34,554,700 bytes across 138 files; consumed import bytes
are 13,307,773. No capacity guard or database plan was enlarged.

Disposable PostgreSQL stores the 93 actual additions plus one synthetic fixture.
All 93 native-point application queries return profiles and calendars. Staging
twice is idempotent, staging preserves the pointer, activation and rollback work,
and original parent content is preserved. Measured database size is 9,311,935 bytes;
places relation including indexes/TOAST is 753,664 bytes, of which indexes are
106,496 bytes. These are local measurements, not hosted capacity guarantees.

The backend suite runs with real external socket connections blocked and AI
credentials cleared: **2,032 pass, 130 optional skips, 80.80% coverage**, above the
unchanged 63% threshold. Python format/lint, focused source/profile tests and
63 additional disposable PostgreSQL regressions pass. Frontend
format/lint, 278 tests (92.37% coverage) and production build pass; Vite retains its
large-chunk warning. Exact test totals and log paths are recorded in the evidence
receipt. Live provider trips, production recovery and full container smoke are not
claimed by these development checks.

The next release step is a complete, permitted current-parent catalog snapshot and
companion set in this cloud, followed by the existing duplicate/immutable-parent
replay and release-owner review. No production action is authorized or attempted
by this development artifact. CT/DE coverage, museums, unusual roadside stops and
evening venues remain priority gaps; source rights, current access and calendars
remain the admission constraints.
