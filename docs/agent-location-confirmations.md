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

This does not establish that a geocoder's first result matches the user's
intent. Bare abbreviations such as `SLO` can resolve to an airport rather than
the intended city. A separate improvement should introduce candidate selection
or traveler confirmation before an ambiguous match becomes routable, shared
by chat and the direct location API. Until then, use a full city and state or
address to correct a bad match. Correcting the start invalidates the old
timezone-dependent departure date, which must be supplied again.

Regression coverage uses fake model/geocoder responses for canonical origin
and destination receipts, failed updates, subsequent turns, complete schema
serialization, and refreshed tool continuation state. Live model behavior and
real abbreviation resolution require separate provider acceptance.
