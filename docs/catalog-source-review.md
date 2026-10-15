# Kaggle source assessment — 2026-10-14

Five Kaggle inputs have now been acquired and profiled; the reviewed Boulder v1
adapter admits 12 unique nature destinations in isolated PostgreSQL. No Neon
catalog was loaded. See the [actual schemas, hashes, rights and source counts](catalog-kaggle-intake.md).
No new credentials, accounts or terms-acceptance actions were taken. The dated
assessment below records the earlier blocked environment and unresolved candidates;
its unavailable-archive assumptions are superseded by the authentic intake.

## Access evidence

The fresh saved environment now exposes `KAGGLE_API_TOKEN`. A single bounded,
authenticated attempt to download version 1 of
`paultimothymooney/trailstrailheadsandrockformationsinboulder` still failed with
proxy `CONNECT 403 Forbidden` before reaching Kaggle. No token was printed,
archive downloaded, or alternative route attempted. See the exact endpoint,
limits and independent checks in [validation](catalog-validation.md). Kaggle
authentication has not been accepted or rejected by the origin.

Earlier unauthenticated Python urllib requests to each URL returned `URLError: Tunnel connection failed: 403 Forbidden` from the environment proxy before reaching the origin:

- https://www.kaggle.com/api/v1/datasets/list?search=us%20museums&pageSize=10
- https://www.kaggle.com/api/v1/datasets/download/imls/museum-directory
- https://www.kaggle.com/api/v1/datasets/download/nationalparkservice/park-biodiversity
- https://www.imls.gov/research-evaluation/data/museum-data-files
- https://catalog.data.gov/api/3/action/package_search?q=Museum%20Universe%20Data%20File&rows=2

The web tool resolves the two Kaggle pages and their titles, but returns no metadata/body. API view/list URLs are also unavailable through web. Therefore exact archive bytes, current version/update time, column names and counts cannot be verified in this environment. This is not evidence that Kaggle itself requires authentication.

## Expanded candidate queue

The requested pilot includes roadside/niche stops, entertainment, nature, beaches,
landmarks, museums and national parks. These six leads came from the task handoff;
archive contents and Kaggle metadata were not independently fetched in this
recheck. No row is approved by appearing in this table. Do not treat uploader
license labels as clearance of upstream content.

| Candidate | Intended contribution | Review before acceptance |
| --- | --- | --- |
| [Boulder trails, trailheads and rock formations](https://www.kaggle.com/datasets/paultimothymooney/trailstrailheadsandrockformationsinboulder) | Regional nature/trailheads | Match actual archive layers and fields to the City of Boulder distribution and applicable CC0 policy identified in the handoff. Verify current public trailhead/parking points, seasonal closures and road access. Rock/area centers and trail geometry are not driving arrivals. One regional dataset cannot supply national variety. |
| [GeoNames allCountries](https://www.kaggle.com/datasets/jwilda3/geonames-allcountries) | Candidate landmarks, beaches and natural features | Resolve the handoff's mirror CC-BY-SA label versus upstream CC-BY before reuse. Inspect exact version/schema and original notices; retain feature/native IDs. Filter explicit US/state and eligible feature codes outside Neon. Do not acquire an unbounded worldwide dump for this pilot. Feature coordinates do not establish an entrance or current visitor access. |
| [Rollercoaster database](https://www.kaggle.com/datasets/robikscube/rollercoaster-database) | Entertainment/amusement-park destinations | Inspect the actual Wikipedia-derived field provenance and applicable reuse requirements. Keep independently permitted facts and attribution; do not assume article text/photos are unrestricted. Collapse rides to an operating destination with its own source identity and verified public arrival point; historical or removed rides do not establish an open park. |
| [US roadside-attractions photographs](https://www.kaggle.com/datasets/headsortails/us-roadside-attractions-photographs) | Leads for niche/roadside curation | Verify the exact Library of Congress collection/item rights and metadata provenance. The handoff reports historical metadata without coordinates: confirm the archive and independently verify surviving destinations, current use, public access and practical arrival. Historical photographs alone do not establish a current stop. Photos are outside this pilot. |
| [IMLS museum directory](https://www.kaggle.com/datasets/imls/museum-directory) | Museums and cultural variety | Resolve contributor/geocoding rights described below; review historical/administrative addresses, duplicates, relocations, museum qualification and current operation. A nonprofit's office is not necessarily a visitor destination. |
| [NPS park biodiversity](https://www.kaggle.com/datasets/nationalparkservice/park-biodiversity) | National-park leads | The handoff reports that version 1 lacks coordinates; verify the actual file. Use independently permitted entrance/visitor-center facts with distinct provenance and current-access evidence. Do not invent park coordinates or substitute park centers. Species observations are outside the places pilot. |

The [GeoNames export page](https://www.geonames.org/export/) was independently
read in this recheck. It states CC-BY attribution, permits commercial use and
offers country extracts as well as a worldwide file. That establishes the
upstream's stated terms, not the terms/provenance of the unavailable Kaggle
mirror or the suitability of individual arrival points. Fetching upstream policy
text did not download a replacement source archive or fulfill the Kaggle requirement.

Use the [500-place pilot plan](catalog-pilot-plan.md) to track review and coverage.
Unknown rights or access evidence remain exclusion reasons even when a category
target cannot be met.

## Offline GeoNames schema inspection

The [upstream readme](https://download.geonames.org/export/dump/readme.txt) and
[feature-code reference](https://www.geonames.org/export/codes.html) were read on
October 14. They document a 19-column UTF-8 TSV, WGS84 latitude then longitude,
US ISO state codes, native integer IDs and modification dates. The readme states
CC-BY-4.0; the unavailable Kaggle mirror's rights/version/format are still unresolved.

`scripts/inspect_geonames.py` can inspect a supplied **local uncompressed TSV**
using those documented positions. It performs no downloads and never connects
to a database. This is a review-queue parser, not an approved Kaggle importer or
proof that the mirror follows the upstream schema. Only selected fields are
validated; it does not certify every column of a dump. It guesses no CSV layouts
or headers. Example after an original file and metadata are legitimately supplied:

```sh
/workspace/roadtrips-venv/bin/python scripts/inspect_geonames.py \
  --input /workspace/catalog-data/supplied-geonames.txt \
  --region CA --region AK --region HI \
  --feature-code S.MUS --feature-code L.AMUS \
  --output /workspace/catalog-data/geonames-review-leads.jsonl
```

The example selects documented museum/amusement-park codes for inspection; it
does not establish public access, current operation, category balance or a driving
arrival. No authentic file has been run. Synthetic rows exist only inside unit tests.
Limits cannot exceed 500 unique review leads, 10,000 scanned lines, 20 MiB read,
64 KiB per line and 30 seconds checked between reads. Scanning stops on the first
limit; a selected prefix is not a representative sample or complete coverage.
The report records truncation/rejects, exact inspected-prefix and output checksums,
plus state/code counts. A prefix checksum is not a full archive checksum.

Every lead is marked `review_only: true`, `import_eligible: false`, with source
coordinates explicitly unverified as arrivals, no arrival point or operation
evidence, and unresolved rights. The separate `.review.json` report always has
`accepted_for_import: 0` and `kaggle_compatibility: "unverified"`. It is not an
import manifest and the existing importer rejects it. Exact duplicate IDs are
counted; conflicting records abort publication. Existing outputs are preserved.
This prepares bounded inspection once access changes, without relaxing any gate
or adding an application runtime path.

## Candidate 1: Biodiversity in National Parks

- Kaggle: https://www.kaggle.com/datasets/nationalparkservice/park-biodiversity
- Confirmed page title: Biodiversity in National Parks.
- Candidate rationale: US NPS-origin parks are a plausible bounded nature supplement. Inspect parks inventory, rather than importing species observations.
- Primary rights evidence: https://www.nps.gov/aboutus/disclaimer.htm (updated March 5, 2025), Ownership section: agency-created material is generally public domain unless otherwise indicated; third-party material and trademarks are excluded. Retain NPS credit and no-claim-to-original-US-government-works notice where applicable. This policy alone does not establish that every field of an unavailable Kaggle archive is agency-created.
- Required before acceptance: acquire archive plus metadata, verify originating NPS dataset/README and factual park-coordinate provenance; inspect actual coordinate column names, finite WGS84 values, source dates, closures and US jurisdictions. Do not import pictures or descriptions with independent rights.
- Size/count/coordinate schema: unverified, since archive and metadata inaccessible. Do not substitute remembered counts for measurements.
- Quality concern: park-level coordinates can be geographic centers with no road access, not entrances/visitor centers. Would need entrance/access-point evidence before use as driving stops. This cannot replace nationwide restaurants/evening venues.

## Candidate 2: Museums, Aquariums, and Zoos

- Kaggle: https://www.kaggle.com/datasets/imls/museum-directory
- Confirmed page title: Museums, Aquariums, and Zoos.
- Upstream: https://www.imls.gov/research-evaluation/data/museum-data-files. Search index identifies Museum Universe Data File releases FY2014 Q1, FY2015 Q1 and FY2015 Q3, with no planned update; actual content fetch blocked.
- Important upstream rights/quality finding: research partner Drexel's own publication https://drexel.edu/news/archive/2016/august/museumstat explicitly says MUDF combines public sources (including IRS) and proprietary location-aggregator data. Do not assume all coordinates are public domain just because a federal agency hosts the dataset. Need the actual IMLS distribution license/readme and contributor restrictions.
- Primary government presentation https://statspolicy.gov/assets/fcsm/files/docs/A-1FrehillFCSM2018toCOPAFS.pdf names source flags including Factual, IRS, association lists, agency records and private foundations. Describes geocode data and later duplicate removal/museum qualification work. This reinforces conservative quality review.
- Secondary observation (not used as acceptance evidence): a 2016 student analysis reports 33,072 rows/44 columns, including latitude/longitude. Exact Kaggle version/schema/bytes remain unverified.
- Likely useful cultural/niche supplement only after rights and current existence/location review. Historical nonprofit administrative records may include non-venues, duplicates and stale addresses.

## Wikidata alternative

https://www.wikidata.org/wiki/Wikidata:Licensing is clear primary evidence that structured data is CC0. Names, stable Q IDs and coordinate statements are a strong independent source for museums, landmarks and public art. This assessment did not identify and verify a particular Kaggle-hosted Wikidata US POI archive, so a direct Wikidata extraction must not be described as fulfilling the requested Kaggle ingestion. Retain Wikimedia provenance and avoid copying Wikipedia text/photos under the CC0 assumption.

## Concrete prerequisite

Permit ordinary outbound HTTPS to the public Kaggle API and any download redirect host it returns, or have the user supply the original public Kaggle archive and dataset metadata/license/readme. Then measure content and establish upstream rights before importer approval. Authentication setup, credential entry and any explicit agreement acceptance remain user actions if Kaggle actually requires them. Do not bypass the proxy or weaken source safeguards to manufacture an import.
