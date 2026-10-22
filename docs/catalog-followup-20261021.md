# Follow-up checkpoint: 20 arrival reviews and 50 museum prospects

Both prepared queues are complete in the cloud. **24 additional T2 browse-only
places** passed the combined source/dedup replay; **26 of the 50 museum prospects
remain held**. The original 129 normalized place rows are preserved byte-for-byte. The full
600-prospect pilot now contains **153 T2 records, 447 holds and 0 T3 records**.
There are no new calendar companions and no admitted arrival-coordinate updates.
Live net additions remain unknown; no production data changed.

## The two requested visitor points

### Air Mobility Command Museum

The [operator visit page](https://amcmuseum.org/visit/) and
[FAQ](https://amcmuseum.org/faq/) establish a separate museum entrance from
Route 9/Kitts Hummock Road, via exit 91 from US 113/DE 1. Visitors must not approach
through Dover Air Force Base. The existing **39.118692,-75.456643** remains a
venue feature point, not verified visitor parking, a gate or a legal vehicle
arrival. No operator-published exact arrival coordinate was found in this bounded
review.

We also inspected the public DelDOT/FirstMap
[centerline layer](https://enterprise.firstmaptest.delaware.gov/arcgis/rest/services/Transportation/DE_Roadways_Main/MapServer/1).
A bounded query returns23 complete surrounding-road features, including Bayside
Drive and multiple roads classified as72-AirForce. Those fields do not distinguish
the public museum drive/gate from military roads or identify the security fence.
No nearest road, base road endpoint or routing snap was accepted as the arrival.
**Actual public gate/parking coordinates remain unknown; the routing hold remains.**
The remaining evidence is an authoritative public gate/parking point or mapped
feature unambiguously tied to the museum's separate public approach, plus its
legal onward vehicle/walking connection. No operator was contacted.

### North Carolina Botanical Garden

The [current visitor information](https://ncbg.unc.edu/visit/visitor-information/),
[storm notice](https://ncbg.unc.edu/2025/07/08/storm-recovery-updates/) and
[official 2025 map](https://ncbg.unc.edu/wp-content/uploads/sites/963/2025/04/NCBG-Master-Map-2025_web.pdf)
establish front visitor parking from **Old Mason Farm Road** and a **17:00 gate
lock**. Laurel Hill is the back/service entrance and remains closed to visitor
vehicles. The older venue/event page still suggests Laurel Hill parking; that
conflict is preserved, with current visitor/closure information taking priority.
The map identifies accessible spaces, drop-off and after-hours parking outside
the gate, but has no coordinate grid or geospatial registration.

Independent source geometry provides stronger front-lot candidates:

| Role | Latitude,longitude | Source and interpretation |
| --- | --- | --- |
| Front street/driveway junction candidate | **35.90119,-79.03189** | Chapel Hill street features 9286/9909 and parking-driveway 8202 share an exact original endpoint. |
| Junction inside the named visitor parking polygon | **35.90086,-79.03227** | Other end of 8202 joins internal parking roads and lies inside UNC BOTANICAL GARDEN lot P256, feature 3864. |
| Existing catalog feature |35.8994,-79.0339| Retained unchanged; not arrival-qualified. |
| Operator venue GeoCoordinates |35.901081,-79.031939| Venue-level metadata, not a parking/entrance declaration. |

The sources are the town/county-maintained
[street layer](https://gis-portal.townofchapelhill.org/server/rest/services/OpenData/Streets/FeatureServer/0)
and the university's
[parking layer](https://gismaps.unc.edu/arcgis/rest/services/UNCOpenData/UNCOpenData/FeatureServer/7).
The restricted front-road query returned 8 complete features; the parking query
returned 7. A broader 30-row road query was truncated and was not used to infer
completeness. The front-driveway candidate is an original shared endpoint, not a
centroid, address geocode or routing snap. Official operator mapping corroborates
its lot/approach interpretation.

**These coordinates remain research candidates, not admitted arrivals.** The
returned EPSG 4326 decimal precision is retained privately; five decimals above
are display resolution, not measured positional accuracy. Source horizontal
accuracy and current gate position are unknown. UNC lot observation freshness
and reuse/redistribution terms are unresolved; ArcGIS/public hosting is not a
license. No driving leg or complete pedestrian approach was established. The
closed Laurel Hill coordinate is never promoted. The source-point and T2 routing
hold remain unchanged. `catalog_arrival_geometry.py` deterministically replays
these relationships and emits zero admissions, including on successful research.

## Broader queue results

All 20 arrival candidates have a field-level review. Four component-specific,
bounded schedule proposals are supported: New Britain Museum of American Art,
Delaware Art Museum, Myriad outdoor grounds and Birmingham outdoor gardens.
Sixteen retain explicit schedule gaps. Connecticut Science Center links a specific
public Science Center Garage point, distinct from its Convention Center Garage;
that is one operator-backed coordinate lead, not an end-to-end qualified arrival.
All calendar proposals remain outside the imported companion set. Timezone binding,
component/holiday exceptions, arrival geometry and road/walking verification still
gate promotion. Dwell remains a labeled planning estimate, never a source fact.

The museum queue yielded24/50 additional T2 admissions, a **48% measured queue
yield**, not a forecast for other states or sources. New categories are 18 museums,
4 historic sites and 2 industrial-heritage destinations. Connecticut gains 18
(pilot 7→25); Delaware gains 6(6→12). The reproducible full local diagnostic comparison
is **825→849** records, retaining all 50 states + DC. The documented hosted 608 count
remains unverified. Neither a regional feature point nor a state count establishes
road-corridor usability.

Examples include Yale Peabody, Yale University Art Gallery, Mashantucket Pequot
Museum, American Museum of Tort Law, Housatonic Museum of Art, Nemours, Nanticoke
Indian Museum and Wilmington & Western Railroad. Park/estate grounds were
classified separately from seasonal museum interiors. A train operator's office
hours were not converted into excursion departures. Lewes' limited museum access
during renovation does not imply its children's component is open.

Holds include Yale's instrument collection renovation through spring 2027,
Barnum's planned 2030 reopening, temporary closure of Delaware Military Museum,
the already-admitted Valley Railroad, organizational headquarters, relocated/mobile
operations, seasonal closure, conflicting public-access scope and blocked sources.
New Haven/USJ/Mattatuck and other 403s were stopped; robots 503/oversize responses
also prevented operator fetches. Delaware Art Museum's S3 parking PDF was not
requested after its host's robots 403. No source denial was bypassed.

All 24 new source identities/points come from frozen **Wikidata CC0** snapshots,
with separately dated primary-operator identity/location/public-purpose reviews.
The original rights notice hashes and native fields remain pinned. No article
prose, photos or operator marketing descriptions were redistributed. Deterministic
14-attribute profiles distinguish category-based fit inferences and 0.5 unknown
priors from factual evidence. Hours, cost, amenities, accessibility and arrivals
remain unknown in app profiles. This is Codex-assisted review, not human signoff,
field surveying or proof that every publisher claim is correct.

## Implementation, proof and reproduction

`catalog_pilot_followup.py` merges only the exact prepared 50 museum IDs into a
new immutable 600-prospect artifact. It rejects changed native facts, another
entity's QID, receipt/path/hash/byte failures, duplicate update IDs and T3 grants.
Minimal T1 discovery rows can gain bindings only to their original queued QID.
Untouched approvals are not restamped. The 64 MiB source/100 MiB import guards remain.
Audit export now binds source manifests, normalized additions, portable proof rows,
query counts and recovery generation so an older unrelated proof cannot be reused.
Persona preview release attribution follows the actual adapter release.

A fresh loopback-only PostgreSQL fixture on 55434 preserved the earlier stopped
fixture on 55433. Explicit libpq hostaddr and cleared PG environment prevent ambient
connection overrides. Typed ingestion staged twice, activated and queried all 153
browse records, confirmed no routing/calendar eligibility, and rolled back while
preserving the synthetic parent. Its 154 rows include one synthetic parent;
they are not a production replacement artifact. Consumed bytes 44,874,633; retained
evidence 44,106,512 bytes across 193 files; database 9,131,711 bytes; places including
indexes/TOAST 1,097,728 bytes, indexes 122,880 bytes. No hosted quota/cost conclusion
is inferred from those fixture measurements.

```sh
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot_followup.py \
  --base /workspace/catalog-pilot-600-20261021/assembled-final \
  --update /workspace/catalog-followup-20261021/museums-a/updates.json \
  --update /workspace/catalog-followup-20261021/museums-b/updates.json \
  --queue docs/data/catalog-pilot-600-20261021/next-batches.json \
  --output /workspace/NEW-followup
/workspace/roadtrips-venv/bin/python scripts/catalog_arrival_geometry.py \
  --research-dir /workspace/catalog-followup-20261021/geospatial \
  --output /workspace/NEW-arrival-research.json
```

Original bodies, request ledgers, review scripts and private proof excerpts remain
under `/workspace/catalog-followup-20261021/`. The checked-in
[audit](data/catalog-followup-20261021/) contains the 24 new additions, full 153
profiles/600 decisions, before/after metrics, arrival reviews, geometry research,
receipt metadata and recovery proof. Literal operator excerpts are omitted from
the public arrival audit; their hashes and original private bodies are retained.
Workspace paths are not public download URLs; no shareable URL was created.

Release still requires the complete authorized cloud-readable live-parent snapshot
and calendar companions, final duplicate reconciliation, and generation/digest
recheck. The earlier snapshot failed with network unreachable; it was not retried
via the unapproved desktop. Whether the final 5,000 target may count browse-only
records remains undecided. No production writes, push/deploy, paid APIs, live
Mentro calls, new accounts/access or operator contact occurred.

Validation: **2,104 backend tests passed, 138 optional skips, 80.72% coverage**;
**72 focused admission/source/merge/geometry tests passed**, plus 24 private arrival
audit checks. Backend and changed-script Ruff format/check and Git whitespace
checks passed. An optional sweep of all legacy catalog scripts found 28 existing
lint issues outside changed files; those files were preserved. Frontend code did
not change in this follow-up; 278 frontend tests/build/lint/format and 71 additional
PostgreSQL regressions passed at the prior checkpoint, not rerun here.
