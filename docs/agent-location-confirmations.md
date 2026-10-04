# Saved location confirmations

The chat model receives the complete `TripProfile` JSON, including missing
fields and the start timezone, after backend extraction and validation on
every turn. After a tool batch, the loop replaces that snapshot with freshly
loaded state before the next model request. The schema owns the serialized
structure; the prompt no longer maintains a separate list of profile fields.

When a location is successfully recorded, the backend prefixes the reply with
the exact persisted address, for example `Saved starting location:
Salem-Leckrone Airport, Salem, Marion County, Illinois, United States of
America.` This confirmation also survives a reply-provider outage. Failed
location updates do not confirm the previously saved address as a new save.
Unchanged locations are available in later model context without repeating
the receipt on unrelated turns.

The model is instructed to copy canonical address values exactly when naming
saved locations and to ask for a correction when they conflict with the
traveler's intent. This is guidance for model prose; the backend-generated
confirmation is deterministic.

## Suggested addresses and explicit confirmation

The chat resolver accepts nonblank location wording, including abbreviations,
city names and full addresses, and requests multiple OpenCage results. It keeps
at most five valid, deduplicated candidates. Results whose leading address words
match the supplied query come first; other matches retain provider order. Thus
San Luis Obispo, California precedes San Luis Obispo County for a full city/state
query, without discarding the county alternative. The first result
is a **suggested address**, not a claim that the traveler intended that place.
Every new endpoint requires an explicit selection, even when there is only one
match. No confidence threshold or requirement to type a full street address
blocks a usable suggestion. Failed lookups ask for a correction and never
invent coordinates.

The recorder saves searches in `TripProfile.pending_locations`, including empty
candidates after a failed lookup. Previously confirmed endpoints stay intact
until selection, but all agent route/itinerary tools reject pending endpoints.
Valid sibling details remain saved. Repeating the same pending query preserves
its choice IDs; repeating a confirmed canonical address does not reopen it.
Changing the query invalidates the old IDs even if the new lookup fails.

Confirmation cards live **inside the scrollable chat log**, after the latest
reply. Each shows the exact suggested address and a labeled Confirm button;
additional provider matches are available under Choose another match. Travelers
can also type a correction. These cards must not be outside the fixed chat box,
which would cover them. The deterministic reply names the suggested address,
rather than repeatedly asking for more specific wording.

A click posts `locationConfirmation` with `field` and `candidateId`. Only this
authenticated owner's chat memory supplies the address, coordinates and timezone.
There is no model-callable confirmation tool. Expired or foreign choices are
rejected; a free-form `yes` never selects a candidate. The confirmation needs no
model inference or additional geocode. Changed endpoints clear the displayed old
route and itinerary; completion uses saved coordinates without re-geocoding.

`TripProfile.pending_departure` retains supplied departure wording and its UTC
request instant while the origin is pending. The chosen local time is retained
separately. Confirming the start resolves that wording in the selected IANA
timezone, using the original request instant for tomorrow and yearless dates.
The result must still be in the future. Invalid dates, DST ambiguities and missing
timezones ask for clarification without discarding the selected location or
other valid details. Changing an origin without supplying a new date still
clears the previous canonical departure; no date is silently copied from an old
trip. Dates already lost by an older server must be supplied again.

Pending locations and departure wording persist through the existing `ChatData`
and agent-memory JSON. The frontend snapshot is advisory; confirmation always
checks authoritative memory. No database schema migration is required. Existing
trips remain readable and previously confirmed addresses are not retroactively
made pending.

The authenticated direct `/validate-location` API shares the same resolution
policy. One unambiguous match keeps the existing success shape. Ambiguity
returns HTTP 409 with `detail.code=location_confirmation_required`, the query,
and bounded candidates; callers must ask for a clarified address or make an
explicit coordinate selection. Existing non-trip reverse geocoding and hotel
verification keep their existing helper behavior.

Regression coverage uses fake model/geocoder responses for single and multiple
address suggestions, query stability, date retention and original-date anchoring,
canonical origin
and destination receipts, failed updates, subsequent turns, complete schema
serialization, refreshed tool continuation state, pending guards, ownership,
stale selections and timezone/date invalidation. Frontend tests cover choice
buttons, explicit request payloads and reload restoration. The disposable
PostgreSQL test persists pending IDs through recreation and backup/restore.
Live model behavior and real abbreviation resolution require separate provider
acceptance. Fake tests do not prove that OpenCage will return San Luis Obispo
for `SLO`; the correction path is essential when only the airport is returned.
