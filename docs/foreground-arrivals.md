# Foreground automatic arrivals

**Enable location and mark nearby stops visited** is an explicit, in-memory opt-in
for the mounted saved-trip/itinerary view. Browser permission alone never starts
a watch. The next eligible attraction is automatically marked after a qualifying
arrival; the UI shows the detection and offers immediate Undo. **Correct an
arrival** exposes the existing manual mark/undo fallback. An arrival is a
conservative proximity estimate, not proof of entry, admission or a completed visit.

One canonical implementation owns acquisition (`foregroundArrivals.js`), pure
detection/events (`tripArrivals.js`) and UI (`TripArrivalTracking.jsx`). No second
tracker/watch runs. Stop, page exit, unmount, account or route change, permission
failure and unsaved/conflicted updates clear it. Hiding the page clears the watch
and pending dwell and explicitly pauses assistance; returning never silently
restarts it. Enable it again to continue. Finishing all eligible attractions also
stops acquisition. There is no background, screen-lock, service-worker, native or
Apple Live Activity behavior.

## Confidence and identity

Only nonoptional attraction arrival rows (`type:stop`, `kind:arrival`) are eligible.
Provider identity and aware arrival timestamp must match exactly one route stop
with valid coordinates and aware arrival/departure timing. Missing, ambiguous or
undated physical attractions leave the trip manual; there is no name-only,
geometry, stop-order or direct-itinerary-coordinate inference. Hotels, destination,
departure, meals and optional evening ideas are excluded from automatic recording.
The detector advances only to the next unvisited, nonsuppressed attraction.

Defaults combine the stricter guards from both arrival implementations:

- Freshness at most 10 seconds, no future timestamp, strictly increasing fixes;
  invalid, duplicate or out-of-order fixes reset evidence.
- Reported accuracy at most 35 meters; distance plus that accuracy must fit a
  100-meter radius. Both reported and inferred speed must be at most 2.5 m/s.
  Invalid/negative reported speed is rejected; unknown speed still needs dwell.
- At least 60 seconds on both acquisition and receipt clocks, at least four
  distinct fixes, gaps at most 15 seconds and drift at most 50 meters from the
  dwell anchor. Movement, bad fixes or a pending write break the dwell. A lost
  fix changes the visible status after 10 seconds; the next fix rechecks gaps.
- Resolve the closest physical target before exclusion. If the distance gap
  between the closest two is at most twice reported accuracy, do not choose:
  the uncertainty circle can cross their midpoint. Co-located identities,
  repeated visits or shared entrances remain manual.
- After any automatic arrival, another target cannot cascade from stationary
  fixes. A fresh accurate fix must be confidently beyond the prior stop's
  200-meter departure boundary before the next arrival dwell can start.
  This departure latch survives ordinary presentation saves and next-target
  rerenders; true route/account changes stop the watch instead.
- Detection starts no earlier than the later of 15 minutes before trip departure
  or one hour before planned attraction arrival, and ends six hours after planned
  departure from that attraction. A future trip cannot be completed merely by
  standing near its coordinates. Large delays require manual correction/replanning.

These are conservative defaults, not field-validated GPS certainty. The browser
may deny or suspend location; source waypoint quality, nearby traffic, large sites
and GPS jitter remain limitations. See the [Geolocation specification](https://www.w3.org/TR/geolocation/)
and [watchPosition requirements](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition).

## Privacy, persistence and edit compatibility

Raw coordinates, accuracy samples, speed, fix timestamps and dwell anchors exist
only in the watch controller's memory. They are never logged, sent to providers,
added to the map or persisted as a user trail. Stopping drops that controller.
The opt-in copy discloses that only stop identity, detected arrival time and
aggregate detection quality are saved to the account. This does not claim the
browser/OS location provider itself operates entirely on device.

`presentation.arrivals` holds at most one latest versioned event per existing
stable itinerary stop ID, alongside existing `visitedStopIds`:

```json
{
  "schemaVersion": 1,
  "type": "trip.stop.arrived",
  "eventId": "<tripId>:<stopId>:<occurredAt>",
  "tripId": 42,
  "stopId": "<existing itinerary visit ID>",
  "occurredAt": "2026-11-07T12:01:00.000Z",
  "source": "web-foreground",
  "dwellSeconds": 60,
  "accuracyMeters": 10
}
```

The event constructor allowlists fields, never copies the fix, and records worst
qualifying accuracy rounded up. Manual corrections use `source:manual` and the
time of correction without quality fields; that time is not a measured arrival.
Applying an event to an already visited stop is idempotent. Undo removes the event
and suppresses automatic recording of that stop until manually marked again.
Immediate Undo also stops the active watch. Unknown presentation fields and old
visited-only trips remain compatible.

Recording uses the existing account/session-scoped presentation-only CAS save.
A successful response updates the revision for the next arrival and Undo. A save
failure remains visibly local and offers the existing explicit retry, with
tracking off; a stale conflict requires reload and is never automatically
replayed or used to recreate a deleted trip. Route-edit previews/saves clear old
visited IDs, arrival events and undo exclusions on both client and backend while
preserving unrelated presentation data. Saved itinerary IDs change with timing,
day and place edits. Future native adapters must respect current itinerary and
storage revisions; this event shape alone implements no native permission,
background location, ActivityKit, notification or synchronization contract.

## Reconciled verification

Both source histories are retained. Original service, lifecycle, UI/manual,
persistence and browser cases were migrated to the single implementation:

| Earlier cases | Combined verification |
| --- | --- |
| Fresh/duplicate/stale/future/inaccurate fixes, speed, distance, drift and time | `arrivalConfidence.test.js`, `tripArrivals.test.js` |
| Co-located and uncertainty-midpoint ambiguity, repeated identities | `tripArrivals.test.js`; mocked-position browser ambiguous case |
| Save/rerender continuity and departure/re-entry latch | `ArrivalConfidence.test.jsx`; browser successive actual-client revisions |
| Consent, denial, timeout, stale callbacks, hide, account, route and unmount | `foregroundArrivals.test.js`, `TripArrivalTracking.test.jsx`, `ArrivalConfidence.test.jsx` |
| Versioned event allowlist, idempotence, manual correction and suppression | `tripArrivals.test.js`, `TripArrivalTracking.test.jsx` |
| Visit save/failure/retry/conflict, reload and route-edit resets | Existing manual/reload/edit and backend persistence regressions, augmented from the parent branch |

The earlier 45-second dwell/150-meter radius and parent 20-second gap expectations
are tightened, not preserved as alternate runtime policies. Earlier legacy
name/direct-coordinate and automatic-on-return expectations now explicitly test
manual fallback and explicit restart. Exact co-located stops remain ambiguous;
an adjacent unambiguous two-stop browser journey tests the departure latch.

The Chromium harness uses mocked positions, synthetic identity and intercepted
persistence replies while exercising the real React UI and revision-aware client.
It never calls real geolocation, Cognito, an API/database or planning provider.
The mandatory signed browser/API/scheduler/disposable-PostgreSQL journey remains
required on the final integrated release candidate. Physical-device GPS and native
acceptance remain separate evidence.


Reconciliation verification on November 7, 2026: **523 frontend tests passed in
66 files**, with unchanged coverage thresholds (92.79% statements and 87.68%
branches). The final focused eight-suite run passed **69 tests**, and the existing
backend saved-trip persistence suite passed **27 tests**. Format, lint and the
production Vite build passed. Independent peer review found no source blocker.

The final mocked-position Chromium journey passed automatic save, one continuing
watch through save/revision/next-target rerenders, no stationary cascade to an
adjacent target, departure/re-entry plus a new dwell, exact co-located ambiguity,
updated-revision Undo, denied-location manual fallback, stale conflict without
replay and 390px/1440px layout. Arrival metadata uses only the event allowlist;
no raw position fields enter persistence. Browser page errors and external
requests were empty. Ignored evidence is in `tests/arrival-assist/.artifacts/`.
A leftover local harness occupied the default port on the first launch, which
failed before reaching the new UI. The final run used an explicit bounded
loopback port; the checked-in harness permits no alternative remote host. Its
PTY-owned server was stopped afterward. None of these checks is live geolocation,
Cognito, provider, native or production acceptance. The integrated exact-commit
mandatory API/PostgreSQL journey and release CI remain required.
