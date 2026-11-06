# Catalog pilot: measured checkpoint, October 21, 2026

The cloud-local pilot assembled **600 prospects**, admitted **129 source-reviewed
T2 browse-only destinations**, and held **471 T1 prospects**. **Zero are T3
itinerary-ready**. No production catalog was changed. The 5,000 target remains
unfulfilled, and live net additions remain **unknown** until reconciliation with
the active catalog. Many held prospects have not received current operator review;
600 prospects does not mean 600 fully reviewed places.

This implements the first development milestone of
[the committed program](catalog-5000-plan-20261021.md), preserving the prior
93-place USFS implementation. The reproducible local comparison is **696 → 825**
records, not the unverified hosted count of 608. New records cover **49 states**;
Connecticut improves **0 → 7**, Delaware **0 → 6**. The combined diagnostic set
now represents all 50 states and DC. It adds no trailheads. Corridor coverage
remains a research-level regional comparison: native destination points do not
establish legal arrivals, detours or usable road access.

## Measured results and source rights

| Cohort | Prospects | Proposed T2 before combined replay | Final T2 contribution |
| --- | ---: | ---: | ---: |
| Museum/science and provisional heritage groups | 300 | 13 | 13 |
| Garden/zoo/observatory/cave, civic art clusters, niche | 170 | 15 | 15 |
| Nature/public facilities and food/farm stops | 130 | 106 | 101 |
| Total | 600 | 134 | 129 |

| Accepted family | Count | Native source and retained rights evidence |
| --- | ---: | --- |
| Wikidata | 27 | Bounded [SPARQL](https://query.wikidata.org/) exact entity/coordinate fields; [structured data CC0](https://www.wikidata.org/wiki/Wikidata:Copyright). No Wikipedia article prose or images. |
| US Fish and Wildlife Service | 80 | Public agency facility points; exact public-view ArcGIS paths and agency item pinned in `pilot.py`. [DOI factual-data copyright policy](https://www.doi.gov/copyright), agency ownership/status/public-use fields, separate FWS policy and metadata review. ArcGIS hosting alone does not grant rights. |
| BLM | 8 | [Agency recreation layers](https://gis.blm.gov/natl/rest/services/recreation/BLM_Natl_Recs_pts/FeatureServer); [BLM notices](https://www.blm.gov/info/notices/drctp-policy) and DOI policy retained. Agency facts only; third-party materials excluded. |
| New York farm markets | 13 | [Official market dataset](https://data.ny.gov/resource/qq4h-8p86.json); exact [Open NY terms PDF](https://data.ny.gov/api/views/77gx-ii52/files/ef0c1840-ad54-4240-92fd-6397c49fde46?download=true&filename=OPEN-NY_20Terms_20of_20Use.pdf) retained and pinned. Attribute the state source, preserve limitations, avoid endorsement. Each public physical visit separately reviewed. |
| NPS historic landmarks | 1 | [NRHP/landmark service](https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer); [NPS disclaimer](https://www.nps.gov/aboutus/disclaimer.htm), federal agency facts with third-party exceptions. District/group references are not automatically independent attractions. |

Raw operator HTML is private evidence, not redistributed description content.
The shipped normalized descriptions are new factual summaries; no photos or
operator marketing descriptions are included. Source-specific attribution, URLs,
receipt hashes, review times and limitations accompany every accepted record.
Commercial reuse is scoped to the reviewed structured facts and each applicable
notice, not a blanket permission for every asset hosted by these services. The
frontend attribution page carries these credits. Changed notice bodies require a
new rights review; caller-supplied license labels cannot bypass pinned evidence.

Kaggle/Hugging Face did not supply new accepted pilot rows. Earlier research found
useful CC0 discovery leads but mixed rights, large snapshots and duplicate/source
staleness risks. Existing Kaggle Boulder rows remain in the baseline. OSM/Overture
and linked HF packages remain outside this pilot until their collection,
attribution and redistribution policy is settled. Reddit/niche directories served
discovery only; no Reddit prose or unsupported recommendation became a factual
record. See the research plan and its source ledgers for those source decisions.

Final category counts are wildlife viewing 74, visitor centers 14, food experiences
13, museums 11, botanical gardens 7, observatories 2, show caves 2, zoos 2, and one
each historic site, industrial heritage, roadside attraction and science center.
These categories are explicitly review-classified, not necessarily publisher
taxonomy. The sample is FWS-heavy: **129/600 = 21.5%** is this stratified pilot's
measured admission fraction, not a national acceptance forecast.

## Admission, evidence and routing behavior

`backend/app/catalog/pilot.py` replays original native field pointers, IDs and
coordinates from retained source bytes. It enforces per-family native paths,
same-entity field anchors, original hashes, source/right notice identity, finite
coordinates, Census state containment, required fields and dated affirmative
operator identity/public-visit evidence. Operator evidence must belong to the
reviewed primary operator host. Source IDs, aliases, normalized same-state names
and 250 m collisions are compared across the 696 local records and this batch.
Five later documented identifiers are additionally excluded. Ambiguous entity
scope, conflicting coordinates or close independent destinations stay held.

The source review is **Codex-assisted**, not independent human approval, a field
survey or proof that a publisher is correct. Byte replay proves which retained
fields were used, not all real-world facts. Native points are destination feature
points; they are not certified parking, entrances or routable arrival coordinates.
Current visitor purpose is not a guarantee of opening at a future visit time.

`admission.py` defines an explicit, strict T2/T3 marker with per-field gates,
review status, timestamp and expiry (maximum 31 days). T2 requires rights,
identity, location, public-access and local duplicate review. T3 additionally
requires arrival and calendar gates **and a valid real calendar companion**.
Neither tier establishes absence from the live parent. T1 is not exposed.
The new namespace cannot regain eligibility by stripping its admission marker.

Repository routing filters run in PostgreSQL **before LIMIT**, and source/provider
filters run before scoring/quotas. An explicit `browse_nearby` path admits current
T2/T3; T2 cannot enter daytime planning, calendar refresh, offline evaluation or
evening suggestions. Evening pilot use is withheld pending date-specific support.
Malformed, future or expired markers fail closed. Legacy unmarked catalog behavior
is preserved. Live revalidation never silently renews a stale marker.

Important holds include four FWS building-name bindings and one FWS gate lacking
the original ownership/public-use contract; a 103 km administrative-HQ mismatch;
an unrelated therapy website replacing a farm domain; wholesale-only and
pickup-only businesses; conflicting 2026 farmstand status; seasonal closures;
Eastern Neck's October 21–22 closure; Cannonville closed indefinitely; an ambiguous
NRIS district/library entity; and Stowe's independent co-location and inconsistent
published time. A 216 km obsolete Alaska office point was replaced only where
original current facility evidence supported the Homer feature. SF art clusters
remain discovery leads, including a conflicting accession location. Restricted
retention terms, invalid UTF-8 evidence, 403s and timeouts were held; access denials
were not bypassed or retried through alternate infrastructure.

## Profiles

All 129 have deterministic profiles in the existing **14-attribute** schema,
without paid or live AI calls. Character, interests and traveler fit are labeled
category-based inferences. Unknown ratings use an explicitly labeled 0.5 prior,
not an affirmative suitability score. Activities are empty unless separately
supported; this pilot does not turn category labels into a verified activity list.
Hours, admission costs, accessibility, amenities, arrival and duration remain
unknown. Visitor-center fit is neutral rather than assuming an outdoor experience.

For example, Mark Twain House has retained Wikidata identity/location and the
operator's physical guided-tour purpose. Its character is “Museum visit” and
culture/arts fit 0.8 is an inference; other unknown attributes remain 0.5. The
description explicitly requires separate arrival/timing verification. Air Mobility
Command Museum retains the operator's warning to use the separate Route 9 museum
approach rather than Dover AFB, without certifying a routable entrance. Altamont
Orchards has source-backed physical public farmstand purpose; food interest is an
inference, and opening/seasonal conditions remain constraints rather than invented
calendar entries. Full profiles and constraints are in `personas.json` and each
row's provenance.

## Local proof, budget and reproduction

The typed incremental workflow now permits zero-calendar additions only when every
addition is admitted T2 from the reviewed pilot adapter. Ordinary empty calendar
enrichment remains invalid. The disposable PostgreSQL proof staged twice,
confirmed pointer preservation, activated, queried all **129** through the actual
browse repository, confirmed routing/calendar exclusion, then rolled back to its
one-row synthetic parent. Candidate rows and parent content were preserved.
It is a development proof, never a production replacement bundle.

The portable import consumes **40,857,151 bytes**, retains **40,174,784 bytes in
168 evidence files**, and contains 130 rows including its synthetic parent, zero
calendars and 2,483 scanned source units. Pilot-only replay charges 2,482 units:
1,130 native rows, 600 prospects, 696 local baseline rows and 56 Census features.
These accounting units are not accepted-place counts. Bounds remain 600 prospects,
64 MiB source preparation, and the existing 100 MiB aggregate import guard.
Available workspace disk was 27 GiB at checkpoint. The measured local database is
9,049,791 bytes; places including indexes/TOAST 942,080 bytes, indexes 106,496 bytes.
These fixture measurements do not establish hosted capacity or cost.

Private reproducible originals and source-specific acquisition/review scripts are
preserved at `/workspace/catalog-pilot-600-20261021/{culture,diversity,nature}`.
Acquisition was bounded and source-specific, not an unbounded crawl. The frozen
combined evidence is `assembled-final/`; the successful portable development import
and recovery receipt are `local-proof-complete/`. Operator bodies are deliberately
not checked into Git. A fresh acquisition must be separately reviewed; replaying
an old review stamp cannot authorize changed content or extend its expiry.

```sh
# Use the existing cloud evidence package; choose NEW nonexisting output paths.
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot.py replay \
  --source /workspace/catalog-pilot-600-20261021/assembled-final/reviewed.json \
  --manifest /workspace/catalog-pilot-600-20261021/assembled-final/reviewed.manifest.json \
  --output /workspace/NEW-pilot-replay
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot_audit.py \
  --source /workspace/catalog-pilot-600-20261021/assembled-final \
  --proof /workspace/catalog-pilot-600-20261021/local-proof-complete \
  --output /workspace/NEW-pilot-audit
/workspace/roadtrips-venv/bin/python scripts/run_offline_tests.py \
  --cov=app --cov-report=term-missing --cov-fail-under=63
```

The checked-in [audit directory](data/catalog-pilot-600-20261021/) contains all
additions, 129 profiles, all 600 decisions, original receipt metadata, exact
before/after coverage, local proof/recovery receipts and explicit next work queues.
The evidence archive has no verified public download URL. These workspace paths
are cloud-local artifacts, not user-download links.

Final validation: **2,088 backend tests passed, 138 optional tests skipped,
80.72% coverage**, above the unchanged 63% floor. **71 real disposable PostgreSQL
tests passed**, including malformed/expired/T2 exclusion before SQL limits and
legacy behavior. **278 frontend tests passed** with 92.37% coverage; frontend
format, lint and production build passed (the existing large-chunk warning
remains). Python Ruff format/check and `git diff --check` passed. Source/profile
unit tests include field-anchor tampering, rights and state failures, stale
evidence, byte bounds, idempotency, unknowns, local aliases and the narrow
zero-calendar T2 ingestion rule. No live AI/provider calls were allowed by the
backend test harness or the frontend network guard. Full container/browser smoke
and live-provider trips were not run by this pilot.

## Remaining work and release blockers

The next bounded queues are 20 already admitted varied destinations for verified
arrival/calendar qualification, 50 currently unreviewed museum/science operators,
and the five source-contract holds. No queue entry is pre-approved. Use observed
operator review and T3 yields before sizing the next batch; do not extrapolate
FWS-heavy T2 admission to 5,000 independently routable destinations.

The hosted catalog read-only snapshot remains **blocked by network unreachable**;
the earlier operation failed before producing an export and was not retried via
the unapproved desktop. Release requires complete active generation/import
manifest/row count; every row's source_id, name, latitude, longitude, region,
categories, nullable address/url/source_updated_at and full provenance; all matching
calendar source_id/entry companions; and rows/manifest/calendars/snapshot files
with original hashes, checked_at and database_write=false. See the exact snapshot
contract in the research plan. After deduplication, recheck the same generation
and digests before any release build. Current IDs/counts alone are insufficient.

The user still needs to decide whether the 5,000 target may include clearly labeled
T2 browse-only places or requires 5,000 T3 places. Neither that decision nor a
production release is inferred from permission to start the pilot. No push,
deployment, external write, new account, credential/access change, paid API,
desktop execution or live Mentro request was made. Tests use socket/credential
guards; live provider trips and production recovery are not claimed.
