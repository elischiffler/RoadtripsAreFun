# Standalone museum review, 2026-10-21

Exactly 24 prepared museum IDs were reviewed. Final dispositions are **11 source-reviewed T2 browse recommendations, 13 T1 holds, zero T3**. No live or production database additions are claimed. The root must apply combined-cohort and semantic duplicate gates against the 890-record local comparison, then reconcile the live catalog.

The recommendations are Marble House, Rosecliff and The Breakers in RI; and 1850 House, Alexandria Museum of Art, Longfellow-Evangeline State Historic Site, Louisiana History Museum, Middle American Research Institute gallery, New Orleans Historic Voodoo Museum, New Orleans Museum of Art and Newcomb Art Museum in LA. Five are classified as historic sites and six as museums. University recommendations have actual property-specific public gallery visitor pages, not merely institutional homepages. The statewide Louisiana State Museum parent is held to avoid duplicating its separately identified properties.

The unchanged 250 m diagnostic flags Voodoo Museum and 1850 House, 73.8 m apart. Distinct operator names do not resolve semantic duplication or coordinate concerns. The root may hold an otherwise positive recommendation. Feature coordinates remain unchanged, not arrival locations. Visitor purpose is supported by dated primary statements, not field inspection or live status.

The 13 holds preserve: Brown Library's 503 robots failure; prior unresolved Jamestown Historical Society policy; Musée Patamécanique's uncorroborated precise physical location; illustration museum renovation closure; Watson Farm's season ended and private house; Whitall House's conflicting seasonal cutoffs and rate-policy failures; New Sweden Farmstead's unresolved former-point/relocation scope; Backstreet Museum's conflicting operator location metadata; Bontemps Museum's missing current primary admission evidence; JAMNOLA's unresolved broad service-copying terms; the Louisiana State Museum institutional parent; Madame John's Legacy restoration closure; and Audubon Nature Center's acquisition rate-policy failure. Unknown reopening dates and old source points are not silently repaired.

## Rate-policy error and quarantine

The inherited fetcher used serial 1.1-second spacing but omitted applicable robots crawl delays. Final offline audit found three request-start gaps below known policy:

| Target | Observed gap | Required |
|---|---:|---:|
| Gloucester County `/671/Red-Bank-Battlefield`, after robots | 1.826977 s | 10 s |
| Audubon Nature Institute `/nature-center`, after robots | 1.527716 s | 30 s |
| Gloucester County `/copyright`, after facility page | 2.219479 s | 10 s |

These were actual acquisition-policy misses. All operator evidence for both affected destinations is held; Audubon was removed from the positive adapter. No request was made to remedy the timing. `rate-policy-audit.json` gives exact URLs, prior requests, timestamps, policy receipt IDs and every applicable comparison, including first content and redirects. Requests have start timestamps, not completion timestamps, so the audit cannot certify completion-to-start gaps.

`acquire.py` is corrected offline to enforce user-agent crawl delay and request rate, including first content after robots, redirects and recent persisted receipt timestamps. `test_timing_policy.py` uses a fake clock and fake HTTP responses with real networking disabled: first content and redirected content each wait 12 seconds for a 10-second policy; immutable replay issues no request. Future compliant acquisition of affected sources needs separate authorization; this package does not re-fetch them.

## Evidence and reproduction

`adapter-inputs.json` is a complete standalone adapter for all 24 records. Its 15 evidence receipts retain the three exact original Wikidata state-box JSON files, original CC0 rights grant, and 11 selected successful operator bodies. Total adapter evidence is 2,387,280 bytes. All acquired response bodies total 6,989,362 bytes across 55 serial public GET receipts, within the 80-attempt/1 MiB-per-content caps. Original native labels, IDs, points and RFC6901 pointers are replayed without alteration. Negative and terms-review bodies remain private under `raw/`, with immutable URL/timestamp/status/SHA receipts.

`build_adapter.py` is offline and replays all 24 native rows and Census state containment, plus positive canonical-source contract, CC0 grant and literal operator proofs. `validation.json` records socket-disabled idempotency and retained-body hash checks. `acquire.py` and `followups.py` default to offline; their explicit acquisition lists are bounded. Acquisition is now stopped. No repository edits, commits, production operations, paid API/AI calls, credentials, agreements, accounts, push, deployment or desktop execution occurred.

The structured facts remain Wikidata CC0. Operator bodies are restricted local review evidence, not an operator-text redistribution grant. Alexandria's collection-object text/images, Tulane image/archival/filming material, NOMA reproductions and Newcomb images have specific permissions; none are imported or transformed into profiles. Existing deterministic profile generation can supply the 14-attribute schema with labeled category inferences and unknown practical fields. This review does not assert hours, costs, amenities, accessibility, current operating status or arrival readiness as maintained catalog facts.

Next work is root combined admission/deduplication and profile generation. Remaining source holds require materially new evidence or separately authorized compliant review; no repeated denial or entrance probes are proposed here. The live snapshot and final 5,000 counting criterion remain separate program gates.
