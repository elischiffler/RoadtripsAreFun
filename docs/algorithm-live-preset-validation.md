# Live preset validation — October 5, 2026

Task base: `c1164d2` (`codex/lab-trip-evaluation`). Changes are on
`codex/lab-live-presets-results`. No public application deployment is included.

## Repairs

- Updated the unresolvable local Mentro Fly hostname to the documented gateway,
  `https://api.mentro.elischiffler.dev`, retaining existing authentication.
- Attraction ratings use the live provider's verified nearby names. Identity,
  radius, utility threshold and candidate caps remain authoritative. Terra
  returned other categories despite its attraction filter; the adapter requires
  an attraction listing URL before adding a result to the attraction pool.
- Corrected Google Hotels' stay-selector flags after comparing an actual guest
  selector URL with the generated token. A live lookup confirmed both children
  (ages 7 and 12) and six verified hotel quotes. Dates, occupancy, currency,
  price and location verification remain enforced.
- Idle database recovery discards the stale pooled connection and checks out its
  replacement through the pool. Untracked replacements previously caused
  `PoolError` on return, making history unavailable.
- Removed the benchmark button and batch/repeat modal. All nine profiles remain
  in the Trip presets modal; individual runs stay live-only.
- New finalized runs save route geometry/stops and itinerary. The owner-scoped
  result endpoint backs a View map and itinerary popup, without another run.
  Older records without a stored route have no viewer button.

## Storage and verification

Inspected the connected table before changing it. Tested the additive result
column migration twice in disposable PostgreSQL, then applied only that column
to the user-connected Neon table. Existing records are preserved. This does
not verify the full production schema or migration history.

Frontend format, lint, coverage thresholds and build passed; the existing Vite
large-bundle warning remains. Backend format, lint and coverage passed.
Disposable PostgreSQL passed CRUD/owner isolation, saved-result persistence,
recreation, loss/recovery, backup/restore and populated-target refusal. A
terminated idle connection exercised pool recovery. Source/restore volumes and
backups are preserved. Guarded preview container smoke passed both tests.

## Live outcomes

Acceptance uses the actual authenticated browser, connected Neon and live
providers. Unit/disposable fixtures do not substitute for these runs. Completion
means the route and itinerary pipeline finished. Attraction counts are caps;
hotel budgets are advisory. Missing stops and over-target quotes remain visible.
