# Selected-arrival parking calendar correction

Seven NPS visitor-facility calendars omitted relevant parking access facts.
The correction preserves all 603 place identities, coordinates, source fields
and provenance. It retains 149 companion records, changes exactly seven to an
explicit unresolved-access hold, and preserves the other 142 companions.
The published indoor clocks remain retained source facts; the hold prevents
automatic scheduling until the selected arrival's access is resolved.

| Selected facility | Unresolved source access |
| --- | --- |
| Wupatki Visitor Center | Named visitor lot has native sunrise/sunset bounds. |
| Manzanar Visitor Center | Selected parking publishes dawn-to-dusk prose and solar bounds. |
| Youngsholm | Adjacent-lot description binds the selected building, but solar bounds and a native longitude-sign conflict remain unresolved. |
| Plains High School Visitor Center | Both passenger and bus/accessible lots have solar bounds. |
| Hampton Visitor Contact Station | Main-lot fixed clocks and dawn-to-dusk prose must both be retained. |
| Chiricahua Visitor Center | Main-lot 03:00 AM–02:30 AM has no published next-day offset; separate overflow does not establish a verified alternate arrival. |
| Scotts Bluff Visitor Center | Selected-center lot has solar bounds; the summit lot is a different component. |

[Reviewed selections](data/catalog-parking-holds-20261016/decisions.json)
pin each original source URL, SHA-256, acquisition timestamp, native facility
pointer/ID, lot pointer/ID and schedule ID. No sunrise/sunset clock, AM/PM
correction, overnight offset or coordinate correction is inferred. The Clinton
Birthplace ordinary-car arrival has explicit W. Division Street parking; its
W. 2nd Street accessible/large-vehicle lot remains a separate conditional fact
and is excluded from these seven holds. No actual future closed visit is claimed.

`scripts/catalog_parking_holds.py` builds the portable correction offline from
a frozen parent export and the retained original evidence. It verifies hashes,
unchanged native facility coordinates and identities, and exact selected lot
and schedule identities. Existing constraints and calendars are preserved;
the native selected parking records are added as separately attributed facts.
The normal bounded importer and guarded SQL compiler stage a new immutable
generation and retain the prior generation for rollback.

Automatic discovery rejects explicit calendar holds before its result limit.
The CP-SAT selection, possible-visit filter and hard visit solver reject them
as well. Optional live, supplied and persisted evening suggestions now reject
explicit held or malformed calendars instead of offering a tentative visit.
Ordinary untimed outdoor places and tentative evening options without an
explicit source calendar retain their existing behavior.

Before final route timing and shared HTTP/chat itinerary rebuilding, one bounded
catalog read refreshes the current active source facts for stable catalog IDs.
Stale or stripped calendars cannot override a current hold. Missing identities,
unrecognized aliases, changed arrival coordinates and changed visit types fail
closed. The refresh never silently moves a road-routed arrival. Optional-only
verification failures remove suggestions while preserving the hotel and route.
These reads and in-memory projections do not update saved trips or user tables.

Regression coverage includes all seven IDs, stale and stripped provenance,
legacy policy omission, changed stop types, identity aliases, coordinate
changes, lookup failure, HTTP and all three chat route-resolution paths, live
and saved evening alternatives, and ordinary unknown-outdoor controls. The
private source bundle contains actual isolated PostgreSQL 18 discovery and
runtime proofs, repeated atomic activation/rollback, an unchanged saved-trip
sentinel, and exact raw/companion comparisons.

Independent review and established production recovery gates precede deployment
and atomic activation. This document does not assert production correction,
the user's failing route, browser saved-trip acceptance or Windows execution.
