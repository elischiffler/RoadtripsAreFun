# Separate diversity increment: 29 natural-unit arrivals

This follow-on contributes **29 reviewed arrivals**, comprising **27 nature
destinations and two national parks**, after PR #42's 214-place proposal.
PR #42 stays frozen at `88900933480dc5034b6cba41374533c5ce69892c`.
The complete source-backed union now re-admits **243 unique records across
46 states and DC**, with all prior 214 rows and provenance unchanged. It remains
**257 short** of roughly 500. Nothing was staged, activated, merged or deployed
to production; rollout remains the deployment owner's responsibility.

The [per-place review](data/catalog-expansion-20261015/nps-nature-29-review.json)
contains each stable ID, native facility selection, unchanged arrival coordinate,
category, explicit facility state, operation URL/date/hash and driving evidence.
The [29-row preview](data/catalog-expansion-20261015/reviewed-nps-nature-29.preview.jsonl)
is actual source-adapter output, not an alternative arbitrary-row import format.
The [receipt](evidence/catalog-expansion-243-20261015.json) records measured
counts, source rights, bounds and reproduction; the
[not-admitted queue](data/catalog-expansion-20261015/nps-nature-not-admitted.json)
accounts for the other 46 source units without declaring all of them closed.

## Useful arrival clusters and category balance

| Cluster | Actual public visitor arrivals and source-published approaches |
| --- | --- |
| Coastal and wetland | Assateague's Maryland visitor center off Route 611; Cape Cod Salt Pond off Route 6; Cape Lookout's Harkers Island mainland center; Big Cypress Oasis on US-41; Gulf Islands' William Colmer center off US-90/I-10; Jamaica Bay's Cross Bay Boulevard parking approach; Padre Island Malaquite via Park Road 22 |
| River, lake and prairie | Bandy Creek off TN-297; Big Thicket at US-69/287 and FM-420; Buffalo River Tyler Bend off US-65; Big Spring off US-60/MO-103; St. Croix River off US-8/WI-87; Niobrara's Valentine visitor center via US-83; Obed in Wartburg; Tallgrass Prairie on K-177/US-50 |
| Mountains and western corridors | Blue Ridge Parkway's Asheville center via I-40/US-74A; Curecanti Elk Creek off US-50; Bighorn Canyon's Lovell center at US-14A/US-310; Little River Canyon via AL-35/I-59; Lake Mead via US-93/Lakeshore Road; Carl Hayden at US-89; Santa Monica Mountains via US-101/Mulholland; Whiskeytown via I-5/CA-299; Lands End's Merrie Way parking approach; Pictured Rocks Munising Falls and Sleeping Bear's Empire center |
| New national-park coverage | New River Gorge Canyon Rim via US-19/I-64/I-79, and White Sands' visitor center off US-70 |

There are **22 states** in this increment. Mississippi and West Virginia are new
coverage, using explicit facility addresses; Gulf Islands' Florida headquarters
is not substituted for its Mississippi arrival. These are useful geographic
connections, not measured trip detours or proof of continuous corridor access.

The union's exclusive primary counts are roadside 1, entertainment 2, nature 51,
beaches 12, landmarks 106, museums 27, national parks 38, food 5, nightlife 1.
Seashore/lakeshore visitor centers are counted as nature arrivals, rather than
inflating beach-parking counts. Recreation areas and preserves are not relabeled
national parks. CT, DE, NH and VT remain empty; entertainment, roadside and
evening coverage remain sparse. No claim of complete national coverage is made.

## Authentic primary evidence and access limits

The existing public NPS identity inventory returned 474 units, SHA-256
`edb47cebd2274266bc751047817cbf50d1c2d9908c4dde0d040e6ddacc5d94a2`.
It contributes names/designations only. No map geometry, park centroid or label
state enters an arrival. Seventy-five previously uncovered natural-unit snapshots
were acquired directly from `https://www.nps.gov/<code>/structured_data_<code>.json`
on **October 15, 2026**, retaining **5,950,165 bytes**. No Kaggle dataset or paid
service is claimed for these new records. The existing verified Kaggle children
remain unchanged in the complete union.

Every selected facility has an explicit domestic physical-address state,
`Parking - Auto`, visitor directions, nonempty published weekly operation and
the existing dated-closure checks. Manual review excludes contradictory access,
intermittent current opening and unsuitable point roles. Native visitor-center
coordinates remain unchanged. Names, address fields, native numeric facility IDs
and unknown source modification dates retain their original meanings.

All 29 pass an actual OSRM driving **destination** check within **71.55 metres**.
The new profile additionally reopens the retained raw response, verifies its
SHA-256, requires two waypoints, and matches the destination's road/distance to
the inspected receipt. A nearby road alone grants no access: independent NPS
visitor/parking evidence is required. Offset origins are network probes, not
journey starts. Road snaps, invented parking GPS, ratings and scheduler opening
intervals are not imported. Driving evidence credit remains **OSRM; © OpenStreetMap
contributors**, under the existing [OSM attribution/ODbL terms](https://www.openstreetmap.org/copyright).

Important qualifications stay attached per place:

- Harkers Island is the public mainland visitor/picnic/kayak arrival; offshore
  Cape Lookout locations require separate boat/ferry access.
- Carl Hayden's visitor center is public, but the operator reports Glen Canyon
  Dam tours closed. Tour access is not implied.
- St. Croix's selected building operates mid-April–October and closes in winter.
  Other centers publish weekday, weekend-only or seasonal hours; these are not
  converted into invented scheduler intervals.
- White Sands' visitor arrival does not guarantee access along Dunes Drive or
  US-70 during missile tests or other restrictions. Weather, fees, reservations,
  road sections and future parking availability always need checking.

Withheld examples include Travertine Nature Center's `NoSegment`, Museum of the
Sea's intermittent October–April visits, Mojave's unresolved current approach
conditions, and the Mississippi River center's expressly labeled walk-up point
whose published vehicle parking is elsewhere. Gauley River redirects to New
River Gorge's Canyon Rim center and is not counted as another arrival. Remote
information offices and unverified park/state/parking records remain outside.

The independently retained [NPS ownership policy](https://www.nps.gov/aboutus/disclaimer.htm)
and [structured-data guidance](https://www.nps.gov/subjects/digital/structured-data.htm)
support the existing `LicenseRef-US-Government-Work` notice. Attribution is
**National Park Service factual natural-unit visitor-arrival data. No claim to
original U.S. Government works. No NPS endorsement.** Only factual fields enter
the rows; photographs, creative descriptions and third-party material are not
imported. Acquisition dates are not represented as source modification dates.

## Existing schema and reproducible handoff

The database schema and public identity namespace stay unchanged. An explicit
`nps-nature-visitors/1` profile within `nps-public-arrivals/1` admits only the
29 inspected unit/facility selections. It reuses guarded NPS facility decoding,
then applies natural-unit identities and categories instead of heritage labels.
The existing beach path and every prior source remain unchanged. No credential,
paid-source, dependency, security or import-hard-ceiling change is introduced.

The atomic file-only producer publishes two existing-schema children of 20 and
nine arrivals. It rechecks the reviewed 214 identity facts, prior unit coverage,
native facility reuse, name/state/distance duplicates, raw source evidence and
every expected normalized row/provenance before publishing any final output.
Existing outputs are refused; any later child failure publishes none.

Private source archive **version 1**: `roadtrips-nature-29-source-20261015.zip`,
**995,397 bytes**, SHA-256
`da9f66bc7345a9bf6e1e9f2844c60818b6e25eeec03dd02d7e9fbf71d6a98a2c`.
Its 124 files include all 75 original snapshots, 31 raw driving responses,
unaltered acquisition metadata, the reviewed portable driving summary, original
inventory, policy evidence, baseline review facts, exclusions and `rebuild.py`.
The ZIP is retained in the private Library; exact private handles go to the
coordinator separately. Original source dumps and browser keys are not committed.

With Python 3.12 and the follow-on checkout, unpack the ZIP and run:

```sh
python -X utf8 <source-folder>/rebuild.py \
  --repo <follow-on-checkout> --output <new-directory>
```

Use the PR #44 portability-fix checkout with this version. Independent Windows
review found that version 0's colon-bearing receipt filenames were renamed
during extraction while their active references retained colons. Version 1 uses
`driving/<unit-code>.json` filenames and consistent active references in
`driving-reviewed.json`. Public source IDs retain their original colons.

The original acquisition index remains byte-identical in `driving-original.json`.
The importer verifies that the active index changes only `response_path` to the
deterministic portable name; coordinates, dates, response hashes and other facts
must match exactly. Row provenance continues to cite the original index SHA,
`449dfc2b5bdb4075dcece4341c1fd8109dc4d3970041d9701df052cc29992fb7`,
and each unchanged raw response SHA. All 243 normalized rows, including their
provenance, remain byte-for-byte identical to version 0. Historical acquisition
logs describe original paths; active receipt lookup uses the portable index.

For complete re-admission, first reproduce the frozen portable 214 package and
add `--baseline-bundle <portable214-result>/reviewed-214.json`. This flattens its
14 original children plus the two new ones; nested mixed bundles are refused.
The resulting complete recipe re-admits **243**, zero duplicates, under explicit
500-row / **40 MiB** bounds. Version 0 measured **36,735,196 bytes** at its original
paths and **36,742,752** after relocation. Version 1 measures **36,790,192 bytes**
in the tested Windows-style extraction/replay, including the retained original
index as well as the active index.
Serialized recipe sizes and generation fingerprints legitimately depend on
paths; all 243 row contents/provenance remain identical. All 75 archived snapshot
hashes were independently rechecked after extraction.

Actual Linux replay with spaces in the paths passes while network and database
connections raise on use. Windows filename preflight detects 31 renamed paths
in version 0 and none in version 1. Extraction using the Windows filename
transformation preserves every version-1 path; all active references resolve
to exact archive members, and all 31 raw response hashes remain unchanged.
Windows instructions use `-X utf8` and ordinary ZIP extraction, but actual Windows
execution and independent review clearance remain pending. Evidence older than
30 days requires genuine new acquisition/review, not edited dates or hashes.

Focused validation passes **254 catalog tests**, including the new profile's
parking/state/closure/point failures, changed raw receipts, exact byte budget,
strict classifications, source/review tampering, atomic publication and prior
adapter behavior, Windows-safe filenames, path-only index derivation and original
provenance preservation. Ruff format/check and diff checks pass. Full application
workflows run automatically in the separate PR; they are not repeated locally.
The complete recipe is a reviewable file deliverable, not activation authority.
