# Second expansion increment: 12 reviewed nature arrivals

The second increment adds **12 nature destinations** to the preserved 103-place
heritage increment. At this checkpoint PR #42 proposed **115 additions**, for a hypothetical
**197-place** union with the 82 live starter records. The remaining shortfall is
**303**. The 103-place review, normalized preview and original evidence archive
remain unchanged; [its original receipt](evidence/catalog-expansion-103-20261015.json)
retains its historical counts and validation.

The [new per-place review](data/catalog-expansion-20261015/nature-12-review.json)
contains source/license acquisition evidence, exact native IDs, original/current
arrival coordinates, current operator evidence dates/hashes, actual driving
checks, exclusions and deduplication. The
[12-row preview](data/catalog-expansion-20261015/reviewed-nature-12.preview.jsonl)
is the existing Boulder adapter's actual output, not an alternative import format.
No production data, generation pointer, deployment or credentials changed.

## Authentic source and current-access review

The existing Kaggle token successfully retrieved the exact pinned Boulder v1
archive: **4,705,510 bytes**, SHA-256
`5dfb978b50c8d238eda2362dcd99b1a1b2328bbe2fc8827803fdc99bb48ff5c4`.
No token value was printed or created. Both original trailhead XML metadata
members identify CC0, consistent with the independently retained
[City open-data terms](https://bouldercolorado.gov/services/open-data).
Attribution remains **City of Boulder Open Space and Mountain Parks (CC0 1.0);
Kaggle mirror by paultimothymooney. No City endorsement.** Photographs and website
prose are not imported.

The 36 native archive records break down as follows: 12 starter identities remain
untouched; the alternate Flagstaff Summit arrival remains excluded; 23 other
pages were attempted. Of those, 18 had the exact City name, structured **Status
Open**, positive visitor parking and one City-published directions coordinate
consistent with the original archive. All 18 also passed actual OSRM driving
**destination** checks. Checks and places are not interchangeable counts.

Manual arrival/access review then withheld six more:

- Enchanted Mesa is held as an alternate Chautauqua-area arrival; Chautauqua
  represents that destination in this increment.
- South Teller has a specifically published October 20, 2026 trailhead closure;
  it needs rechecking rather than invented scheduler blackout hours. Teller Farm
  North remains the selected farm/trail destination.
- Centennial has published Red Rocks construction closures with unresolved
  current access scope.
- Boulder Valley Ranch, Eagle and Left Hand remain outside the increment: the
  operator specifically directs checking muddy-condition closures, but the
  linked dynamic feed returned HTTP 503. Alternate arrivals also must not
  inflate the same ranch destination count.

The other five attempts are excluded: Dry Creek explicitly reports Closed; NCAR
lacks the required verified parking evidence; Fourth of July, East Boulder at
White Rocks and the historical Settler's Park URL returned 404. No changed name,
new URL or coordinates were silently substituted to make them pass.

The accepted destinations are **Joder Ranch, Bobolink, Chautauqua, Gregory Canyon,
Cottonwood, Four Mile Creek, Foothills, Wonderland Lake, Teller Farm North,
Cherryvale, Buckingham Park and Sawhill Ponds**. Their arrival points are the
City's published directions coordinates, not Google geocoding or road snaps.
The v1 embedded Y-column error remains excluded by the existing parser.

All 12 unchanged current points pass a destination check within **14.67 metres**.
Every raw response hash and destination field was rechecked. Routing evidence is
credited to **OSRM; © OpenStreetMap contributors** under the
[OpenStreetMap attribution/ODbL terms](https://www.openstreetmap.org/copyright).
The source page supplies the independent public-parking basis; network proximity
alone grants no access. Gregory Canyon's operator warns of cooler-month road
closures due to ice/snow. Fees, parking availability, weather and future access
remain qualified; no ratings or scheduler opening hours are imported.

## Coverage, bounds and reproduction

This is one additional Colorado nature cluster, connected to US-36/Denver-area
routes, rather than new national geographic coverage. It combines foothill hikes
with eastern wetlands and ponds. None shares identity or lies within 250 metres
of another accepted addition or starter. The hypothetical union remains **43
states and DC**, with primary counts: roadside 1, entertainment 1, nature 24,
beaches 12, landmarks 106, museums 17, national parks 36. CT, DE, MS, NH, VT, WI
and WV remain empty. Food/nightlife is still absent.

The producer re-admits all originals through `kaggle-boulder-trailheads/1`:
**12 accepted**, 36 source rows scanned, 24 missing selected operator evidence.
Those 24 include the starter identities and deliberately withheld records; they
are not 24 new failures or extra approved places. Actual archive plus selected
publisher-page bytes total **5,433,804**. The adapter now counts publisher
snapshots against its existing byte budget; previously it reported only archive
bytes. A boundary regression proves the exact budget passes and one byte less
fails. The source schema, IDs, coordinates, attribution, records and hard/default
limits are unchanged.

A mixed recipe containing the six preserved heritage children plus this nature
input revalidates **115 additions, zero duplicates and 9,847,771 source bytes**,
under the existing 500-row/20 MiB expansion bounds. This recipe omits the starter
and must never be activated. A full 197-place replacement still requires the
owner's 82-place original-source recipe, not the public identity export. Its
combined source-byte budget must be explicitly remeasured; a bounded **32 MiB**
assembly setting is available within the unchanged existing hard ceiling. The
starter's newly counted City snapshot bytes must also be included.

Focused validation passes **84 tests** across Boulder admission, mixed-source
assembly, importer and preserved expansion/review checks. Ruff format/lint and
diff checks pass. Rebuilding from a relocated archive reproduces all 12 normalized
records exactly. The earlier passed 103-place evidence remains separate.

Retained source archive:
`/workspace/catalog-expansion-phase2-20261015/roadtrips-nature-12-evidence-20261015.tar.gz`
(**5,122,900 bytes**), SHA-256
`98b867d86156fffc3e554803a21da9c64f9e0313f27a686bea70237467859345`.
It contains the original pinned Kaggle archive, unmodified City pages, selections,
rights/closure evidence, raw driving responses, acquisition index and source
manifest. No source archive, publisher page dump, publisher key or credentials
are committed. The original 103-place archive remains SHA-256
`b2b13b60c2c62f4b47933a97b51f27d0288ac64661e78bf68078c773dae1e318`.

After unpacking to a private local evidence directory, use the backend Python
environment and the existing manifest helper. Copy the original ZIP into a new
work directory, relocate only the `path` fields in `boulder-selected-pages.json`
to `<unpacked>/boulder-pages/<original-basename>`, and write that relocated index.
Then run:

```sh
python scripts/catalog_boulder_manifest.py \
  --archive <new-work>/boulder-v1.zip \
  --page-index <new-work>/relocated-selected-pages.json \
  --output <new-work>/boulder-v1.zip.manifest.json \
  --retrieved-at 2026-10-15T03:37:14.739124+00:00
PYTHONPATH=backend python scripts/catalog_import.py \
  --input <new-work>/boulder-v1.zip \
  --manifest <new-work>/boulder-v1.zip.manifest.json
```

Both commands are database-free without an explicit stage/activation action.
Keep original hashes/dates, and never overwrite retained originals. Evidence
older than 30 days needs actual new acquisition and review. The deployment owner
retains all import, activation and rollout ownership through the parent.

## Independent intake leads kept outside admission

These attempts have **zero additional import approvals**:

- The official USDA Forest Service Recreation Opportunities ArcGIS layer exposes
  its actual schema and a lowercase `open` field. A bounded, explicitly truncated
  500-record parking-description subset was retained (1,006,659 bytes) at
  `/workspace/catalog-expansion-phase2-20261015/fs-open-parking-500.json`, with exact
  request/hash in `fs-acquisition.json`. An open flag alone is not independently
  verified public arrival/current access. The inspected operator-detail read
  failed; current facility access, explicit jurisdiction and upstream rights
  review remain necessary. Source NAD83 fields must not be mislabeled WGS84.
  Needed assets: exact dataset rights/metadata plus legitimately retained current
  operator parking/approach/closure evidence for selected native `recareaid`s.
- AllThePlaces' download index returned **403**. It was not retried through
  alternate hosts/routes or relabeled as acquired data. Needed assets: an
  authentic bounded selected-spider GeoJSON, pinned run/source metadata and
  CC0/rightful upstream evidence, followed by current operator arrival review.
- Wikidata main-namespace structured data has an independently readable CC0
  policy, but the entity-data and local policy acquisitions returned **403**.
  No entity JSON or coordinate was imported. Needed assets: legitimately retained
  selected entity JSON/revisions and license evidence, then current operator
  identity/access/parking evidence. This is not Kaggle intake.
- Several additional NPS coastal snapshots were read successfully but lacked
  usable parking arrivals. Gulf Islands has two positive-capacity beach lots,
  but its multi-state jurisdiction/current-access evidence still needs explicit
  per-lot review; the zero-capacity Opal lot remains excluded.

The original-source handoff has subsequently been recovered through the private
Library and all 143 inventoried files verified. Its exact 82-place recipe now
reproduces successfully. The [third increment and complete handoff](catalog-expansion-venues-17.md)
record the current 214-place offline union and resolved artifact blocker; the
counts and original evidence above retain this second increment's scope.
