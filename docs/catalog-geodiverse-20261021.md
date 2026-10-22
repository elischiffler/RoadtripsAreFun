# Diverse regional expansion and noncommercial-source review

This cloud-local checkpoint adds **41 source-admitted T2 browse-only places**:
38 from a 60-prospect regional operator batch and 3 from a separate 4-record
Baltimore Heritage source batch. The batch has **23 holds and zero T3 additions**.
The original 153 normalized admissions are preserved byte-for-byte. The program
now has **194 browse-only admissions**, with a local diagnostic comparison of
**849→890** places including the 696-row earlier baseline. These are development
results, not live net additions or production database writes. The 5,000 target
is unfinished and its browse-only versus itinerary-ready counting decision remains
unanswered.

## Measured acquisition and coverage

| Queue | Dispositions | Source-review proposals | Final T2 | Held | T3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Regional museums |30|19|18|12|0|
| Gardens, animal attractions and observatories |15|9|9|6|0|
| Caves, heritage railways and lighthouses |15|11|11|4|0|
| Separate Baltimore source |4|3|3|1|0|
| Total |64|42|41|23|0|

The 60-place queue was selected across 25 states, beyond the prior CT/DE focus.
Actual admissions cover **22 states**. They include 16 museums,4 gardens,4 caves,
4 heritage railways,3 animal attractions,3 lighthouses,2 science centers,2 historic
sites,2 observatories and 1 visitor food experience. These are review-classified
destination types, not a verified activity inventory. The 600-prospect pilot still
has its original denominator:191 admitted and 409 held. Baltimore's 4 prospects
are a separate bounded source artifact, not replacements for pilot rejections.

New places include the West Virginia Mine Wars Museum, Squirrel Cage Jail,
International Quilt Museum, Museum of the Great Plains, Georgia Aquarium,
Alaska Botanical Garden, Lost Sea, Natural Bridge Caverns,1880 Train, Cass Scenic
Railroad, Fort Gratiot Light, Tybee Island Lighthouse, Absecon Light, Peabody
Heights Brewery, Baltimore Streetcar Museum and Bromo Seltzer Tower. Current
published public visitor purpose was reviewed separately from each native feature
point. No feature point became a legal vehicle arrival by implication.

The National WWII Museum/Ogden Museum pair is 117.2 m apart. The unchanged 250 m
co-location gate held one; this is an unresolved co-location review, not a claim
that the two institutions are actually the same place. Grand Canyon Railway's
source point identifies a distant rail corridor rather than a visitor depot and
stayed held. Other holds preserve reassigned domains, seasonal closure, stale
public-night information, blocked access, an access challenge returned as HTTP200,
and explicit copying restrictions. Previously unresolved entrances and 403 hosts
were not repeatedly probed. Cumbres' coarse source point remains a feature with
precision limitations, not a depot-arrival assertion. Observatory public nights
remain event/weather-specific; campus ownership does not imply public entry.

All accepted profiles use the existing 14 attributes without model calls. Character
and traveler fit are labeled category-based inferences; unknown attributes retain
explicit 0.5 priors. Unsupported activities, maintained hours, prices, accessibility,
amenities, arrival points and calendars remain unknown. No source authenticity or
field truth is established solely by schema, byte-hash or Census checks.

## Creative sources and the noncommercial context

The new context that the app earns no money broadened source review. It did not
automatically establish permission to redistribute, transform, scrape or monetize
any particular source. Six catalogs were inspected with 34 bounded original-request
receipts (~2.05 MB). The reviewed ledger splits Baltimore fact/text and photo rights
into separate scopes, so it contains seven scoped source entries.

| Source | Actual grant/scope finding | Decision |
| --- | --- | --- |
| [SERC Montana geoheritage](https://serc.carleton.edu/research_education/mt_geoheritage/sites/Red_Lodge_Beartooth_Pass_Cooke_City.html) | Display says BY-NC-SA4.0 but the actual license link points to3.0. Individual media can have different rights. | Two geological-stop leads quarantined; version, ShareAlike, intended use, coordinates/current public access and duplicates unresolved. |
| [Texas Historical Commission](https://thc.texas.gov/policies) | Express noncommercial agency reuse language, with third-party/image exceptions. | French Legation operator evidence retained; intended-use qualification, transformed-profile scope and location/arrival/dedup remain unresolved. |
| [Living New Deal](https://livingnewdeal.org/disclaimer/) | Unspecified NCND scope, third-party exceptions; agent access restriction discovered. | Acquisition stopped; no place records collected or admitted. ND/factual-extraction questions remain separate. |
| [GFZ night-sky atlas](https://dataservices.gfz-potsdam.de/contact/showshort.php?contactform=&id=escidoc%3A1541893) | Indexed primary metadata suggests NC4.0, but direct metadata returned503. It is context raster data, not visitor destinations. | No download/retry/admission; primary grant and context use unresolved. |
| [HistoricBridges](https://historicbridges.org/info/about/index.php) | No broad NC/database reuse grant established. | Discovery only; no copied catalog records. |
| [Explore Baltimore Heritage](https://explore.baltimoreheritage.org/) | Publisher work uses CC BY4.0; sampled Steve Earley photograph1551 separately uses BY-NC2.0. | Three factual destinations admitted through a new typed permissive adapter; photo excluded. Phoenix Shot Tower held for explicit temporary closure. |

The exact questions, attribution, license URLs/versions, retention/access terms,
original hashes and limitations are in `rights-research/source-ledger-reviewed.json`.
The source ledger's conflicting/unknown values remain conflicting/unknown. There
are **zero NC-source catalog admissions**. Four restricted research records remain
separate: three place leads and one photo reference, with no photo downloaded.
The four Baltimore factual discovery records are separately identified as permissive;
three were later admitted by the typed adapter, not by the research partition.
Do not count these overlapping discovery records again as additional attractions.

`catalog_rights_partition.py` emits separate `noncommercial_only`,
`permissive_discovery` and `unclear_rights` collections. Every research record
remains T1 with no profile and no browse/routing eligibility; NC-only records carry
`future_monetization_excluded=true`. A future approved NC adapter would still need
exact grant/context, public-access, identity/location and duplicate gates. Rights
labels alone do not grant admission. The new namespace also fails runtime admission
without a valid marker if a quarantine record is accidentally presented as a place.

The [BY-NC4.0 deed](https://creativecommons.org/licenses/by-nc/4.0/) distinguishes
commercial purpose from merely receiving money, and
[BY-NC-ND4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) restricts sharing
adapted material. Whether a factual extraction constitutes protected adaptation,
and whether this app's actual intended use qualifies, require separate source/use
review. No owner was contacted and no new agreement accepted.

## Baltimore implementation and source attribution

The new `baltimore-heritage` family permits only the four reviewed item endpoints
with `output=mobile-json`. Original native fields `/id`, `/title`, `/latitude` and
`/longitude` must belong to the same original item. The endpoint ID must equal
the native ID. Homepage grant bytes are pinned; Bromo's named contributor is
additionally bound to its exact item-page grant and byline. Unreviewed contributors
or photo-license substitutions fail closed. Current operator identity/address and
public visitor purpose are separate evidence checks.

Each row credits its native creator, item title, canonical item URL, CC BY4.0 URL,
and extraction/enrichment changes. Original modified metadata is retained without
claiming a current opening status. No article prose, photos or marketing descriptions
enter app profiles. The public attribution page carries the new source credit.
For example, Peabody Heights gets an inferred food-interest fit and an explicitly
unknown arrival/timing context; family suitability and amenities are not inferred.
The [Shot Tower source](https://explore.baltimoreheritage.org/items/show/200) does
not override its operator's temporary-closure statement or substitute Carroll
Mansion's address/hours.

## Reproducibility, budgets and local database proof

Operator updates use the frozen QID/source-hash queue. The merger now accepts
explicit unique queues of at most 100 records, including diversity IDs, and permits
previously retained native snapshots absent from the earlier bundle only when
their original hashes match the prepared queue. It never grants T3. Receipt
namespaces are content-bound, source facts/rights remain immutable, and untouched
review timestamps are not renewed. Lighthouse and heritage-rail persona rules
only add labeled category inferences.

The source assembler preserves its default 600-prospect behavior while allowing
an explicitly declared smaller bounded artifact. Baltimore was assembled as 4
records against the verified 191-row development comparison plus the 696-row earlier
baseline. This checks its three additions against all 887 existing local rows.
The 64 MiB per-source and 100 MiB aggregate guards were preserved. Approximately 24 GiB
workspace disk remained; no large source download was attempted.

Two separate disposable loopback PostgreSQL proofs staged twice, checked pointers,
activated, retrieved every 191/3 accepted record through the actual browse repository,
confirmed routing/calendar exclusion and rolled back while preserving synthetic
parents. They are separate development proofs, not a joint production import.
The eventual combined release still needs the real complete immutable parent and
cross-source typed import preparation.

| Measurement | Main proof | Baltimore proof |
| --- | ---: | ---: |
| Accepted source rows |191|3|
| Rows including one synthetic parent |192|4|
| Calendar companions |0|0|
| Consumed bytes |53,075,264|19,212,671|
| Retained evidence bytes |52,151,272|19,188,042|
| Retained evidence files |243|21|
| Source scan accounting units |2,703|952|
| Database bytes |9,336,511|8,156,863|

Scan units include discovery rows, comparison rows, Census features and the synthetic
parent; they are not additional-place counts. The small Baltimore proof repeats
fixed Census/comparison overhead, so these totals cannot be extrapolated as cost
per attraction. No hosted capacity, price or production-schema claim is made.

Originals, acquisition/review scripts, immutable source artifacts and logs remain
under `/workspace/catalog-geodiverse-20261021/`. The checked-in
[audit directory](data/catalog-geodiverse-20261021/) contains all 41 new additions
and profiles, complete source decisions, coverage, rights partitions and recovery
proof. Raw operator bodies remain private. No public artifact URL was created.

```sh
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot_followup.py \
  --base /workspace/catalog-followup-20261021/assembled-final \
  --update /workspace/catalog-geodiverse-20261021/museums/updates.json \
  --update /workspace/catalog-geodiverse-20261021/gardens/updates.json \
  --update /workspace/catalog-geodiverse-20261021/niche/updates.json \
  --queue docs/data/catalog-geodiverse-20261021/queue.json \
  --output /workspace/NEW-regional-replay
/workspace/roadtrips-venv/bin/python scripts/catalog_pilot.py assemble \
  --input /workspace/catalog-geodiverse-20261021/baltimore/adapter-inputs.json \
  --states /workspace/catalog-followup-20261021/assembled-final/states.json \
  --expected-prospects 4 --comparison /workspace/NEW-regional-replay \
  --release catalog-baltimore-20261021 --output /workspace/NEW-baltimore
```

## Next work and remaining decisions

`next-queue.json` prepares another 60 unreviewed prospects across 20 states:24 museums,
12 gardens,4 animal attractions,2 observatories,2 caves,8 roadside sites,5 lighthouses
and 3 heritage railways. It excludes the just-reviewed records, known admitted QIDs,
and prior detailed holds. Accumulated blocked URL/host ledgers must be checked again
before probing. This is a work queue, not admission or bulk-access permission.

Use a new standalone source artifact and compare all 890 local rows; do not grow
the 600-prospect bundle indefinitely or enlarge its byte ceilings. Archive old source
evidence with immutable hashes and preserve old approval stamps. Preparing the
complete 890-row local comparison for the next independent batch is routine cloud
development work; it does not require a production connection. Public-arrival and
calendar leads need materially new evidence, not repeated probes of held entrances.

No user decision blocks that permissive next batch. NC-only reuse needs the exact
source-specific questions above resolved before implementation. Release still needs
the complete authorized live-parent catalog/calendar snapshot and generation/hash
reconciliation; its earlier network-unreachable failure was not retried through the
unapproved desktop. No production writes, push, deployment, paid APIs, live Mentro
calls, new accounts/credentials or desktop execution occurred. The program remains
in active development toward 5,000 net additions; neither 194 browse records nor the
documented hosted 608 count establishes that target.

Validation: **2,120 backend tests passed, 138 optional skips, 80.73% coverage**;
**71 real PostgreSQL regression tests passed**, including admission before limits.
**278 frontend tests passed** (92.37% coverage), along with frontend format/lint/build,
backend/changed-script Ruff format/check and Git whitespace checks. Source-specific
reviews and the private integrity checks are separately recorded in their ledgers.
Two timing-sensitive backend assertions failed during the initial parallel run;
the performance comparison passed on isolated retry. The streaming test incorrectly
assumed route-start was frame two, excluding a valid startup heartbeat. Its fix
keeps the existing half-second responsiveness deadline and adds an explicit assertion
that the blocked provider has not finished. The streaming implementation and timing
thresholds were unchanged. The final complete suite passed. Full application-container
smoke, live provider trips and production recovery were not run. The existing Vite
large-chunk warning remains.
