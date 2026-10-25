# Entertainment coverage expansion — October 25, 2026 UTC

The previous fixed-rating San Francisco–Denver pool contained ten places, all in
California. Increasing its requested stops exhausted the higher entertainment
matches and selected trail destinations. This is a geographic coverage limitation;
it does not justify changing stored attraction ratings.

This expansion adds thirteen real, individually reviewed cultural and food
venues. Selection preceded AI scoring and used published visitor access and hours,
source identity, unchanged OpenStreetMap coordinates, a measured driving arrival
within 75 metres, and duplicate checks. Existing profiles, persona weights, the
5–25 mile bell corridor, selection objective, and paper sweeps remain unchanged.
This is a targeted dataset enrichment, not a random sample or an independent
validation of the AI's absolute rating accuracy.

| Destination | Official facts | Study corridor membership |
| --- | --- | --- |
| National Automobile Museum, Reno | [Visitor information](https://automuseum.org/visit/) | Medium, long, coast |
| Western Folklife Center, gallery and shop | [Visitor information](https://www.westernfolklife.org/where-we-are/) | Long, coast |
| Northeastern Nevada Museum | [Visitor information](https://museumelko.squarespace.com/about) | Long, coast |
| Clark Planetarium, public exhibits | [County operator](https://www.saltlakecounty.gov/clark-planetarium) | Long, coast |
| Carbon County Museum, Rawlins | [Visitor information](https://www.carboncountymuseum.org/contact-us) | Long, coast |
| Cheyenne Depot Museum | [Visitor information](https://www.cheyennedepotmuseum.org/hours-of-operation) | Coast |
| Denver Milk Market | [Visitor information](https://www.denvermilkmarket.com/location/denver-milk-market/) | Long |
| The Durham Museum, Omaha | [Visitor information](https://durhammuseum.org/visit/hours-and-admission/) | Coast |
| Des Moines Art Center | [Visitor information](https://desmoinesartcenter.org/visit/) | Coast |
| West Side Market, Cleveland | [Visitor information](https://westsidemarket.org/location/hours/) | Outside current corridors |
| Akron Art Museum | [Visitor information](https://akronartmuseum.org/visit/) | Outside current corridors |
| National Museum of the Great Lakes, galleries | [Visitor information](https://nmgl.org/visit/) | Coast |
| The Basque Market, Boise | [Visitor information](https://www.thebasquemarket.com/faq) | Medium |

The Cleveland and Akron venues are retained in the general dataset without
widening the research corridor. The Archway was held out because its building
spans I-80 and a centroid road snap did not establish a visitor entrance. Iowa 80
Trucking Museum was held out because the official page failed TLS validation.
Neither was admitted or rated from search snippets.

Published clocks are expanded into thirty dated calendars beginning October 25,
with no weekly fallback beyond the review horizon. Seasonal Monday/Tuesday
closures and Clark Planetarium's October 27 early closure are explicit. Ambiguous
Veterans Day access is omitted where the operator says major holidays are closed.
The museum ships at Toledo, separately scheduled performances, and neighboring
businesses are excluded from the relevant destination descriptions. Source facts
are paraphrased; no photographs or marketing descriptions are imported. Private
original responses retain acquisition times and SHA-256 hashes; the checked-in
review inventory pins their bindings. OSM locations retain ODbL attribution.

Generation `2b6426033674f2fafd1467f2896a7f6729a045bec039894d99f9c987c13b8297`
adds thirteen places and calendars to the unchanged 611-place/192-calendar parent.
The current generation has 624 places and 205 calendars. A fresh catalog-only
backup (3,436,560 bytes, SHA-256
`a4d9d99ea435e944eef831012de51e4bcdbc19e977a8f6f0b214c98d5c449493`)
was restored to a separate PostgreSQL 18 recovery database and all six parent
fingerprints matched. This recovery rehearsal is not a local fixture test gate.
The rollback receipt hash is
`c975858b7908b355c354ccc562adce4acbc24301a5ebd612eb5070301230aefe`.
No schema migration or application deployment is involved.

Only missing profiles for these new identities may receive a first AI rating.
Every prior rating row is compared with the pre-import snapshot. Utility remains
a deterministic persona-weighted sum of the permanent attribute profile. New
results must be reported as a separate dataset generation; seeded repeats are
not independent venue samples and improvements must not be attributed to a
solver change.
