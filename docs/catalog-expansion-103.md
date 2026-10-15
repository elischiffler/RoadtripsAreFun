# Independent catalog expansion — October 15, 2026

This PR contributes **103 reviewed additional arrivals**, in six independent
source batches. It does not replace, activate, merge or deploy the initial
82-place release. The hypothetical union is **185 unique places across 43 states
and DC**, still **315 short** of roughly 500. Full replacement-generation
assembly awaits the original 82-place recipe and its retained source artifacts.
No database writes, new credentials, paid data acquisition, authentication,
security-policy or deployment changes occurred.

The [review ledger](data/catalog-expansion-20261015/review.json) contains every
stable ID, native facility selection, name, state, category, original arrival
coordinate, source URL, SHA-256 and operation/access evidence date. The
[103-row preview](data/catalog-expansion-20261015/reviewed-103.preview.jsonl)
contains the actual existing adapter's normalized output and provenance. It is
review material, not an arbitrary-row import format. The
[aggregate receipt](evidence/catalog-expansion-103-20261015.json) records measured
counts, bounds, source fingerprints, driving checks and the evidence archive.
The [excluded queue](data/catalog-expansion-20261015/exclusions.json) accounts for
all 154 withheld units; none is added to accepted counts.

## Delivered batches and useful routes

Each batch reuses `nps-heritage-arrivals/1`, with one selected facility per parent
unit. Counts below represent destinations rather than extra entrances or rides.
The groupings connect actual visitor arrivals and named roads; they are review
clusters, not a claim of continuous national route coverage or measured detours.

| Batch | Scope and example connections | New places | Landmarks | Museums |
| --- | --- | ---: | ---: | ---: |
| heritage-01 | Southwest: I-40 at El Malpais/El Morro, I-17 at Montezuma Castle/Tuzigoot, US-89 Sunset Crater–Wupatki, US-64/550 Aztec Ruins | 22 | 20 | 2 |
| heritage-02 | Pacific: I-5 Fort Vancouver, US-395 Manzanar, California coastal urban stops; Hawaii's separate island road networks | 10 | 10 | 0 |
| heritage-03 | Northern Plains: I-90 Devils Tower/Jewel Cave connections, US-26 Fort Laramie–Scotts Bluff, I-29/US-75 Pipestone | 14 | 13 | 1 |
| heritage-04 | Great Lakes/Ohio–Tennessee: I-70/I-75 Dayton, I-75 River Raisin, I-77 Canton, US-31E Lincoln Birthplace | 15 | 13 | 2 |
| heritage-05 | Gulf/Southeast: I-30 Clinton Birthplace, I-35 Waco/San Antonio Missions, I-85 Kings Mountain/Cowpens, US-158 Outer Banks | 23 | 21 | 2 |
| heritage-06 | Mid-Atlantic/Northeast: I-95 Baltimore/Fredericksburg, US-40 Fort Necessity, Massachusetts Lowell/Minute Man/Springfield connections, DC Frederick Douglass | 19 | 18 | 1 |
| **Total** | **34 states and DC in the additions** | **103** | **95** | **8** |

The eight explicitly named museums are Pipe Spring, Tumacácori, Wilson's Creek,
Camp Nelson, Mill Springs Battlefield, Plains High School/Jimmy Carter, Wright
Brothers and Springfield Armory. Other visitor centers remain landmarks in the
primary reporting counts. Heritage designations are not relabeled national parks.
The existing schema retains daytime/culture labels; it imports no evening hours.

The hypothetical 185-place union retains all starter categories: roadside 1,
entertainment 1, nature 12, beaches 12, landmarks 106, museums 17, national parks
36. These are exclusive primary reporting counts. It remains heritage-heavy.
There are **no new food/nightlife, dedicated entertainment, beach or roadside
records**. CT, DE, MS, NH, VT, WI and WV remain empty. Alaska retains only its
starter arrival; Hawaii gains three actual visitor facilities. Exact state counts
for the additions and hypothetical union are in the receipt.

## Source, rights and current access

The public NPS map service's `parktiles.sd_parks` inventory was acquired through
this bounded identity-only query:

```sql
SELECT parkcode AS unit_code, fullname, designation, states
FROM parktiles.sd_parks ORDER BY parkcode
```

It returned 474 identities in 57,224 bytes, SHA-256
`edb47cebd2274266bc751047817cbf50d1c2d9908c4dde0d040e6ddacc5d94a2`.
No inventory geometry was requested or used. The adapter adds this exact
independently retained fingerprint while preserving the initial release's
original fingerprint. Provenance records the fingerprint actually used.

After excluding the starter's 12 heritage identities, 257 inspected heritage
units had ordinary successful official snapshot reads, totaling 7,804,267 bytes.
Every snapshot uses `https://www.nps.gov/<code>/structured_data_<code>.json`.
Identity/name, explicit US facility state, finite original facility coordinates,
listed `Parking - Auto`, actual directions, nonempty published weekly schedule
and the existing dated-closure exclusions are required. Manual review then
withheld contradictory schedules, closure language, remote information offices,
partner-site identity substitutions and non-driving/reservation-only arrivals.
Malformed schedules remain excluded; they were not edited into passing data.

Six of the 109 remaining actual facility points failed the ordinary driving
**destination** check and are withheld: Appomattox Court House, Chamizal, C&O
Canal's selected Great Falls facility, Fort Smith, Fort Union Trading Post and
Pearl Harbor. The new Antietam check succeeded; this does not rewrite the initial
release's historical `NoSegment` result. Every admitted point retains its NPS
coordinates, with a destination snap distance at most 71.77 metres. All retained
raw response checksums and destination fields were independently rechecked.

Driving review used the public OSRM driving service at no more than one request
per second: **OSRM routing engine; © OpenStreetMap contributors**, subject to
[OpenStreetMap attribution and ODbL](https://www.openstreetmap.org/copyright).
An offset origin is only a network probe. These checks establish network
proximity of the unchanged facility destination; they do not establish parking
availability, legal access to every nearby feature, a real end-to-end road trip,
future opening or shuttle availability. Raw routing points never replace NPS
facility coordinates. NPS parking/directions supply the separate public-arrival
basis. Road names in the retained review provenance come from this routing check.

The NPS [ownership policy](https://www.nps.gov/aboutus/disclaimer.htm) and
[structured-data publication guidance](https://www.nps.gov/subjects/digital/structured-data.htm)
were independently retrieved and hash-retained. The existing
[government-work notice](../frontend/public/licenses/LicenseRef-US-Government-Work.txt)
and source attribution remain mandatory: **National Park Service factual
heritage-unit and visitor-arrival data. No claim to original U.S. Government
works. No NPS endorsement.** Only factual identity/location/access fields enter
the catalog; photographs, website prose, contact details and third-party creative
works do not. Source modification dates remain unknown. Acquisition dates are
not represented as publication dates. No ratings are supplied.

The fresh environment exposes the existing `KAGGLE_API_TOKEN`; legacy
`KAGGLE_USERNAME`/`KAGGLE_KEY` and local `kaggle.json` are absent. Only presence
was inspected; no token was printed or created. This batch is **official NPS
data**, not a new Kaggle intake. The earlier archive-specific rights findings
still apply, particularly unresolved contributor/geocoding rights in IMLS and
historical ride/photograph coordinates. The unavailable 329 Overture candidates
remain unreviewed and outside this expansion.

## Deduplication and validation

A single read-only query exported the starter generation's 82 public identities,
names, coordinates, regions and categories. The
[identity export](data/catalog-expansion-20261015/starter-82-identities.json) is
hash-pinned in the review ledger. No user/application table was queried.
Source IDs, parent unit codes, selected native facility IDs, names, addresses,
URLs and spatial relationships were reviewed. The rebuild additionally refuses
shared identity or same normalized name/state within 250 metres against either
the starter or another addition. No new place pair lies within 250 metres of
another addition or starter. The two close pairs already present among the
starter's distinct Boulder trailheads are preserved unchanged and documented.

All six original-source bundles and their mixed expansion-only recipe pass
`prepare`: **103 accepted, zero admission rejects, zero duplicates**, 4,413,967
inspected bytes, under the unchanged 500-row / 20 MiB bounds. The preview is the
actual resulting output. A second rebuild at a relocated artifact path produced
the same normalized records; existing output paths are refused.

Focused verification: **116 tests pass**, covering expansion source/fact changes,
starter identity and spatial conflicts, atomic publication, missing/altered
source evidence, new/old inventory fingerprints, closure/access review, ordinary
NPS admission, mixed-source assembly, importer and Overture review/combination.
Ruff format/lint, attribution-page Prettier and `git diff --check` pass. The
public attribution page credits OSRM/OpenStreetMap driving evidence. No full
frontend/application suite,
production staging, database activation/restore or deployment acceptance is
claimed for this data addition. The test-image context explicitly includes the helper and public review facts;
its filesystem layout passes the ten expansion tests. Runtime image contents
are unchanged. The existing catalog SQL schema, importer ceilings, source
namespaces and application contracts are unchanged.

## Artifact and import handoff

Retained evidence archive:
`/workspace/catalog-expansion-20261015/roadtrips-expansion-103-evidence-20261015.tar.gz`
(1,264,176 bytes), SHA-256
`b2b13b60c2c62f4b47933a97b51f27d0288ac64661e78bf68078c773dae1e318`.
It contains the original inventory, all 257 source snapshots and acquisition
index, 109 raw driving responses and summaries, policy snapshots, six admitted
bundles/sidecars and an expansion-only mixed recipe. It contains public source
evidence and no credentials, user data, publisher browser keys or image binaries.
Original source archives/page dumps remain outside Git.

Unpack the evidence into a separate local directory. Rebuild the six child
bundles using the tracked review ledger and relocated originals:

```sh
python scripts/catalog_expansion_manifest.py \
  --artifacts /path/to/unpacked-evidence \
  --review docs/data/catalog-expansion-20261015/review.json \
  --baseline docs/data/catalog-expansion-20261015/starter-82-identities.json \
  --output /path/to/new-expansion-bundles
```

The helper has no network or database calls and does not publish anything if a
child fails validation. It refuses changed source facts and existing outputs.
Evidence older than 30 days must be reacquired and reviewed; do not alter a
fingerprint or retrieval timestamp to make expired evidence pass.

**Do not activate the expansion-only recipe.** Activation replaces all active
coverage. The deployment owner must recover the **original-source child inputs
and manifests** for starter generation
`cfdb55a51fe8abfe015fcbb12b8d23c7a09fa71945d95758bd00756ec502ada0`
(original aggregate manifest SHA-256
`24dd309f74e156efcc4f8a4a48dc2a431fc39df497c70f8e0dfe1a215a7307a8`),
then use `scripts/catalog_mix.py` on those original children plus these six new
children. Nested mixed bundles and normalized previews are not source substitutes.
The fresh environment has neither that recipe nor the old Overture source
extracts. The public identity export supports deduplication, not original-source
readmission or exact recovery of the starter recipe.

The prior starter receipt counted 17,373,539 source bytes. Adding this batch's
4,413,967 inspected bytes would exceed the old 20 MiB pilot setting. For a full
185-place assembly, explicitly choose and record a bounded **24 MiB** command
budget (`--max-rows 500 --max-bytes 25165824`) within the existing 100 MiB hard
ceiling; defaults and hard ceilings are not changed here. The actual combined
artifact must still be revalidated and measured; that sum is an input-budget
estimate, not a completed replacement-generation receipt.

The deployment owner retains rollout/activation ownership through the parent
coordinator. After original-source assembly, the existing staged import,
recovery, review and activation/deployment gates still apply. Nothing here
provides an executable production transaction or activates a partial generation.

## Next expansion scope

Prioritize the missing entertainment, niche roadside, nature/beaches and
food/nightlife batches, plus the seven empty states, over further heritage
volume. The original 329-candidate Overture extracts/sidecars and reviewer queue
are the most useful missing artifact. Review licensed original venue points
against current operator visit/parking evidence along the established corridors.
Keep closed, ambiguous, administrative and remote information-only locations
excluded. The 103-place batch is useful now; it does not meet the approximately
500-place goal or establish nationwide corridor coverage.
