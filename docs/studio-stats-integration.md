# Studio statistics and develop integration

October 19, 2026 (America/Los_Angeles). Requested scope: simplify Studio's
Algorithm details section and consolidate compatible outstanding PRs into develop.

## Included changes

The local integration starts from develop `aa41b8f10c2bd449a6bd6c17c51bae9dfb92915f`,
fast-forwards through main's already released `5cd24eb15acae671127679e21aa5ce64afcb2fba`,
and merges these exact heads in order:

| PR | Head | Result |
| --- | --- | --- |
| [56](https://github.com/elischiffler/RoadtripsAreFun/pull/56) | `55cd1eec20da23bafcfbc1cc9387c4de861ee703` | Chat retirement and saved presentation JSON compatibility |
| [55](https://github.com/elischiffler/RoadtripsAreFun/pull/55) | `b52014581e28fdb28ab6f37df48475f3d0d9cd9a` | Standalone guided planning, saved trips, origin-local departure validation, two-day Studio default |
| [51](https://github.com/elischiffler/RoadtripsAreFun/pull/51) | `32b47624da9d4ee767e9ff96e6a76f17eee61c0c` | Bounded visit estimates, local arrival/leaving clocks, frozen offline captures and v5 active-time measurements |

All three merge without textual conflicts. The newer PR56 probe correction and
PR55's equivalent JSON assertions agree. PR51 retained three tests importing the
retired dispatcher. Those tests are replaced with 21 HTTP itinerary cases covering
all seven access holds at 15-minute, two-hour and six-hour visit lengths. Existing
direct reconstruction, saved duration, calendar, frozen-source and cache hold
regressions remain. No retired runtime modules are restored.

A GitHub audit of all 39 repository PR records found every merged commit and every
closed/superseded PR head already in the combined ancestry. The three open heads
above are included exactly. Old branches are not merged again simply to clear the
queue. This integration targets develop; production main and deployment settings
are unchanged.

## Studio display

`LabResults.jsx` now labels its third tab **Trip stats**. `TripStats.jsx` displays
recorded measurements as compact figures and independent horizontal bars:

- Delivered/requested, considered, usable and chosen attraction counts.
- Delivered and chosen match estimates, compared with the best available match.
- Direct versus final driving time, signed extra driving/distance and longest driving gap.
- Total planning time and attraction-selection time.

The section omits raw JSON, solver terminology, objective formulas and repeated
stage disclosures. Hotel details, per-place scores, provider counters and individual
stage timings are omitted from this summary. Route maps, itinerary views, errors,
saved history and backend measurement collection retain their contracts. Place
cards and popups omit Sources links and visit-estimate tags; numbered route-list
dots match the map colors instead of repeating stop/hotel labels. Source metadata,
the public attribution page and map-provider attribution remain. A previous
response is no longer retained solely for the removed replay comparison UI.

Missing measurements display a dash; measured zeros remain zeros. Historical
objective scores and eligibility thresholds are never reinterpreted as match
percentages. Chosen and delivered measurements remain distinct. Total wall time
and selection time remain separate measurements; nested/parallel timings are not
summed. Subsecond selection times display milliseconds. No chart dependency or
additional provider request is added.

### Minimal display verification, October 19

Frontend locked installation, formatting, lint, all **258 tests**, coverage
(**91.65% lines**, existing thresholds), and production build pass. The existing
bundle-size warning remains. Browser verification uses an already saved real
Studio trip: compact stats, colored route places and the shared itinerary retain
their measured values and times. No new provider trip is required for this UI
change. A temporary sample-event page verifies the actual loading component in
the browser and is removed afterward. Loading, retries, cancellation and
reconnect behavior are covered by controlled component/service tests. Backend
contracts and saved research data are unchanged.

The follow-up timing display uses compact Arrival/Leaving columns in both route
and itinerary cards. A shared short date/time zone appears once for same-day
visits; overnight dates and changed offsets appear beside their respective clocks.
Full dates, years, zones and offsets remain in accessible time labels and hover
text. Missing/invalid clocks remain unknown; historical explicit offsets do not
use the browser's local zone. Final destinations show only arrival. Saved times
and scheduling are unchanged. All **259 frontend tests**, coverage (**91.72%
lines**), formatting, lint and build pass. A temporary browser preview with sample
daytime, overnight and destination times is inspected and removed afterward.

## Local verification

- Node 24.12.0 / Python 3.12.14; locked `npm ci` and pinned backend requirements installed.
- Frontend format, lint, **250 tests**, coverage (**91.8% lines**, existing thresholds), and Vite build pass.
- Backend Ruff format/check and **1,785 tests, 128 skipped**, **79.01% coverage** pass against the existing 63% gate.
- Launcher: **5 tests** pass. Guarded Compose build/start and **2 container smoke tests** pass.
- Disposable real PostgreSQL CRUD, ownership, recreation, connection-loss recovery,
  backup/restore and refusal to restore into a populated database pass. Unique
  source/restore volumes and backups are preserved by the runner.
- Actual React components were inspected in the in-app browser at 1280px and
  320px using a temporary local sample-data page. No horizontal overflow or browser
  console errors; all numerical labels remain available as text. The temporary
  page was removed and viewport reset. This is synthetic UI verification, not
  live provider-trip acceptance.

Initial backend runs inherited a root dotenv CORS list missing `127.0.0.1:5173`.
A narrowed temporary test override also omitted preview/production test origins.
The successful full run uses the exact default allowlist explicitly, the
non-listening local database fixture and a non-listening local AI gateway. Root
`.env` and application CORS policy are unchanged. The pre-existing Vite bundle-size
and duplicate health operation-ID warnings remain. No thresholds are lowered.
Remote CI must be checked on the exact pushed develop SHA separately.

No live AI/provider trip, Cognito account journey, hosted database migration,
catalog activation or production deployment is part of this validation.
