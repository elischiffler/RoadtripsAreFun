# Authentic Kaggle intake, October 14–15, 2026 UTC

PR #40 remains a work in progress. Five authentic bounded Kaggle inputs were
acquired with the existing token, without printing credentials. The first
reviewed adapter accepts **12 unique Boulder nature destinations locally**.
Production accepted/staged/activated counts remain **0 / 0 / 0**. No Neon DDL,
data, pointer, credential, billing or deployment change occurred.

## Access and measured source contents

Ordinary Kaggle HTTPS now succeeds. Production website, API `/health`, `/ready`
and `/algorithms` returned 200 at 23:58 UTC October 14; the algorithms response
advertised only `cp_sat`. These are connectivity/baseline checks, not evidence of
the catalog release. Direct PostgreSQL to the existing Neon URL returned
connection refused. The authorized Neon connector's read-only query succeeded:
PostgreSQL 18.6, 22,134,784 database bytes, all three catalog tables absent.
Project metadata reported 46,145,536 branch logical bytes and 307,384 compute
seconds (85.38 CU-hours) for October 1–November 1. Those distinct measurements
are snapshots, not reserved capacity or a reason to keep probing Free compute.

| Pinned Kaggle input | Downloaded bytes | CSV rows | Actual findings / remaining admission work |
| --- | ---: | ---: | --- |
| [Boulder v1](https://www.kaggle.com/datasets/paultimothymooney/trailstrailheadsandrockformationsinboulder/versions/1) | 4,705,510 | 36 trailheads | Native `ACCESSID`; geometry `X` is longitude, `Y` latitude. Embedded `OSMPTrailheadsOSMPY` incorrectly repeats longitude. Archive XML identifies City OSMP and CC0. Current city pages independently establish 12 arrivals. |
| [Rollercoasters v2](https://www.kaggle.com/datasets/robikscube/rollercoaster-database/versions/2) | 1,007,277 | 1,087 | 812 finite coordinate pairs; 668 rows labeled Operating in this 2021 snapshot. Ride names repeat 97 times and are not globally unique venue IDs. Collapse rides to verified park destinations; review Wikipedia-derived fields/rights and current parking arrivals. No parks accepted. The JPEG was not used. |
| [IMLS museums v1](https://www.kaggle.com/datasets/imls/museum-directory/versions/1) | 1,914,327 | 33,072 | 33,007 finite points; only 9,216 physical street addresses, versus 23,846 rows with only administrative street addresses. Schema has 25 columns. Kaggle's description expressly warns of non-museums, duplicates and stale 2014 source records. Contributor/geocoding rights and current visitor locations remain unresolved. No museums accepted. |
| [NPS biodiversity v3](https://www.kaggle.com/datasets/nationalparkservice/park-biodiversity/versions/3) | 2,602,745 | 56 parks | Actual `parks.csv` has Park Code, Park Name, State, Acres, Latitude, Longitude. **This version has coordinates**, correcting the earlier unverified v1 assumption. All 56 are finite source points, not verified entrances. Multi-state values need explicit arrival-state treatment. Species rows were not used. No parks accepted. |
| [Roadside metadata v4](https://www.kaggle.com/datasets/headsortails/us-roadside-attractions-photographs/versions/4) | 236,882 | 11,710 | Downloaded only `us_roadside_attractions.csv`, not the 4.17 GB image collection. Fields are index, title, year, image, image_link; there are no coordinates. Historic photograph subjects need independently verified surviving venues/arrivals. No roadside stops accepted. |

Each acquisition stayed below 20 MiB; the roadside member request stayed below
5 MiB. ZIPs were not extracted wholesale. `scripts/profile_kaggle_archive.py`
profiles only the five actual selected CSV schemas with 20 MiB archive/member,
50,000-row and 64 KiB field ceilings. Reports explicitly remain review-only with
zero admission; a valid coordinate or uploader license is not arrival/rights proof.
Museum financial fields, photographs, descriptions and species data are not
retained in the catalog. Aggregate reports are under
`/workspace/catalog-data/intake-20261014/`, outside Git with the source artifacts.

GeoNames metadata was inspected, but its data was not downloaded. Version 5 has
`allCountries.txt` (1,604,444,581 decoded bytes) and `us_cities.txt` (302,955,839).
The archive's list size is 444,139,668 bytes. The mirror label says CC BY-SA 4.0
while its description says CC BY 4.0; upstream rights, mirror obligations and
practical arrival/current-operation evidence remain review gates. No large
download ceiling was silently increased.

## Provenance and rights

Measured original acquisition SHA-256 values:

```text
Boulder v1       5dfb978b50c8d238eda2362dcd99b1a1b2328bbe2fc8827803fdc99bb48ff5c4
Coasters v2      16dd8ded1cd2cebf81e721eefdc82e2721730683226717ec8ffdb799135be9af
Museums v1       6628bbe151ee7bbffb5e53515d30d10e6ed6858e45b7c27cf3c3b3af4bae879d
Parks v3         19537d3229511b8471801b2a0525958b05bcd2231ed033418c63834ef114f8ec
Roadside member  ccb612de965ec24613d8185cd4675d9b7bdf5672149721c8406b3bcdde21b556
```

The [City's current open-data policy](https://bouldercolorado.gov/services/open-data)
and the original `OSMP_Trailheads.xml` both identify CC0 1.0. The XML metadata
date is April 17, 2019; it describes designated access locations and native
AccessID, rather than park centers. Retained city pages separately provide
dated structured Open status, parking information and directions points. For
example, [Realization Point](https://bouldercolorado.gov/trailhead/realization-point)
identifies its parking area and road approach. The parser reads coordinates
from the city's published directions link without making a Google request.
No website prose or photographs are imported. The public attribution page links
the archive, CC0 terms and City policy and disclaims City endorsement.

The remaining sources retain the source-specific caveats in
[source review](catalog-source-review.md). No blanket Kaggle license permission
or invented open status was introduced. The NPS public GIS service returned a
403 during an attempted official-resource read; no denial bypass was attempted.

The newly reachable [IMLS source page](https://www.imls.gov/research-evaluation/data/museum-data-files)
and its [official 2018 user guide](https://www.imls.gov/sites/default/files/museum_data_file_documentation_and_users_guide.pdf)
confirm the retired initiative, commercial contributor records, and commercial
geocoding applied to physical addresses where available, otherwise administrative
or IRS addresses. The guide names Factual and a per-record source flag; the
Kaggle 25-column file lacks that flag, so it cannot safely filter those source
contributions. [IMLS terms](https://www.imls.gov/about/privacy-terms) distinguish
agency works from third-party works and do not grant rights in third-party
content. These primary documents reinforce the museum exclusion rather than
clearing all coordinates from a CC0 uploader label. Original PDF/HTML and hashes
are retained with the intake evidence. The old LOC rights URL now redirects to a
general rights guide; a collection/item-specific assessment is still required.

## First explicit Kaggle adapter

`app/catalog/boulder.py` supports only the measured v1 archive SHA, CSV member,
native IDs and reviewed CC0 attribution. `scripts/catalog_boulder_manifest.py`
builds a bounded manifest from that archive and a retained operator-page index.
The ordinary importer dispatches this explicit schema through its existing
atomic staging/activation mechanism. Overture validation remains separate;
the regional combiner refuses Boulder rather than relabeling it Overture.
Mixing source generations is still pending, not silently implemented by
successive activation (which replaces all active coverage).

Operator snapshots must match the source name, official HTTPS trailhead URL,
checksum and a non-future retrieval within 30 days. Structured status must be
Open, a parking description and unique directions point must exist, and the
current point must be in Boulder and within 0.002 degrees of the source point;
larger differences require independent review. Unknown/closed status, missing
evidence, changed arrivals and ambiguous IDs are excluded or fail closed.
The two Flagstaff Summit arrivals count as one destination. No access claim
extends beyond its evidence date; seasonal closures, fees and parking limits
remain possible and scheduler opening hours remain unknown.

Dry-run result: 36 scanned, **12 accepted**, 23 missing current evidence, one
duplicate summit destination. All 12 are nature/trailheads in Colorado. Native
identities such as `boulder:272` persist through database discovery with
`source=boulder-osmp`; original and arrival provenance travel through typed
candidates, route stops, itineraries and Studio metrics. Original source
modification date remains unknown; retrieval is not mislabeled as modification.

Reproduce using legitimately acquired originals and retained pages:

```sh
python scripts/catalog_boulder_manifest.py \
  --archive /workspace/catalog-data/intake-20261014/boulder-v1.zip \
  --page-index /workspace/catalog-data/intake-20261014/boulder-current-pages.json \
  --retrieved-at <actual-archive-retrieval-time-with-offset> \
  --output /workspace/catalog-data/intake-20261014/new-manifest.json
PYTHONPATH=backend python scripts/catalog_import.py \
  --input /workspace/catalog-data/intake-20261014/boulder-v1.zip \
  --manifest /workspace/catalog-data/intake-20261014/new-manifest.json
```

The first command refuses overwrites. The second is a database-free dry run.
Staging remains an explicit separate operation on an approved target.

## Authentic isolated PostgreSQL evidence

Used pinned PostgreSQL 18.6 in disposable container
`roadtrips-catalog-intake-20261015`, loopback port 55438. It contains public
catalog data and synthetic tests only. Production data was not copied there.
Source `catalog_authentic` and initially empty `catalog_restore` are distinct
databases. Source/restore volume and artifacts are retained.

- Final generation: `c15d1c9c224f5e13b6c8c070209eeb0ea53b04be39f6423a46624e1df0b11ec5`.
- Previous generation: `ee77cc84674be415631449e92e0e19510a4089cefd3e11646e08da6364166cbe`.
  It contains the same 12 authentic destinations with the earlier manifest.
- Repeated staging returned existing. Activation to the final generation,
  rollback to the previous generation, and return to final all preserved counts.
- The actual repository's five-mile query returned native Boulder IDs and
  retained parking provenance. Separate synthetic PostgreSQL tests preserve
  Overture IDs, rollback/storage guards and distance/antimeridian behavior.
- Two retained generations and indexes occupied **204,800 bytes**; disposable
  database size was 8,197,823 bytes. This is a small nature sample, not a
  500-place or nationwide size projection.
- Custom-format dump: **10,630 bytes**, SHA-256
  `9e2bbf8632582a0feda04be73413cc1c156c06b79f3b2d4e71b3b16f2c96afef`.
  Restore into the empty separate database matched the active generation,
  12 rows and normalized-content MD5 `681166eb3122875e06986086416f06d7`.

## Application validation

Final local backend run: **866 passed, 88.29% application coverage**, including
the four opt-in real PostgreSQL tests, above the unchanged 63% floor. The 28 new
unit cases cover source identity, geometry-field order, status/parking evidence,
changed/future/stale arrivals, checksum/URL/rights guards, duplicate destinations,
profile schemas/limits, no invented coordinates and combiner refusal. Ruff
format/lint and diff checks pass. Frontend: **314 passed**, 90.23% line/statement
coverage; format, lint and production build pass. The existing large-bundle
warning remains.

The first full backend run, concurrent with frontend work, failed the existing
`test_process_caps_across_private_event_loops[nearby-4-8]` assertion because it
observed peak four rather than eight. All other 865 tests passed. The full rerun
passed without modifying that test, concurrency code or thresholds. This is
recorded as an intermittent timing result, not hidden or treated as deployment
acceptance. Exact pushed-head CI is checked separately.

## Exact remaining rollout gates

The roughly 500-place target is not met: **12 nature / 0 roadside / 0 entertainment /
0 beaches / 0 landmarks / 0 museums / 0 national parks**. There is no food or
nightlife batch. Every state/DC except Colorado is a gap, explicitly including
Alaska and Hawaii. A Boulder-only cutover would leave nearly all existing routes
without discovery. Do not deploy it as national coverage.

Before Neon writes, the [rollout runbook](neon-places-catalog.md) requires current
production recovery evidence. The shared
[S3 runbook](https://github.com/elischiffler/hosting-ops/blob/main/scripts/roadtrips-s3/README.md)
describes installed daily backup, hourly freshness and weekly isolated restore
jobs, but its last recorded acceptance is September 28. This environment has no
authorized host/AWS/SSH credential or current status artifact for those jobs.
The deployed HTTPS release endpoint only replaces checked-main API containers;
it does not run migrations or backups. The question for a current evidence
location or existing authorized host-access path remains pending. No new
credential, broader security permission, private-data destination or paid plan
was provisioned to work around that gate.

After recovery and broader eligible data are ready, use the existing PR/review,
exact-main CI and serialized EC2 deployment path. Then capture actual production
version and authenticated chat/Studio, route/evening/history/attribution results
with source IDs and zero Tripadvisor discovery calls. Current green baseline
health or local catalog success does not establish any of those final journeys.
