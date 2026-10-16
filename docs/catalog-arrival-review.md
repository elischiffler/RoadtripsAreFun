# Current publisher arrival review — October 15, 2026

The [82-place release candidate](catalog-release-82.md) supersedes current
eligibility counts below: six NPS dated-closure exceptions were addressed and
12 verified heritage arrivals added. Earlier 72-place generations remain preserved.

The [rollout-candidate receipt](evidence/catalog-rollout-candidate-20261015.json)
records a subsequent 72-place generation with the same original rows/coordinates
and deduplicated attribution statements. Its generation is
`2c09cc2993640b966c6f73231c031aafbf765695ef748f2017067a1c88bf4e3f`;
the prior 72-place generation below remains preserved and independently restored.
CodeRabbit's completed review found this attribution issue; producer and response
formatting now preserve first-seen credit/license statements without repetition.
Full backend validation passes 940 tests at 87.58% coverage. The exact-head
follow-up review and release gates are tracked separately on PR #40.

The separate reviewed local catalog now contains **72 unique arrivals across
24 states**: one roadside, one entertainment, 12 nature, 12 beaches, nine museums
and 37 national parks. It remains **428 short** of the roughly 500 target, with
substantial category/geographic/corridor gaps, no dedicated landmark batch,
no DC record and no food/nightlife coverage. This is not national coverage or
production acceptance. The original 400-record evaluation and the prior
70-arrival generation remain unchanged in their separate databases.

The [aggregate receipt](evidence/catalog-arrival-review-v2-20261015.json) records
publisher URLs, acquisition dates/hashes, driving-destination checks, source and
category counts, exact database recovery and actual discovery-adapter results.
The [first roadside increment](catalog-roadside-review.md) retains Corn Palace
and LOC rights details and its earlier 70-arrival proof.

## Two independently reviewed Overture arrivals

| Destination | Native ID | Evidence and point role | Limitations |
| --- | --- | --- | --- |
| Wing Luke Museum, Seattle WA | `03f811cd-0401-40ad-b75c-1ae7328cf6b7` | Current [visitor page](https://www.wingluke.org/visit) matches 719 South King Street and publishes car directions. The unchanged licensed venue point is 11.178 metres from the checked driving destination on South King Street. | No on-site parking; paid lots/street parking require a walk. Weekly and holiday hours need checking before travel. |
| Waikīkī Aquarium, Honolulu HI | `57193dd5-6aa9-4857-98bc-60e2097c3af0` | Official [directions/parking](https://www.waikikiaquarium.org/visit/directions-parking/) matches 2777 Kalakaua Avenue and describes limited visitor parking at the entrance. A driving-destination check is 4.2 metres from the unchanged licensed point beside that frontage. | The checked link is unnamed; it is not labeled Kalakaua Avenue. Entrance parking is limited/visitor-only, nearby street parking metered. The aquarium reports remaining open during renovations and publishes [special hours/closures](https://www.waikikiaquarium.org/visit/hours/). Future access/parking availability is unknown. |

The original licensed points/categories/native IDs pass the existing normalizer
and upstream-rights checks. An optional `arrival_review` manifest section then
revalidates explicit `wing-luke/1` and `waikiki-aquarium/1` profiles. It requires
exact identity coverage, matching venue/address/publisher, retained recent
publisher pages, positive access/parking facts and a matching successful
**destination** waypoint check. Wrong/missing/stale evidence, a current closure,
an origin-only driving check or a different venue/point prevents admission.
The aquarium's unnamed link is accepted only by its inspected entrance-parking
profile and stricter 10-metre bound. An unnamed road alone proves no access.

No arbitrary place payload, guessed coordinates, road snaps, source recategorizing
or creative website prose enter the catalog. The added provenance retains current
publisher URLs/hashes/dates, review profile, point role, driving evidence and
limitations separately from the original upstream/source evidence date. Opening
hours are not imported or invented. These explicit profiles do not clear other
records from the 331-point Overture evaluation pool; **329 remain outside** the
usable bundle, including the explicitly withheld Museum of Illusions closure.

`scripts/catalog_combine.py --selected-ids <ids.json> --arrival-review <review.json>`
uses the original bounded Overture files and existing `.manifest.json` sidecars.
It rechecks the complete selected review before publishing the output pair and
refuses to strip an input's existing review silently. `scripts/catalog_mix.py`
re-admits that child with the other original source artifacts as one complete
replacement generation. Neither command performs downloads or database calls.

## Source access and quality findings

One ordinary retry of 20 exact URLs that previously returned 503 now yielded
19 HTTP 200 responses and one read timeout. Eighteen HTML files totaling
3,684,063 bytes were retained; one response exceeded the explicit 2 MiB/page
ceiling and was not retained. Ten publisher-linked visitor/parking/schedule
follow-ups all returned 200 and were retained. A separate one-URL K1 homepage
recheck also returned 200, establishing restored source access rather than a
venue-specific arrival. Actual 403 denials were not retried or bypassed.

An HTTP 200 page alone remains insufficient. Empty/script-only pages, a blog
replacing an operator site, unrelated city addresses, mall entrances and park
centroids are not promoted. Kubota Garden reports parking/construction impacts;
Chihuly publishes specific partial closures; Downtown Aquarium distinguishes a
closed sub-exhibit from the venue's public operating information. These remain
review findings, not additional admitted places. The temporarily closed Museum
of Illusions is withheld despite the older source open flag. Broad source
access now works; current eligibility work remains necessary.

## Authentic local database and restore

Final generation:
`3d9d99878577fa635fb46390051e64d40d6b1810a9446cd1ef4f5d3125c0e384`.
Manifest SHA-256:
`144290357712730e9601a71929f75e12b9594140cd545a8f9a48bc2bf107d737`.
The 70-arrival baseline and 72-arrival generation total 142 stored rows and
475,136 indexed catalog bytes in isolated PostgreSQL 18.6. Idempotent staging,
activation, rollback (the two new arrivals disappear) and return to the final
generation passed. The observed database size was 8,468,159 bytes, not a
production growth forecast.

The custom dump is 34,346 bytes, SHA-256
`992b1c022992c471878c35e097eed581d9e20d364acd61972d4e703874d236fe`.
An empty separate database restored all three tables with exact row-content
digests and the active pointer. The prior 70-arrival database's table digests
also match its preserved proof. The original 400-record database is unchanged.

Actual legacy/persona discovery returns the imported aquarium ID; optional
culture discovery returns the imported museum ID, each with retained provenance
and the active generation. HTTP request/send transports raise on use: zero
discovery HTTP calls and zero Tripadvisor calls. Routing and geocoding are
separate services. These are authentic local adapter evaluations, not a live
production website journey.

Backend validation passed 938 tests including five real PostgreSQL cases, with
87.57% application coverage above the unchanged 63% floor. Sixteen synthetic
arrival-review cases cover evidence/identity/parking/closure/destination failures,
provenance preservation and refusal to strip reviews. The closure test caught
adjacent HTML text nodes hiding a word boundary; text extraction now separates
nodes before checking, and authentic inputs were revalidated. The frontend tree
is unchanged from the prior 314-test format/lint/build pass. Exact-head CI and
code review are tracked on PR #40; CodeRabbit re-review remains rate limited.

Production has no catalog writes, activation or deployment. Current authorized
host backup/freshness/isolated-restore evidence, review, exact-main checks and
the established release path remain gates. Completion still requires the real
deployed version and live saved-trip/Studio, routing, attribution and saved-history
flows using database catalog IDs with zero Tripadvisor discovery calls.
