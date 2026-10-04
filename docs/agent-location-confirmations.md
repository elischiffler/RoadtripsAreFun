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

## Ambiguous location choices

The shared resolver requests multiple OpenCage results and presents at most
five valid, deduplicated candidates. Multiple distinct candidates require a
choice. A bare two- or three-letter abbreviation such as `SLO` or `LA` requires
confirmation even when the provider returns one result. A single valid result
for other wording can be saved directly. Provider confidence measures precision,
so it is not used as proof of relevance. This conservative policy may request
confirmation even when the traveler considers a city obvious.

The recorder saves unresolved searches in `TripProfile.pending_locations`.
This includes empty candidates after a failed lookup, so a failed revision
cannot silently reuse the old origin for a new trip. Valid sibling details
remain saved. Old confirmed endpoints remain intact until a new selection or
unambiguous correction succeeds, while all agent route/itinerary tools reject
pending locations. The agent responds with a deterministic choice prompt;
free-form `yes` never chooses a candidate. Location extraction is instructed to
preserve abbreviations exactly.

Chat shows exact candidate addresses as buttons and offers a full city/state
or address correction when none match. A click posts `locationConfirmation`
with `field` and `candidateId`; addresses, coordinates and timezones are loaded
only from this authenticated owner's chat memory. There is no model-callable
confirmation tool. New searches replace the opaque IDs; old or foreign choices
are rejected. Selection does not need inference or another geocode. Confirming
the start clears the old departure date but keeps the selected local time;
the traveler supplies the date again. Confirming the destination asks the
traveler to continue planning. Changed endpoints clear the displayed old route
and itinerary. Completion uses the stored coordinates without re-geocoding.

The pending profile is also saved in the existing `ChatData` JSON so buttons
survive reloads. This UI snapshot is advisory; confirmation always checks
authoritative agent memory. No database schema migration is required. Existing
trips remain readable; previously misresolved locations are not automatically
corrected and need a new full-address request.

The authenticated direct `/validate-location` API shares the same resolution
policy. One unambiguous match keeps the existing success shape. Ambiguity
returns HTTP 409 with `detail.code=location_confirmation_required`, the query,
and bounded candidates; callers must ask for a clarified address or make an
explicit coordinate selection. Existing non-trip reverse geocoding and hotel
verification keep their existing helper behavior.

Regression coverage uses fake model/geocoder responses for canonical origin
and destination receipts, failed updates, subsequent turns, complete schema
serialization, refreshed tool continuation state, pending guards, ownership,
stale selections and timezone/date invalidation. Frontend tests cover choice
buttons, explicit request payloads and reload restoration. The disposable
PostgreSQL test persists pending IDs through recreation and backup/restore.
Live model behavior and real abbreviation resolution require separate provider
acceptance. Fake tests do not prove that OpenCage will return San Luis Obispo
for `SLO`; the correction path is essential when only the airport is returned.
