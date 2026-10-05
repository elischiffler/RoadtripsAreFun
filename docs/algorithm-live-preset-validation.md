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
- Guest confirmation compares child ages irrespective of display order while
  retaining each age and duplicate count. Contradictory occupancy still fails.
- Preserved the actual guest selector's applied-filter parameters (`qs`, `ap`).
  Reno reset children without them despite a valid stay token; a direct live
  lookup with them verified ages 7/12 on search and detail pages and returned
  five dated, independently verified hotel quotes.
- CP-SAT keeps the hotel search band equal to the per-room nightly target on
  every night. Subtracting previous nights from that target produced a negative
  price range and crashed long trips. Actual over-target costs and warnings are
  retained; a multi-night regression covers this case.
- The family example restarts at 07:30 instead of 08:00. Its verified final
  reroute arrived three minutes past the 19:00 cutoff with the original example;
  the earlier restart leaves margin while preserving the arrival deadline.
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
large-bundle warning remains. Final frontend suite: 279 tests, 88.2% line
coverage. Backend format/lint passed; 677 tests passed with 86.83% coverage
(required threshold remains 63%).
Disposable PostgreSQL passed CRUD/owner isolation, saved-result persistence,
recreation, loss/recovery, backup/restore and populated-target refusal. A
terminated idle connection exercised pool recovery. Source/restore volumes and
backups are preserved. Guarded preview container smoke passed both tests.

## Live outcomes

Acceptance uses the actual authenticated browser, connected Neon and live
providers. Unit/disposable fixtures do not substitute for these runs. Completion
means the route and itinerary pipeline finished. Attraction counts are caps;
hotel budgets are advisory. Missing stops and over-target quotes remain visible.

| Preset | Outcome | Attractions / cap | Itinerary days | Overnights | Quoted room-night total |
| --- | --- | --- | --- | --- | --- |
| Coastal nature | Completed | 2 / 2 | 1 | 0 | $0 |
| Same corridor, culture | Completed | 2 / 2 | 1 | 0 | $0 |
| Overnight road trip | Completed | 0 / 3 | 1 | 0 | $0 |
| Short single-day | Completed | 2 / 2 | 1 | 0 | $0 |
| Medium two-day | Completed | 4 / 4 | 2 | 1 | $151 |
| Long multi-day | Completed | 1 / 8 | 4 | 3 | $706 (six independently quoted rooms) |
| Dense corridor | Completed | 0 / 4 | 1 | 0 | $0 |
| Sparse corridor | Completed | 2 / 3 | 1 | 0 | $0 |
| Tight hotel budget | Completed | 4 / 4 | 2 | 1 | $125 |

All completed rows above have stored geometry and itinerary and zero measured
schedule violations. Tight-budget's single room quote exceeds its $60 target by
$65; the warning remains visible. Long and dense runs did not fill their caps;
completion does not mean all requested attractions were selected. Original
failure records remain in history, so the all-time completion rate includes them.

Final acceptance: all nine latest preset runs completed through live route and
itinerary construction. The browser's View map and itinerary button was exercised
for every preset, loading both saved map and itinerary without rerunning providers.
The overnight-labeled example did not actually require a hotel with its observed
selection and drive duration; its label is not a guarantee of an overnight.
