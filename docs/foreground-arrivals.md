# Foreground arrivals (Stage 2)

## User flow and limits

The saved trip and itinerary views offer **Enable automatic arrivals** before
requesting browser location permission. Opt-in is in memory for this mounted
view only, not persisted or inherited by another trip/account/tab. Browser
permission alone never starts tracking. **Turn off automatic arrivals** clears
the watch. Navigation, page exit, sign-out, permission failure and component
teardown also clear it. Hiding the tab clears the watch and pending dwell;
returning to the visible page starts a fresh dwell only while that view remains
opted in. There is no background, locked-screen, service worker or Live Activity
tracking. Map and editor navigation ends this first web version's tracking.

A recorded arrival is a conservative proximity estimate, not proof of a visit.
Only fresh (at most 10 seconds old), monotonic fixes with reported accuracy of
35 meters or better qualify. The reported accuracy circle must fit inside a
100-meter radius of the stop. A full 60 seconds, at least four distinct samples,
no sample gap over 20 seconds, and observed/reported speed at or below 2.5 m/s
are required. Leaving, poor fixes, movement, hidden pages, route changes, save
blocking and errors break the dwell. A 10-second stale indicator removes a
misleading live status. The next sample also rechecks freshness/gaps. GPS jitter,
traffic near a venue, approximate coordinates and large sites remain limitations;
thresholds are conservative defaults, not field-validated certainty.

The detector uses existing itinerary visit IDs and [latitude, longitude] stop
coordinates. Historical itineraries omit coordinates, so it resolves exact
provider/stop identities (or a full legacy arrival name/type/address tuple) from
the saved route. It rejects ambiguous coordinates and never guesses from
Mapbox geometry, route order, geocoding or a venue name alone. Optional evening
suggestions can resolve from their saved route records. Meal windows and paired
departures do not become targets. Stops without usable coordinates remain
manual. Neighboring venues require correction when their distance difference is no
more than twice the reported accuracy, including rivals just outside the dwell
radius; the uncertainty circle could cross the midpoint between them. Colocated
venues and repeat visits at the same coordinates are ambiguous, including shared
entrances; use the manual fallback for those visits in this version.

**Correct an arrival** exposes the existing manual mark/undo controls. Undo
removes that arrival record and suppresses automatic detection for the stop
until manually marked again, preventing it immediately reappearing while the
user remains nearby. Existing visited IDs and unknown presentation fields stay
compatible. Schedule time alone never creates an arrival.

## Privacy, saving and concurrency

No raw user positions are persisted, logged, added to the map, sent to a provider
or saved to the account. The detector holds only the immediately previous fix
and current dwell in memory. Stops are not shared live. Only arrival metadata
is stored in the existing authenticated trip presentation JSON, alongside
`visitedStopIds`; no endpoint, migration or permission change is added. The existing backend
route-update path now clears arrival metadata and undo overrides with visited
IDs, preserving unrelated presentation fields after an itinerary change.
Destination coordinates already present in itinerary IDs are not a user GPS trail.

Arrivals reuse the existing owner/session-scoped, revision-checked presentation
save path. Processing serializes behind a save. Errors leave the result local,
stop tracking and offer retry of the same snapshot. Conflicts require reload
instead of overwriting newer route/progress data. An unsaved update is labeled
as such. Retrying successfully resumes a still-enabled view with a fresh dwell.
Raw positions never enter the save payload. Changing accounts invalidates late
location callbacks and save completions; browser watch generations also reject
callbacks from hidden, replaced or stopped watches.

## Native integration contract

`services/tripArrivals.js` separates position acquisition, pure detection and
arrival event creation. The `presentation.arrivals` dictionary keeps the latest
record per existing stable itinerary stop ID; it is not an unbounded event log.
A web automatic arrival has this versioned shape:

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

`accuracyMeters` is the worst reported accuracy during the qualifying dwell,
rounded up. Manual corrections use `source: "manual"`, the time of correction,
and omit measurement fields. Consumers must not interpret a manual timestamp
as a measured physical arrival. Applying an event for an already visited stop
is idempotent. `automaticArrivalExcludedStopIds` represents manual undo; removing
a record/visited ID must remove it from any future Live Activity projection too.
Existing stop IDs intentionally change when the itinerary's day/time/place
identity changes. Native clients must reconcile against the current itinerary
revision and discard obsolete IDs, not treat them as permanent catalog IDs.

A future native adapter can reuse the domain shape and owner/revision rules,
with a separately reviewed `source: "ios-native"` acquisition contract. Native
location permissions, background modes, ActivityKit/Live Activity updates,
notification delivery, ETA/routing, authentication and device synchronization
are not implemented here. Do not infer any of them from this event shape. The
web event is an internal save object, not a broadcast or public event bus.

## Verification

Focused offline Vitest suites cover the detector, coordinate resolution,
monotonic/stale/malformed/poor fixes, drive-bys and inferred speed, gaps,
ambiguous/repeated stops, idempotent saves, undo suppression, opt-in/denial/retry,
visibility, sign-out, route replacement, stale callbacks, save failure and
conflict. Geolocation is synthetic; tests do not grant OS location permission,
contact Mentro or any live location/provider endpoint. The signed guided journey
continues testing actual visit save/undo through **Correct an arrival**.

Frontend aggregate checks and exact results belong in the task handoff. Real
outdoor GPS/permission behavior and iOS background/native support remain
unverified. Production release still requires the repository's complete signed
journey and release-owner gates.
