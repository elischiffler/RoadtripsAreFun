# Second regional review checkpoint — October 21, 2026

The prepared **60 prospects across 20 states** received final dispositions:
**27 source-admitted T2 browse-only places, 33 holds, and zero T3 itinerary-ready
additions**. The browse-review program advances **194→221**; the diagnostic local
comparison advances **890→917** (603 earlier rows, 93 earlier USFS additions,
221 browse admissions). These are cloud development artifacts, not production
database additions or live net-new counts. The 5,000 target remains unfinished.

| Review group | Reviewed | Final source recommendations | Root admissions | Held | T3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Museums and heritage properties | 24 | 11 | 10 | 14 | 0 |
| Gardens, science/animal facilities, observatories and caves | 20 | 8 | 8 | 12 | 0 |
| Roadside landmarks, lighthouses and heritage railways | 16 | 9 | 9 | 7 | 0 |
| Total | 60 | 28 | 27 | 33 | 0 |

The measured final admission yield is **45% for this selected queue**, not an
unbiased estimate of future sources. Four preliminary positive recommendations
were withdrawn by the acquisition-policy audit. The unchanged 250 m guard held
Voodoo Museum against 1850 House at 73.8 m. This is an unresolved co-location/point
review, not a claim that these distinct institutions are duplicates. No source
coordinate was moved to evade the guard.

## Useful additions and coverage

Admissions cover **13 states**: LA 7, MI 3, NC 3, RI 3, SC 3, and one each in
AL, AR, KS, MS, ND, TN, WI and WV. Categories are seven gardens, six historic
sites, five museums, three roadside destinations, three lighthouses, two heritage
railways and one science center. Broad native query membership was reviewed:
Greensboro is a science center rather than three aquarium/zoo/museum additions;
the Belle Isle parent park remains held while its conservatory is admitted.

Examples include Marble House, Rosecliff, The Breakers, 1850 House, Alexandria
Museum of Art, Louisiana History Museum, New Orleans Museum of Art, Belle Isle
Conservatory, Dow Gardens, North Carolina Arboretum, Cypress Gardens, Magnolia
Plantation gardens, Moore Farms Botanical Garden, Cheekwood, Mission Point Light,
Currituck Beach Lighthouse, mainland Round Island Lighthouse, Salem Sue, the
Anniston office-chair landmark, Dalton Gang Hideout, Chester teapot, Eureka Springs
railway and Osceola railway. A retained proper name or superlative is a publisher
label, not independent validation of dimensions or historic claims.

The existing **16 frozen OSRM road captures** were reused offline for the same
continuous five-mile feature buffer. Houston–New Orleans coverage improves **2→6**;
Atlanta–Asheville **4→5**. Other corridor counts remain unchanged, including zero
on Denver–Salt Lake, Nashville–Knoxville, Minneapolis–Duluth, Rapid City–Billings,
Medford–Bend and Salt Lake–Boise. These are feature-proximity diagnostics, not
routable places or verified trip feasibility. All route hashes, state/category
counts and before/after values are in [coverage.json](data/catalog-regional2-20261021/coverage.json).

## Acquisition audit and the correction

The reviews made **145 bounded operator GET attempts**: 55 museum, 49 nature,
41 niche. Retained originals, failures, redirects, policies and exact timestamps
remain in the private working directories. Original native Wikidata snapshots and
rights receipts were reused; no new broad dataset crawl occurred.

The final timing audit found **eight request intervals below declared delays** in
two reused fetchers. This was a real implementation error, not a successful
rate-compliance check:

- Gloucester County: two intervals below 10 seconds; Whitall House was already
  held for seasonal conflict.
- Audubon: first content 1.53 seconds after robots despite 30 seconds; its positive
  recommendation was withdrawn.
- Blue Spring: 1.97 seconds versus 60; For-Mar: 1.12 versus 10; their positive
  recommendations were withdrawn.
- Lincoln Park school: 1.76 seconds versus 5; already held after HTTP 403.
- Greensboro: initial failed page 1.01 seconds versus 10. Its later successful
  visitor page is separately supported by a 46.19-second interval with no intervening
  same-host request, exceeding the 35-second maximum request timeout plus 10 seconds.
  The failed page is excluded from positive proof; the initial mistake remains recorded.
- Life/Science: initial failed page 2.05 seconds versus 10. Its later interval
  cannot conservatively prove completion-to-next-request timing, so it is held.

No acquisition continued to remedy these misses. Both fetchers were corrected
offline to honor applicable pacing for first content after robots, redirects and
cached receipts. Nature now records completion timestamps; its scheduler
conservatively includes otherwise ambiguous delay declarations. Offline clock tests
passed. The niche audit found no applicable start-interval misses; its two
nonzero policies were 10 and 50 seconds, with observed gaps 10.76 and 108.16 seconds.
Missing completion timestamps limit retrospective certification; the exact audits
state that limitation.

The [source-review audit](data/catalog-regional2-20261021/source-review/) and
[corrected fetcher code](data/catalog-regional2-20261021/source-review-code/) make
the error, exclusions and correction reviewable. Those code copies preserve the
reviewed implementation; run originals from the private working directory with
their raw receipts, not from the documentation tree. No remedial request or new
operator contact was made. Future permitted research must use the corrected policy;
an actual denial still requires the existing materially-new-evidence rule.
This audit covers the new acquisition only. The defect was found in reused
fetcher patterns, so earlier batches need a retrospective timing-policy audit
before a combined release. Their 194 staged admissions were preserved, not newly
certified by this checkpoint. That audit can use existing receipts without making
new source requests and should precede the next acquisition batch.

## Rights, factual checks and profiles

All 27 new rows derive native identity, names and feature coordinates from the
retained [Wikidata structured-data CC0 grant](https://www.wikidata.org/wiki/Wikidata:Copyright).
Operator visitor-purpose/location facts were reviewed separately. Exact source
IDs, same-entity native field pointers, original response hashes, dated proofs,
reviewer, constraints and limitations are retained. Reproduction restrictions on
collection images, archival material, galleries and service content were examined;
no photos, article descriptions, testimonials or collection text enter profiles.
JAMNOLA remains held for unresolved restrictive terms. No agreement was accepted.

There are **zero new noncommercial-only admissions**. The prior separable NC
research partition and its future-monetization flags remain unchanged and hash-pinned
in this checkpoint. Earning no revenue does not resolve scope, redistribution,
adaptation, license-version or intended-use questions. No quarantine label grants
browse or itinerary access.

Every new place has the existing **14-attribute deterministic profile**. For example:

| Place | Evidence-supported scope | Inferred character/fit | Explicit unknowns |
| --- | --- | --- | --- |
| Marble House | Distinct property and public house tours on its operator page | Public heritage visit; history 0.8 | Arrival, maintained calendar, current cost and accessibility |
| Salem Sue | Lions Club landmark and explicit invitation to stop | Roadside visit; unique-local-experiences 0.7 | Road grade, safe vehicle arrival, parking, hours and amenities |
| Currituck Lighthouse | Conservator identifies Corolla site and a dated visitor season | Lighthouse visit; scenery 0.8 | Surveyed arrival, complete exceptional-date calendar and future availability |

Other attributes retain explicit 0.5 unknown priors. Fit confidence is labeled
"limited category inference"; activities remain empty when unsupported. The
description identifies review-classified destination type and state rather than
inventing a richer operator narrative. Current notices, component closures,
advance-tour requirements, member-only hours and holiday exceptions remain dated
source constraints, not invented normalized hours/cost/amenity values. Fresh
acquisition does not prove that all publisher content is freshly maintained.

Validation checks finite native coordinates and Census state containment,
primary operator identity/location/public-visit evidence, rights contracts,
closure conflicts, aliases, names, 250 m proximity and parent/component scope.
Schema, hashes and state containment do not establish publisher truth, surveyed
precision, safe public vehicle entry or availability at a future visit. The same
30-day admission expiry remains; old approvals were not renewed.

## Two arrival/calendar qualification holds

Two previously admitted lighthouses were reviewed separately, without adding them
again or changing their T2 status:

- [Fort Gratiot](https://www.phmuseum.org/fort-gratiot-lighthouse/): the operator
  puts December 20 in both its open and closed periods. The county's official
  schematic PDF has no parking/entrance coordinates or georeferencing. Its "Map
  This Park" link leads to a county GIS page, not the lighthouse arrival. Adjacent
  Coast Guard access is unresolved. No exact point or precision was asserted.
- [Tybee](https://www.tybeelighthouse.org/visitor-general-info): the general visitor
  page and retained homepage disagree on holiday exceptions. The page supports
  US80→N Campbell→Van Horne→Meddin and ticket-holder two-hour parking, but not an
  exact public vehicle arrival point. An address query was not converted into an
  arrival. Linked brochures exceeding the task's 1 MiB probe ceiling were skipped
  after size checks; this is a local acquisition limit, not an access denial or a
  request for user approval.

Seven GETs and three HEAD size checks retained 3,374,704 new body bytes; eleven
new/reused body hashes and selected HTML fragments passed offline replay. Exact
arrival coordinates, precision and point observation dates remain null. Neither
calendar was admitted. Details are in the [qualification report](data/catalog-regional2-20261021/source-review/arrival-qualification/qualification-report.json).

## Implementation, replay and database proof

`catalog_pilot.py assemble` now accepts repeatable `--comparison` arguments and
an optional prepared `--queue`. It replays each comparison, requires equality with
its frozen admitted rows, rejects repeated artifacts/identities and records source
manifest hashes and counts. Expired or changed comparison admissions fail assembly
instead of silently shrinking duplicate coverage. Queue IDs, denominator and
original native snapshot hashes must match. Source-family, same-entity and rights
checks still run; a queue pin is not independent factual validation.
The combined assembler checks 53 retained native bindings; seven minimal niche
hold records have no positive bindings and cannot be admitted. Their discovery
native facts were separately replayed in the niche review audit.

The new 60-place artifact is standalone. It independently replays the prior 191-row
main and 3-row Baltimore artifacts against the 696-row earlier baseline, preserving
all 890 comparison rows. Earlier source artifacts and approvals remain untouched.
The 64 MiB source, 100 MiB aggregate and 50,000 accounting-row ceilings were retained.
No source budget was enlarged. Approximately 24 GiB remained before packaging.

The source replay consumes **26,160,547 bytes** and **1,554 accounting units**:
60 prospects, 890 comparison rows, 548 native scan rows and 56 Census features.
These units are not additional attractions. Four output files replay byte-identically
with sockets and external DNS blocked.

The disposable loopback PostgreSQL proof stages twice, preserves the active pointer,
activates, retrieves all **27** records through the actual browse repository,
checks routing/calendar exclusion, and rolls back to one unchanged synthetic parent.
The candidate's 28 rows remain available for recovery inspection. It is not a
917-row production-parent rehearsal. Proof generation:
`017fa936120f56b646a6d476163590e1b0553951cd05b7ea9d5638d1c01c713a`.
The typed build consumes 26,360,117 bytes; retained evidence is 26,187,870 bytes in
52 files. Database size is 8,320,703 bytes, with 57,344 bytes of place indexes.
Fixed baseline/Census overhead makes this unsuitable as a per-attraction cost model.

Final checks: **2,124 backend tests passed, 138 optional skips, 80.73% coverage**
against unchanged 63% minimum; **71 PostgreSQL tests passed** across the four
catalog suites plus eight automation integration checks; focused assembly tests
passed; Ruff format/check and whitespace checks passed. All automated checks block
external sockets/AI; PostgreSQL tests permit only the explicit disposable loopback
fixture. No frontend files changed, so the previous checkpoint's 278-test,
format/lint/build result is retained rather than reported as a new run. Full app
container smoke, live provider trips and production recovery were not run.

## Reproduce and continue

Private evidence and runnable acquisition/review code remain under
`/workspace/catalog-regional2-20261021/`. The versioned audit contains all 27 rows,
profiles, 60 decisions, receipts, policy corrections, proof and checksums. No public
download URL was created or verified.

```sh
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot.py assemble \
  --input /workspace/catalog-regional2-20261021/museums/adapter-inputs.json \
  --input /workspace/catalog-regional2-20261021/nature/adapter-inputs.json \
  --input /workspace/catalog-regional2-20261021/niche/adapter-inputs.json \
  --states /workspace/catalog-geodiverse-20261021/assembled-main/states.json \
  --comparison /workspace/catalog-geodiverse-20261021/assembled-main \
  --comparison /workspace/catalog-geodiverse-20261021/assembled-baltimore-final \
  --queue docs/data/catalog-regional2-20261021/prepared-queue.json \
  --expected-prospects 60 --release catalog-regional2-20261021 \
  --output /workspace/NEW-regional2-replay
```

The [next queue](data/catalog-regional2-20261021/next-queue.json) has **32 genuinely
unreviewed museum-query prospects across nine states**, at most four per state.
Seven other prospects were filtered for immediate local identity/name/250 m
conflicts. Primary purpose, scope, rights and all other gates remain unreviewed;
selection does not grant access or admission. Compare the next standalone artifact
against all 917 local rows and carry forward blocked/closed/timing-quarantine ledgers.

An additional [27 varied heritage discovery leads](data/catalog-regional2-20261021/next-heritage-leads.json)
cover windmill manufacturing, dredges, rail works, a historic naval ship, carousels,
an offshore rig, public waterworks and historic properties. These retained NPS
features remain T1. They require explicit `culture:nris` prepared-queue/native
binding support before that supplemental intake can be assembled, plus operator,
public/private access, relocation and duplicate review. No current visit is inferred
from landmark designation. This diversification can proceed in cloud without a new
production connection or user decision; it should accompany rather than merely
exhaust the remaining museum pool. Geographic intake still needs the western and
northern corridor gaps above.

Release remains blocked by the unavailable authorized complete live-parent
catalog/calendar snapshot and generation/hash reconciliation. The earlier hosted
network-unreachable failure was not retried, and desktop fallback remains unapproved.
The final 5,000 counting decision (browse-only versus itinerary-ready) is unresolved.
Neither blocker prevents the next independent permitted development batch. No
production write, push, deployment, paid API, live Mentro call, new account,
credential/access change or desktop execution occurred.
