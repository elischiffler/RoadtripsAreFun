# Automated hours and visitor-arrival imports

The October 19 develop work adds bounded acquisition, offline source replay,
duplicate checks and portable import assembly for National Park Service visitor
facilities and USDA Forest Service recreation facilities. Runtime discovery,
calendar filtering, routing and saved trips keep their existing contracts.

The completed imports add **five places** along the SF–Boise/SF–Chicago corridors
and fills missing calendars for **35 existing places**. It preserves every field
of all 603 parent places and all 149 parent calendar companions. The candidate
contains **608 places and 189 companions**. The 35 existing-place updates are
national; they do not all lie on the tested routes.

| New visitor facility | Published daily hours | Road destination distance from native point |
| --- | --- | ---: |
| Hobart Mills / Prosser Trailhead | 06:00–22:00 | 0.24 m |
| Sawtooth Trailhead | 06:00–22:00 | 4.13 m |
| Donner Summit Pacific Crest Trailhead | 24 hours | 0.33 m |
| Boca Historic Townsite Interpretive Trail | 06:00–22:00 | 9.56 m |
| Lewis and Clark National Historic Trail Visitor Center, Omaha | 08:30–16:30 | 20.69 m |

These are source-backed visitor facilities with documented car parking and
driving approaches, checked against actual OSRM destination responses. Native
coordinates and native stored names are preserved, including publisher title
truncation. They are not surveyed gate coordinates or parking availability.
The source review window is a bounded admission policy, not an agency guarantee.

## Repeatable commands

Run from the repository root using Python 3.12 with the pinned backend
requirements installed and the existing configured database connection. Keep
outputs in a new private directory; acquisition and builds refuse overwrites.
No credentials belong in command arguments or checked-in files.

```sh
backend/.venv/bin/python scripts/catalog_automated_import.py refresh \
  --output .artifacts/catalog-refresh-NEW \
  --nps-arrival-page-url 'https://www.nps.gov/lecl/planyourvisit/directions.htm' \
  --parking-publication-url 'https://www.fs.usda.gov/sites/nfs/files/r05/tahoe/publication/Equestrian%20ROG%202025.pdf'
```

`refresh` reads a consistent **catalog-only, read-only** parent snapshot,
captures the fixed test routes when no `--routes-index` is supplied, acquires the
reviewed official sources and prepares an import. It never stages or activates a
database generation. A run with no usable changes records `status: no_change`.
Source acquisition counts and `partial_source_acquisition` stay visible even
when no additions pass. Failed unit downloads remain unknown, never an empty
successful source or proof that no attractions exist. A completely empty native
acquisition fails source replay. The final real NPS acquisition retained two
unsuccessful units explicitly; the admitted Omaha evidence is complete.
Existing retained routes can be supplied with `--routes-index PATH`.
`--sources usfs-current` limits acquisition to Forest Service data; the default
also acquires NPS visitor-facility data. This is a command-driven import process;
no recurring job or production scheduler is installed.

Individual operations are also available:

```sh
backend/.venv/bin/python scripts/catalog_automated_import.py routes --output .artifacts/routes-NEW
backend/.venv/bin/python scripts/catalog_automated_import.py snapshot --output .artifacts/parent-NEW
backend/.venv/bin/python scripts/catalog_automated_import.py acquire \
  --source usfs-current --output .artifacts/usfs-NEW \
  --parent .artifacts/parent-NEW --routes-index .artifacts/routes-NEW/index.json
backend/.venv/bin/python scripts/catalog_automated_import.py build \
  --parent .artifacts/parent-NEW \
  --source usfs-current .artifacts/usfs-NEW/bundle.json \
  --routes-index .artifacts/routes-NEW/index.json --output .artifacts/import-NEW
```

Use the optional parking-publication flag during acquisition as well when
reproducing Donner's separate parking corroboration. Only reviewed official
publication URLs are accepted. Route capture and source acquisition make network
calls; `build` and subsequent source replay are offline. Receipts retain complete
response bytes, URL, acquisition time and SHA-256, with source-specific reuse
notices. Partial or erroneous responses do not become empty successful datasets.

Review `completion.json`, `arrival-decisions.json`, `catalog.preview.json`,
`calendar.preview.json`, `catalog.manifest.json` and the retained evidence. The
calendar preview contains **new updates**, not the inherited companion set.
The portable activation input is `catalog.enrichment.json`. Existing explicit
stage, activation and frozen-receipt rollback operations remain in
`scripts/catalog_incremental_import.py`; ordinary refresh cannot invoke them.

## Admission rules

USFS acquisition paginates the published facility inventory, selects new native
facilities near the retained route geometry and revisits existing native catalog
identities. A separate, unfiltered native-ID lookup of the older public feed is
retained even when empty. Known closures and other negative access facts always
veto admission. A missing older record is recorded as unknown; it is never
rewritten to OPEN. The primary agency service metadata explicitly identifies its
facts as inputs to public visitor webpages. That publication contract is required
for the separate primary-feed path; legacy qualification is unchanged.

Positive admission requires published operational status, unchanged finite native
coordinates, a Census state-boundary match, supported visitor-facility type,
documented parking and driving directions, complete literal clock hours and a
successful actual road destination within 75 m. Source seasons, qualified access,
vehicle warnings, closure text and applicable second-feed clocks remain binding.
Solar-hour statements and unresolved prose receive no guessed numeric hours.

The optional USFS PDF path extracts only a literal ordinary-vehicle parking
statement. It joins a unique complete facility title to the native approach,
forest and region, and rejects ambiguous or conflicting bullets. Donner's 2025
publication supplies parking corroboration; the current structured feed supplies
its hours, status and native coordinates. Older water claims are not imported.
The PDF's overnight camping ban is retained separately from parking access.

NPS acquisition uses the published unit inventory, original visitor-center
records, applicable unit/component hours, holiday/closure facts and parking
evidence. All applicable facility, parent and specifically related parking hours
intersect. Unrelated campground hours cannot stand in for visitor-center hours;
ambiguous component relationships are held. Explicit car-parking amenities and
published car directions may establish a visitor arrival on an unnamed parking
aisle; a nearby road alone cannot establish public access. The original response
and road destination are both replayed. Nine NPS facilities pass the initial
native-only source review; four supply missing parent calendars, while the other
five are held by existing calendar, collision or route-scope checks. The optional
native-linked arrival-page path admits a tenth facility, the new Omaha visitor
center. It requires an exact native formal title and full address in one scoped
section, followed by one typed Car section with literal approaches and visitor
parking. Global headings, pre-heading alerts and surrounding access/clock
qualifications can veto admission. Hours and coordinates still come exclusively
from native facility records. RV, bus and oversized-vehicle qualifications are
retained; only ordinary-car arrival is established. No fuzzy address, geocoding
repair or per-venue parser profile is used. `--nps-arrival-page-url` is an explicit
bounded selector; supplied URLs must be native-linked before acquisition, with
redirects rejected.

Every new arrival passes native identity, same-name/region and 250 m spatial
collision holds against the parent and other additions. No collision is resolved
by moving coordinates. New additions must lie within the existing five-mile
sampled test-route radius. Missing-hours updates require one identical explicit
publisher-native identity and exactly unchanged coordinates. Fuzzy names and
nearest neighbors cannot bind calendars. Original primary source release and
credits stay unchanged; supplementary calendar credits remain attached.

**Existing calendars are not renewed or replaced**, including expired, held or
manually reviewed companions. Embedded calendar facts also prevent automatic
binding. This process adds places and fills missing hours; a separate reviewed
renewal process is still needed before existing review windows expire. A later
`no_change` result does not establish that the whole catalog has fresh calendars.

The unchanged import ceilings remain 50,000 source units and 100 MiB consumed
evidence, with existing manifest/catalog/database limits. Portable assembly also
caps all retained source files together at 100 MiB / 50,000 files, including
unused discovery files and duplicate copies. Validated consumed bytes and retained
file bytes are reported separately. Bound source rows remain charged even when
selection holds them. No database plan upgrade or admission threshold increase is
part of this change.

## Measured result and boundaries

[The retained coverage comparison](evidence/catalog-automation-coverage-20261019.json)
uses eight genuine OSRM route receipts, four-mile geometry vertex samples, the
unchanged five-mile radius and sixty-result bounds. At capture time, six corridors corresponded to
unique Studio presets; Seattle–Portland and LA–Phoenix are additional checks.

| Route | Structurally eligible nearby places before → after | Oct 20 published two-hour clock fits before → after |
| --- | ---: | ---: |
| LA–San Diego | 10 → 10 | 1 → 1 |
| SF–Boise | 5 → 9 | 2 → 6 |
| SF–Chicago | 7 → 12 | 3 → 8 |
| SF–LA | 11 → 11 | 1 → 1 |
| Ely–Reno | 0 → 0 | 0 → 0 |
| SF–Monterey | 6 → 6 | 0 → 0 |
| Seattle–Portland | 3 → 3 | 2 → 2 |
| LA–Phoenix | 10 → 10 | 1 → 1 |

Clock-fit arithmetic uses explicit source-local dates and an **artificial UTC
zone**, with a chosen 120-minute comparison dwell. It is not the runtime's actual
candidate timezone, arrival time or dwell estimate. These read-only measurements
do not prove a feasible personalized itinerary, live parking inventory or future
access. The exported hosted catalog is diagnostic input, never a fixture used to
clear local PostgreSQL or recovery gates. Local tests use synthetic facts.

The first import replays 4,751 source units and consumes 41,490,115 bytes. Broader initial
source discovery is retained separately and is not mislabeled as admitted rows.
The 4,751 units include 603 parent rows, 3,802 NPS records and 346 USFS records.
Portable retained evidence occupies 61,223,291 bytes across 570 files; generated
previews and manifests are separate output overhead.
Intermediate 607-place generation:
`5e522dd7323ad41cda32cd53c88dfc565348c83947da2e5a06959403fb16ef6c`.
Original 603-place parent generation:
`49e0069bd6544ca370b3123bf6ae36f0ef5e324a9bc3ba84cf6c144be69e79fe`.
The first private portable source bundle is under
`.artifacts/catalog-automation-20261019/final-bounded/`; raw publications and complete
source bodies are intentionally not checked into Git. The second import adds
only Omaha to that actual 607-place parent, preserving all 607 rows and 188
companions. It replays 611 units (607 parents plus four native NPS records),
consumes 5,306,118 bytes and retains 1,541,846 evidence bytes across 20 files.
Final 608-place generation:
`e1dac379fb6863d9c5e8415e925a8394cb9b949919ee835defc564984a406ede`.
Its private portable bundle and recovery receipt are under
`.artifacts/catalog-automation-20261019/lecl-candidate/`.

Other investigated sources remain held. The
[source research report](catalog-automation-source-holds-20261019.md) records
publisher reuse restrictions, unresolved solar hours and incomplete Overpass
responses. No held source was converted into an admission to inflate counts.

## Release status

Implementation is developed only on `develop`. No main release or application
deployment is part of this task. Catalog staging preserves the existing active
pointer. The 607-place candidate was staged in the configured hosted catalog;
its frozen rollback receipt is retained and verified against both stored
generations. Measured hosted catalog storage is 16,515,072 bytes and total database
storage is 42,385,408 bytes, below unchanged limits. These are dated staging
measurements, not local-test fixtures or future capacity promises. The release
owner confirmed the recent verified off-host backup in this chat after the
existing [recovery-freshness boundary](catalog-growth-20261016.md#release-boundary)
was explained. This is owner attestation; the host marker was not independently
read in this session, and local restore tests were not substituted for it.
The intermediate candidate was atomically activated at **2026-10-20 02:26:18 UTC**.
The additional Omaha import was staged, given its own verified frozen recovery
receipt, and activated at **02:34:59 UTC**. The active generation now has **608
places and 189 companions**. Both 603/607-place generations remain verified
rollback targets. Final measured hosted catalog storage is 19,898,368 bytes and
total database storage is 45,768,704 bytes. No user or saved-trip table is in the
import's write scope.

## Verification

[The verification receipt](evidence/catalog-automated-import-20261019.json)
records offline build fingerprints, aggregate retained source size, hosted
staging, activation and read-only application repository queries. All five new
places return through the real active-catalog query with their current source
calendars; chosen Pacific/Central-zone Oct 20 two-hour clock checks pass. This is a
read-only hosted diagnostic, not a live trip. A separate real one-command run
captured fresh routes, acquired USFS/PDF evidence and prepared four new arrivals
plus 31 missing-hours bindings without database writes. Its parent read preceded
activation, so its independent proof artifact was not staged. A separate complete
NPS refresh fetched the full native inventory plus the explicitly selected
official arrival page, then prepared only the Omaha addition against the 607-place
parent. That fresh acquisition/replay proof made no database writes and was not
substituted for the independently reviewed, frozen source artifact.

Python 3.12 Ruff format/lint pass. The
frozen backend suite passes 1,984 tests with 130 optional tests skipped and
79.98% coverage, above the unchanged 63% threshold. A separate synthetic-data
PostgreSQL 18 run passes all 63 selected catalog, binding, SQL and recovery tests.
Frontend format, lint, 262 tests (91.85% coverage) and production build pass.
Container smoke and the disposable CRUD/recreation/backup/restore run pass.

The local developer environment allows only the localhost development origin;
its existing 127.0.0.1 preflight test fails when that environment is inherited.
The reported passing backend run explicitly supplies the normal development
CORS origin list. No developer secrets/configuration or application CORS behavior
was changed. Early runs overlapping PDF test edits are superseded by the frozen
suite. This does not establish complete live provider trips. Production recovery
freshness is recorded as release-owner confirmation rather than independently
collected host evidence.
