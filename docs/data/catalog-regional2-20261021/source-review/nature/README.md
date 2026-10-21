# Regional batch 2: nature review

This cloud-local tranche reviews exactly the 20 nature candidates in the checkpoint 190e12c queue. **8 source-reviewed T2 browsing candidates, 12 T1 holds, 0 T3 itinerary-ready.** Nothing was written to a database, pushed or deployed. Root must replay this standalone adapter input and keep the final live-catalog snapshot gate.

## Deliverables and replay

`adapter-inputs.json` is standalone for all 20 records: full unchanged native QID/name/WKT bindings, copied original Wikidata receipts, pinned CC0 notice, new operator proof receipts, and explicit held dispositions. It does not depend on earlier merged evidence IDs. `decisions.json` carries native fact mappings and classification decisions; `persona-fact-basis.json` gives deterministic profile inputs. `attempts.json`, the three probe result files, `skipped-and-held-actions.json` and exact `sources/*.body` retain successful, failed and not-requested actions.

Run `python build.py` then `python validate.py` from this directory. The build is entirely offline and freezes the original review timestamp in `review-contract.json`; reruns do not renew approvals. It reads original local source mappings from `/workspace/catalog-pilot-600-20261021/diversity`. Validation disables network sockets before app imports, checks original hashes/native same-row bindings, literal identity/public access/rights proofs, Census state, and proximity/name conflicts against the pinned 890-row local comparison. Root supplies the shared Census/baseline bundle when assembling the full 60-record release.

`acquire.py`, `followups.py` and `last-probes.py` document the bounded serial public GET recipes. Existing receipt IDs are cached; automatic revalidation is not implied. Public probes used a descriptive user agent, robots requests before content, a 1 MiB response ceiling, 35-second timeout and 0.7-second minimum spacing. This run made 49 direct GET attempts, below 65. The reusable fetcher now enforces a conservative maximum declared crawl delay (including orphan directives), records completion timestamps and inspects robots redirect chains before content. `test_timing.py` tests first-content and redirect spacing offline. Future fresh acquisition must still preserve inherited holds. The initial Chippewa robots response was HTTP202, and McMath robots returned503: the first acquisition script also attempted their public pages; both are held and the script was tightened to stop on such robots responses. This is a recorded acquisition limitation, not accepted proof. No alternate host, script challenge, credential, owner contact or bypass was used after denial.

## Accepted source-review dispositions

| State | Destination | Review scope |
| --- | --- | --- |
| MI | Belle Isle Conservatory | Anna Scripps Whitcomb Conservatory; component only; park alerts retained |
| MI | Dow Gardens | Gardens/Whiting Forest one destination; seasonal schedule and separate parking leads |
| NC | Greensboro Science Center | Corrected zoo to science center for whole aquarium/museum/zoo; construction/parking and seasonal exceptions |
| NC | North Carolina Arboretum | Public garden only; current property/gate/building rules, no full trail reopening inferred |
| SC | Cypress Gardens | Garden visitor purpose; guided boats and splash-pad seasonal closures retained |
| SC | Magnolia Plantation and Gardens | Primary admission/tours and physical address; Thanksgiving/Christmas and add-on experience constraints |
| SC | Moore Farms Botanical Garden | Advance appointment or explicit public events, not ordinary daily opening |
| TN | Cheekwood | Garden scope; sculpture trail closed until further notice; seasonal daytime versus special evening tickets |

## Held dispositions and precise blockers

The post-acquisition timing audit additionally quarantined **Blue Spring Heritage Center**, **For-Mar**, and **Museum of Life and Science**. See `timing-audit.json` for every policy and request-start interval. No fresh requests were made to remedy these misses. Blue Spring requires 60 seconds, For-Mar 10 seconds; their first positive requests started too early. Life and Science has an orphan/global 10-second declaration; the initial 404 was too early and the later positive lacks a response-end timestamp sufficient for conservative proof. Greensboro’s initial 404 also missed its 10-second delay, but its independently acquired corrected positive was 46.194644 seconds later, exceeding the previous 35-second timeout plus 10-second delay; the initial failed body supplies no accepted proof. The school 403 also missed its 5-second delay and was already held.


* **Belle Isle Park:** semantic parent-campus/component counting hold. Native park and conservatory points are **443.93 metres** apart; distance and distinct labels do not resolve duplication. The broad park is not silently relabeled a viewpoint to satisfy profile rules. Conservatory is the only proposed accepted component here.
* **Mystic Caverns and Crystal Dome:** historical closure conflict, current official domain under construction in discovery, and direct robots request failed with URLError. Current primary reopening/access is unverified. Do not describe permanent closure as established solely from secondary sources.
* **Chippewa Nature Center:** HTTP202 tiny non-content responses; identity/public access not corroborated with usable retained operator body. Garden versus nature-center category unresolved.
* **Hector J. Robinson Observatory:** school operator host HTTP403; stopped. Public school/campus presence is not public observatory admission.
* **McMath–Hulbert Observatory:** operator robots/page HTTP503; current public visit/closure status uncorroborated.
* **North Carolina Aquarium at Fort Fisher** and **on Roanoke Island:** inherited ncaquariums.com robots nonretryable denial; no requests, including robots or alternate hostname. Parent must retain host hold.
* **Elisabeth C. Miller Botanical Garden:** original page says all visits reservation-only, 2026 regular season filled and 2027 reservation request period closed. Future class leads do not confirm currently obtainable entry. Precise operator location also not corroborated.
* **Longhorn Cavern State Park:** robots explicitly disallows the requested Texas operator page; no content GET and no concessionaire bypass.

## Rights and release boundaries

Native structured facts use the exact retained Wikidata CC0 notice at `https://www.wikidata.org/wiki/Wikidata:Copyright`, SHA256 `e0744a22fe6ed5e46fa537e41625f26f560c9eb1a34cb28db4ef52b03a2f618e`. CC0 covers structured Wikidata data, **not** operator prose, images, branding or every linked website. Original native coordinates identify features; no point is promoted to an arrival. Retain QID, query, exact JSON pointer, original snapshot and provenance. Operator pages provide bounded factual corroboration and internal audit receipts; no open redistribution license is asserted for their full bodies. Do not publish those bodies, copy their marketing descriptions/media, or infer a noncommercial grant from the app's lack of revenue. No NC-only data is admitted in this tranche. Magnolia's retained policies were inspected; no acceptance of new agreements occurred.

## Verification result and limits

All 20 immutable native point/name/ID bindings and state matches passed. All 8 proposed T2 records passed pinned rights, bounded literal primary identity/location/public visitor evidence and same-operator-host checks. No matches were found by the existing 250-metre or same-state normalized-name guard against the pinned **890 development rows**, or between proposed T2 rows. Broader semantic duplication still needs root review; the Belle Isle parent hold demonstrates why that guard alone is insufficient. Production may contain unseen additions.

Selected positive proof receipts total **2,845,198 bytes** (17 receipts, including five shared native/rights originals). The build is byte-identical on rerun. Full acquisition includes negative bodies for audit and deliberately does not convert success status/schema/hash checks into blanket factual verification. Source review is agent-assisted, with no independent human inspection, surveying or field verification. Current operating status, ticket inventory and weather cancellations remain unknown.

Every T2 profile must stay browsing-only. Root's existing deterministic 14-attribute profile generator supplies category-based traveler-fit inferences and 0.5 uninformative priors, explicitly labeled as inferences. Practical hours, costs, accessibility, amenities, reservation availability and arrival stay unknown in normalized fields. Literal seasonal/event restrictions remain source constraints. No paid model or live Mentro call is needed.

## Next queue

Do not repeatedly retry the twelve holds. Useful independent work is new operator cohorts and source diversity. Future arrival qualification leads exist at Dow's new welcome center, Museum of Life and Science's north/south lots, NC Arboretum's gate/building rules, and Cheekwood's parking/ticket calendar; none has an accepted independent arrival point or compiled dated calendar here. A materially new primary reopening source is needed for Mystic/McMath, explicit current public events for the observatories, and a genuinely obtainable appointment plus precise location for Miller. The live read-only catalog snapshot remains a release blocker, not a research blocker.
