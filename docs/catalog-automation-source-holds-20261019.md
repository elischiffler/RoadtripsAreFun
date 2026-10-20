# Sources held during the October 19 import work

This review found additional attraction identities but did not admit them. The
[source receipts and aggregate decisions](evidence/catalog-automation-source-holds-20261019.json)
record exact source hashes, byte counts and UTC acquisition times. Original source
bodies remain in ignored local research artifacts; no PDF artwork, photographs or
creative descriptions are destination fields.

## East Bay Regional Park District

The official [2026 Trails Challenge guidebook](https://www.ebparks.org/sites/default/files/TC-2026-Guidebook-web.pdf)
has twenty trail destination pages with native GPS points and published hours.
The retained [publisher terms](https://www.ebparks.org/terms-use) restrict use of
site materials and require permission for commercial use of copyrighted content.
No compatible reuse grant was confirmed. All twenty candidates remain held; a
publicly downloadable PDF was not treated as public-domain data.

Current park pages also contain component-specific restrictions. A trail's general
hours cannot override narrower parking gates, holiday closures or construction
closures. A future authorized import must reconcile those facts before admission.

## U.S. Fish and Wildlife Service

Three current official visitor pages supplied eight native map markers:

| Source | Result |
| --- | --- |
| [Don Edwards San Francisco Bay](https://www.fws.gov/refuge/don-edwards-san-francisco-bay/visit-us) | Two markers fall within the sampled SF–Monterey corridor, but their solar-hour restrictions do not establish fixed clocks. The Fremont visitor center has explicit weekend hours; its broader unit marker is outside the query radius and does not establish the exact center arrival. |
| [Ridgefield](https://www.fws.gov/refuge/ridgefield/visit-us) | Three entrance markers fall within the sampled Seattle–Portland corridor. Published numeric gate times also carry sunrise/sunset qualifications, so the numeric times alone were not admitted as opening hours. |
| [Stone Lakes](https://www.fws.gov/refuge/stone-lakes/visit-us) | Blue Heron Trails publishes seasonal wall-clock hours and visitor parking. Its native point is 14.74 miles from the nearest tested route sample, outside the existing five-mile query radius. |

These distances use retained real OSRM driving geometries, sampled at four-mile
vertices, and the existing five-mile radius. They are discovery diagnostics,
not measured detours or complete itinerary proofs. No FWS rows were admitted.

## OpenStreetMap acquisition

A bounded San Francisco Overpass query did not produce a complete usable source
response: the retained attempts recorded HTTP 406, an explicit server memory
error, and a read timeout. No OSM attraction adapter or additions were produced.
These acquisition failures do not establish that the requested area lacks
attractions. Error receipts are preserved in the aggregate evidence.

## Admission boundary

Additional native-linked NPS arrival research checked Presidio, Seattle's
Klondike visitor center and San Francisco Maritime facilities. Presidio's
[visitor-center page](https://www.nps.gov/prsf/planyourvisit/presidio-visitor-center.htm)
does not supply the complete scoped address/Car-section evidence needed by this
adapter. [Klondike directions](https://www.nps.gov/klse/planyourvisit/directions.htm)
carry street-parking, private-lot and street-closure qualifications.
[Maritime directions](https://www.nps.gov/safr/planyourvisit/directions.htm)
explicitly say there is no designated visitor parking lot. These findings do not
mean the sites cannot be visited; they do not establish an admissible ordinary-car
arrival under the current source contract. Existing healthy NPS companions were
preserved rather than replaced. The separate Omaha LECL admission and its full
evidence are recorded in [the import report](catalog-automated-import.md).

A usable import needs a publisher-native visitor arrival, public vehicle access,
a successful road-arrival check and a source-backed calendar. Missing facts stay
unknown. Solar-hour descriptions require an explicit, reviewed conversion process;
a convenient numeric gate time does not resolve a simultaneous solar restriction.
An administrative address or park centroid does not become a visitor entrance.

The hour-long batch therefore prioritizes sources that satisfy these conditions
and keeps source and access holds intact. This report does not establish database
activation, a production release, actual-arrival opening or parking availability.
