# Reviewed place context — 7 November 2026

This is a display enrichment review, not a catalog import or a claim of complete
place coverage. It adds **seven exact identity bindings and one optional photo**.
No hosted catalog was queried or changed. Current active/admitted coverage is
therefore **not verified**. A binding displays only when an already admitted,
refreshed source record matches its provider ID, source namespace, native name
and exact arrival coordinates. Admission, release holds, calendars and timing
remain authoritative and independent. All 133/170/7 existing pins are unchanged.

## Coverage and primary factual sources

| Identity | Visitor context reviewed | Primary source |
| --- | --- | --- |
| `boulder:284` | Stone shelter, trail connector, outdoor tables; indoor reservation distinction | [City of Boulder: Halfway House](https://bouldercolorado.gov/trailhead/halfway-house) |
| `boulder:272` | Named connecting trails, tables and absence of a trailhead restroom | [City of Boulder: Realization Point](https://bouldercolorado.gov/trailhead/realization-point) |
| `boulder:250` | Hiking starting point, Ranger Cottage information and picnic facilities | [City of Boulder: Chautauqua](https://bouldercolorado.gov/trailhead/chautauqua) |
| `nps-public:bica:visitor-center` | Relief map, geology/history exhibits, requested films, outdoor interpretation | [NPS: Cal S. Taggart visitor center](https://www.nps.gov/bica/planyourvisit/bighorn-canyon-visitor-center.htm) |
| `usfs:facility:5770.004481` | Paved half-mile historic interpretive loop, uphill sections and cemetery | [USDA: Boca Historic Townsite Interpretive Trail](https://www.fs.usda.gov/r05/tahoe/recreation/trails/boca-historic-townsite-interpretive-trail) |
| `usfs:facility:5340.004481` | Short connector to north/south PCT routes; winter Sno-Park payment qualification | [PCTA: Donner Summit PCT trailhead](https://explore.pcta.org/trailheads/donner-summit-pct-trailhead) |
| `nps-public:facility:lecl:1242` | Riverfront setting, film, period-clothing display and ranger information | [NPS: Omaha headquarters and visitor center](https://www.nps.gov/lecl/planyourvisit/lecl_headquarters.htm) |

The last three identities occur in the checked-in SF–Boise / SF–Chicago corridor
coverage evidence (`docs/evidence/catalog-automation-coverage-20261019.json`).
This does not guarantee that a newly generated route selects them. Native
truncated names and spacing are retained for exact matching. The other four
bindings match existing reviewed JSONL source arrivals. Context is original
factual paraphrase, not copied operator creative descriptions or inferred
persona/category labels. It supplies no new hours, tickets, reservations,
accessibility guarantee, itinerary duration, closure status or parking promise.

The two remaining new corridor identities — Hobart Mills / Prosser and Sawtooth
trailheads — remain unenriched. The bounded search found a historic event and a
county construction/access project respectively, insufficient to establish a
useful stable visitor description without confusing nearby trails or proposed
facilities. Other catalog places also remain unenriched. No generic category
sentence or stock photo fills those gaps.

## Photo and rights

Only Chautauqua has a photo in this review. The local asset
`frontend/public/place-images/chautauqua-trail-2026.jpg` is the source-provided
960×720 preview of **Chautauqua Trail in Boulder Mountain Park looking west at
6th Street Connector**, by **Dough4872**, photographed 27 October 2026 and
released by its author as **CC BY-SA 4.0**. Review records:

- [Pinned Commons revision and author own-work grant](https://commons.wikimedia.org/w/index.php?oldid=1295058964&title=File:Chautauqua_Trail_in_Boulder_Mountain_Park_looking_west_at_6th_Street_Connector.jpeg)
- [CC BY-SA 4.0 terms](https://creativecommons.org/licenses/by-sa/4.0/)
- Source preview URL, SHA-256, byte count, identity and rights reasoning are retained in the registry.

The image is self-hosted; no browser image hotlink, Google scraping, bucket or
new service is required. It is an unedited source-provided resized preview,
separately licensed from application code. Its October landscape does not
promise future conditions or identify the catalog arrival/parking location.
Author, image-record link, license link and resize notice accompany every
rendered image. The photo is optional; loading errors preserve the text.

An NPS Bighorn image had an explicit public-domain mark but uncertain location
identity, so it was rejected. Other Commons candidates had unresolved author or
import-review details and were rejected. NPS/Commons hosting alone is never
proof of reusable image rights. No operator web imagery was copied.

## Reuse pipeline and HTTP contract

`backend/app/catalog/place_context_registry.json` is the review artifact and
runtime registry. It contains original summaries, exact identity bindings,
review dates, primary-source URLs, bounded claim statements, source-page capture
hashes where obtainable, and image rights provenance. USDA's page was reviewed
through the web reader; direct HTTP capture was unavailable and is explicitly
recorded as such. Complete source HTML is not redistributed.

`app.catalog.place_context` has no network fallback. Call it only after the
existing server-side authoritative admission/source refresh. It independently
checks calendar/admission eligibility and exact identity. Ineligible, unknown,
renamed or moved records have no context until reviewed. It never reads caller
`place_context`, category-generated descriptions or photo URLs as authority.

- `Route.place_context` is an optional/default-empty map keyed by provider ID.
- `AlternativePlace.place_context` and `Itinerary_Stop.place_context` are nullable.
- Each context has `summary` and optional `image` (local asset, alt, dimensions,
  caption, creator, license and source-record links).
- `/generate-itinerary` always replaces supplied/serialized route context using
  refreshed source facts. Route-edit preview therefore also recomputes the map
  and itinerary after authoritative source and actual-road checks.
- Derived context stays **outside physical source stop dictionaries**; no
  pinned exact-row projection/admission allowlist is broadened.
- Missing context is omitted in the UI. Legacy trips still load.

`PlaceContext.jsx` is the reusable rendering component. Itinerary arrivals,
nearby idea lists/sheets and map details use it. Provider map popups render its
summary as DOM text. Image references must be local raster assets with the
reviewed license/credit contract; invalid or missing rights suppress the image.
No data-source paragraph appears in these traveler views. Source/provenance
fields remain in records for internal audit; necessary per-image credits remain
visible. Onboarding can reuse the component when its ideas carry this contract.
The image height is a master design token; gaps, typography, color and radii use
the existing design variables.

To expand coverage: identify an existing admitted native place and arrival,
review relevant operator/primary factual claims, write original bounded prose,
add review receipts and identity, and run the regression suite. Photos require a
separate per-file rights/identity review, local asset and hash, legal credit and
license. A registry entry grants no catalog admission and clears no hold.
