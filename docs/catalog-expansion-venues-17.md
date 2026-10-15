# Third increment: museums, food and evening visits

PR #42 now supplies **132 reviewed additions**: the preserved heritage 103,
nature 12 and this **17-place** venue increment. Recovered original source files
allow actual offline re-admission of **214 unique places across 44 states and
DC**, including all 82 starter records. This remains **286 short** of roughly
500. No database staging, production write, activation, merge or deployment was
performed. The deployment owner retains the release decision.

The [per-place ledger](data/catalog-expansion-20261015/venues-17-review.json)
records stable IDs, unchanged licensed coordinates/categories, source provenance,
publisher URLs/hashes/access dates, venue-specific arrival profiles, driving
evidence and limitations. The [17-row preview](data/catalog-expansion-20261015/reviewed-venues-17.preview.jsonl)
is actual existing-adapter output. The [combined receipt](evidence/catalog-expansion-214-20261015.json)
records measured source/release/rights, geographic counts and reproduction facts.
These public facts do not substitute for the retained source inputs.

| Primary category | New destinations | Geographic / driving connections |
| --- | --- | --- |
| Museums, 10 | Alaska Aviation; Gone With the Wind at Brumby Hall; California Heritage; Armenian Museum of America; Connections Seattle; Phoenix Art; Jacques Marchais Tibetan Art; Seattle Pinball; Historic Richmond Town; Fort Ward | Anchorage road-network side trip; I-75 Marietta; I-10 Santa Monica/Phoenix; I-90 Watertown; I-5 Seattle; I-278 Staten Island; I-395 Alexandria |
| Food, 5 | Gates & Brovi; Lombardino's; Everly; Lallande; Begonia | Actual Madison neighborhood approaches near I-90/I-94 and the US-12/14/18 beltline |
| Nightlife, 1 | Garth's Brew Bar | Madison Monroe Street, published public evening service and street parking |
| Entertainment, 1 | SEA LIFE Arizona Aquarium | I-10/US-60, Arizona Mills Neighborhood 1 / Entrance 1 visitor approach |

There are nine states in this increment: AK 1, AZ 2, CA 1, GA 1, MA 1, NY 2,
VA 1, WA 2, WI 6. Wisconsin is new coverage. These clusters do not establish
continuous national corridor coverage or measured detour times. CT, DE, MS, NH,
VT and WV remain empty. The 214-place union's exclusive primary counts are
roadside 1, entertainment 2, nature 24, beaches 12, landmarks 106, museums 27,
national parks 36, food 5, nightlife 1. Evening coverage remains very sparse.

## Source and access evidence

Eleven arrivals reuse genuine records from the earlier unreviewed Overture
pool. Six food/nightlife records come from a bounded fresh public-S3 extraction
at pinned release **2026-09-23.1**, using the existing extractor and source
normalizer. The retained public STAC index pins that release. The extraction
stopped at its 40-record limit; it did not complete its bounding box. Its actual
decoded/output count was 56,570 bytes; network range-transfer overhead was not
measured. No paid service or new credential was used. The previously verified
Kaggle datasets remain source children of the full union; these 17 are Overture,
not relabeled Kaggle records.

All selected upstream provenance passes the existing Apache-2.0,
CDLA-Permissive-2.0 and Foursquare NOTICE checks, using the committed license
texts. Credit remains **Overture Maps Foundation; BrightQuery; Foursquare;
Microsoft; Overture; Overture-signals; meta**, with row-specific upstream facts.
The original source/native IDs, labels and coordinates are preserved.

Nineteen retained operator pages, acquired **October 15, 2026**, independently
establish current published public visits and parking at the matching addresses.
Public parking may require walking; native venue points are never rewritten as
invented entrance GPS or road snaps. Each point passes an actual OSRM driving
**destination** check, maximum **30.844 metres**. Bounds are specific to the
inspected venue, with named frontage or explicit public visitor parking. An
unnamed link alone does not establish access or a street name. Driving review
credit is **OSRM; © OpenStreetMap contributors**, under the existing
[OpenStreetMap attribution / ODbL terms](https://www.openstreetmap.org/copyright).
No rating, opening interval, future parking availability or access permission is
invented. Weekly service evidence is not imported as scheduler opening hours.

Limitations remain attached per place: Connections is Sunday-only; the Armenian
museum's administrative hours are not public gallery hours; Seattle Pinball is
seven-and-older; Brumby Hall requires the published Hilton approach and a walk;
restaurant service days differ; Badger games affect Monroe Street parking.
SEA LIFE is a specific tenant/Entrance 1 approach, with tickets and a walk from
the public lot, not a mall-center coordinate. The checked unnamed links are
reported as unnamed.

The [not-admitted queue](data/catalog-expansion-20261015/venues-not-admitted.json)
accounts for **148 of 165 shortlisted candidates**. Many still require review;
they are not 148 completed negative access determinations. Examples of explicit
holds include the old Chandler Museum address, Cadre's conflicting address
pages, Garibaldi's redirect to an unrelated author site, children's-party-only
eligibility, and Staten Island Zoo's published October 16–19 general-entry
closure. HTTP 403 denials were not bypassed. A source open flag or successful
homepage read does not clear a venue.

## Reproduction and import handoff

The original-source handoff was recovered through the private Library:
`catalog-release82-plus-329-source-handoff-v2.tar.gz`, **9,181,249 bytes**, SHA-256
`14874d14cc7e509579485b9770c07ccb7e3207c7722b8ebb91c7abb380d5cd76`.
All **143** inventoried source files were verified. The six-child recipe
reproduces the exact starter 82 IDs and coordinates and its unchanged generation
`cfdb55a51fe8abfe015fcbb12b8d23c7a09fa71945d95758bd00756ec502ada0`.
This resolves the source-artifact blocker recorded at the earlier checkpoints.

The new source-only archive is
`roadtrips-venues-17-evidence-20261015.tar.gz`, **948,272 bytes**, SHA-256
`98a5502599689c86abb81f774f471fc2c43b54d279a1c121cfd7bb0b3df2c7ad`.
Its 52 files include original bounded source JSONL/sidecars, selected retained
operator pages, raw driving responses, evidence summaries, review and an offline
`rebuild.py`. It is retained in the private Library; private handles are provided
to the coordinating owner separately and are not embedded in public Git.

After legitimate private materialization, rebuild the 17-place child:

```sh
python <source-folder>/rebuild.py --repo <expansion-checkout> --output <new-path>.jsonl
```

An actual archive extraction into a different directory reproduced identical
normalized rows: **17 accepted, zero rejects, 5,909,157 aggregate evidence bytes**.
The existing `roadtrips-arrival-review/1` schema and source/license guards remain
in force. New static venue profiles additionally bind their exact inspected
coordinates; changed points, even with a matching changed drive receipt, fail.
Evidence older than 30 days needs renewed review rather than a forged date.

Focused validation passes **200 tests** covering arrival review, source admission,
mixed-source deduplication, the preserved heritage/nature inputs and roadside
rights. All 183 backend Python files pass Ruff format/check. The new cases
exercise all 17 profiles, absent access facts, closure language, changed native
points with matching changed drive receipts, and deduplication against the prior
197 records. Full application suites run in PR CI; they are not duplicated here
for this bounded catalog change. A draft PR's skipped CodeRabbit status is not
an independent completed review.

For the full replacement-generation candidate, use **all six original starter
children**, all six heritage-103 children, the nature-12 Boulder child, and this
17-place Overture child as flat inputs to `scripts/catalog_mix.py`. Nested mixed
bundles are intentionally refused. Use explicit `--max-rows 500 --max-bytes
41943040`: measured aggregate evidence is **33,865,430 bytes**, above the prior
32 MiB run budget but below the unchanged **100 MiB hard ceiling**. No default
or safety threshold changed. Actual full re-admission returns **214 accepted,
zero duplicates**. Source-specific unselected rows remain recorded as such.

The helper commands only produce files. Activating an increment alone would
replace retained coverage; the deployment owner must use the complete recipe
and established release/backup/restore gates. Prior 103- and 12-place source
archives and evidence remain intact. This PR does not authorize rollout.
