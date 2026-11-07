# Foreground arrival assist

Arrival assist is off until the traveler chooses **Enable location and mark
nearby stops visited** and grants the browser location permission. It detects a
conservative arrival at the next unvisited attraction and automatically uses the
existing presentation-only saved-visit operation. Detected arrival is visible;
Undo and the existing manual visit buttons remain available. A detected arrival
means proximity, not proof of entrance, admission or a completed visit.

The location watch runs only in a visible page. Stop, hiding/leaving the page,
unmount, changing account/session or route, denied/unavailable location and
unsaved/conflicted visit state clear it. Completing the last eligible attraction
also stops the watch. Returning to the page requires explicit opt-in again. A
browser page does not provide native/background tracking or Apple Live Activities.

## Conservative defaults

- Only the next unvisited, nonoptional attraction arrival is eligible. Meals,
  hotels, departure/destination entries and optional suggestions are excluded.
- Its itinerary provider identity and arrival timestamp must match exactly one
  route stop with valid coordinates and aware arrival/departure timestamps.
  Legacy or ambiguous trips retain manual visits.
- A fix must be no older than 15 seconds, no more than two seconds in the future,
  and strictly newer than the preceding fix. Repeated/invalid fixes reset dwell.
- Accuracy must be at most 50 meters. Distance plus reported accuracy must fit
  inside a 150-meter radius. A reported speed above 2.5 m/s is rejected; missing
  speed is allowed only with the same sustained dwell guards.
- At least 45 seconds of fresh samples, on both reception and acquisition clocks,
  are required, with gaps at most 15 seconds and drift at most 50 meters from the
  first sample. A gap, stale/inaccurate/moving fix or pending write resets dwell.
- After an automatic arrival, stationary fixes cannot cascade through co-located
  or adjacent identities. A fresh accurate fix must place the traveler confidently
  outside the preceding stop's 200-meter departure boundary before a new 150-meter
  arrival dwell can begin. Nearby separate attractions may require manual visits.
- Detection is limited to the period from the later of 15 minutes before trip
  departure or one hour before the attraction's planned arrival, through six hours
  after its planned departure. Trips on another planned day cannot be completed
  merely because the device is near their coordinates. Large schedule changes
  and delays use manual visits or a new plan.

These thresholds are conservative product assumptions, not measured GPS quality
or a guarantee of attendance. Source waypoint quality and device/browser location
accuracy still matter. The browser may deny permission or suspend updates; see the
[Geolocation specification](https://www.w3.org/TR/geolocation/) and
[watchPosition requirements](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition).

## Storage and conflicts

Raw coordinates, accuracy, speed, timestamps and dwell samples exist only in the
watch controller's memory. They are never added to trip JSON, account memory,
analytics, requests or a sharing projection. Stopping drops that controller.
Only existing stable visited-stop IDs are sent through the account-scoped,
revision-checked presentation update. The normal returned revision supports later
visits and Undo. A save failure stays visibly unsaved with the existing explicit
retry; a stale 409 stops assistance and requires loading the current trip. It is
never automatically replayed or used to recreate a deleted trip. Undo stops
arrival checks to prevent immediate redetection.

## Verification

Focused service/UI tests cover fresh and repeated/stale/inaccurate/moving fixes,
time windows, coordinate/timing ambiguity, co-located/adjacent-stop departure,
automatic save/undo, permission/unavailable/insecure contexts, failed save versus
stale conflict, and hide/account/route/unmount cleanup. Existing manual visit
tests remain unchanged.

`tests/arrival-assist/browser.mjs` runs actual Chromium against a test-only React
harness. Positions, identity and the persistence HTTP response are synthetic; it
checks automatic save, the returned revision on Undo, denied-location manual
fallback, stale-save stop, and 390px/1440px layout. It makes no real geolocation,
Cognito, API, database or provider request. The separate mandatory guided journey
remains the real signed-verifier/API/scheduler/disposable-PostgreSQL release gate.
Physical-device GPS, permission policy, battery use and native/background behavior
require separate acceptance; these tests do not claim that evidence.


Local verification on November 7, 2026: the full offline frontend suite passed
495 tests across 63 files with existing coverage thresholds. After adding the
explicit two-stop React lifecycle regression, the final focused service/UI/manual
visit run passed 29 tests. Chromium also passed the two co-located arrivals with
one continuing watch, no stationary cascade, successive actual client revision
updates and Undo (visited counts 1 → 2 → 1), denied-location manual fallback,
stale-save stop and 390px/1440px layout. Browser page errors and blocked external
origins were empty. Format, lint and production build passed. The final wording
clarifies that this app does not save/share location; browser/OS location-provider
behavior remains outside that claim. No actual geolocation or provider requests
were used. Ignored evidence is under `tests/arrival-assist/.artifacts/`; final
integration must still run the mandatory real API/PostgreSQL gate.
