# Trip detail lists

The backend owns collection receipts and missing-detail questions. Agent replies
with validated trip changes, pending location choices, explicit trip-summary or
collection requests, or a route/itinerary tool outcome carry an optional
`presentation` alongside a readable `reply` fallback. Other conversation keeps
the model's natural answer. Model-originated follow-up requests also carry lists,
including on unchanged/no-tool turns.

`presentation.updated` contains user-facing text derived from differences between
the persisted profile before and after the turn. Unchanged fields and failed or
pending location changes are omitted. Canonical saved addresses are copied
exactly. Departure receipts include the backend-resolved year, time, UTC offset
and saved IANA timezone. A successful `complete_trip` or explicit summary shows
the full saved list with the title **Trip details**; ordinary changes use
**Updated trip details**.

`presentation.needed` contains at most two questions, prioritizing backend
validation and pending location choices. Collection, prompt stage selection and
the completion tool share `TripProfile.missing_details()`. Skipping the optional
car satisfies its choice requirement; an unanswered car does not. Required-question text does
not depend on model prose or frontend defaults. Car choice is one question,
separate from independently requested year, make and model values.

`presentation.notes` carries tool failures, route budget warnings, incomplete
itinerary recovery and model-outage notices. A complete-trip success is required
for the whole-trip readiness message. The structured actions still own route and
itinerary updates. No routing, provider, extraction or location-selection policy
changes are introduced by the formatter.

The frontend renders escaped text with native headings, `ul` and `li` elements.
Malformed presentations and old messages fall back to text. The existing
one-line animated process status is unchanged. Mobile messages use the available
column width and wrap long addresses.

## Storage and compatibility

The same optional presentation model is accepted by the existing `ChatLogSchema`.
ChatLog remains JSONB; no database migration is required. Both JSON and NDJSON
return the same final response. Each successful reply is persisted even without
trip-data actions. Message updates also update the persistence reference before
saving, so React batching cannot omit the current reply.

Older clients can display `reply`; newer clients can load older plain messages.
Backend validation and authenticated, explicit location confirmation remain
authoritative. Pending candidates retain the existing choice buttons and restore
through the same saved trip profile.

## Verification

Deterministic fixtures replay Boulder to Marceline, 10 AM, a 2023 Mazda CX-5, six
attractions, $200/night and November 21. They cover corrections, invalid fields,
unchanged values, optional-car choices, exact addresses, a noncompliant prose
model, provider outages, completion and partial/failure outcomes, and JSON/NDJSON
parity. A completion test runs the real tool dispatcher with controlled provider
fixtures. Frontend tests cover native lists, escaping, legacy messages, immediate
persistence and restored lists/choices.

The disposable PostgreSQL probe stores a presentation through `ChatLogSchema` and
checks it in new processes after recreation and backup/restore. It uses only the
checked-in local DDL. Production schema and live model/provider acceptance remain
unverified.

Run the commands in `AGENTS.md`. Container smoke tests also accept
`ROADTRIPS_SMOKE_API` and `ROADTRIPS_SMOKE_WEB` for an isolated preview on alternate
ports; the preview's CORS origin and frontend build URL must match those values.
Defaults retain the runbook's ports 8002 and 8082.

## One information request per item

Final model answers use a small internal JSON envelope: `introduction` and
`requests` (each with a canonical `field` and `question`). This is presentation
intent, not extraction or authorization. Required asks are filtered against the
saved profile using the shared collection-field helper and rewritten with the
backend question text. Saved values are not requested again. Vehicle values each
have a separate item; at most two total questions are displayed.

Optional scheduling clocks, late-driving choice and evening interests render in
`presentation.questions` under **Questions**. They use single-field backend
wording and never add required fields, change saved defaults or block planning.
`presentation.introduction` appears before the lists. These optional additions
have defaults, so older saved presentations still load. Plain `reply` includes
newline-separated bullets for both required and optional asks.

A model that still returns prose on an otherwise unstructured turn gets one
bounded formatting call through the existing provider, with no tools. Its usage
is included in turn totals. Malformed formatting or provider failure returns
saved-state questions and a retry notice, rather than raw JSON or a clumped
paragraph. Ordinary answers with no requests remain prose. The formatting
classifier and introduction still depend on model interpretation; fixtures do
not establish live provider compliance. No new provider is introduced.

Before: “What time would you like to depart? Would you provide a car, including
year, make and model, or skip?” After, within one bubble:

- What time would you like to leave? You can choose 9:00 AM.
- Optional car: would you like to provide a car for this trip, or skip it?

Controlled regression coverage includes unchanged turns, paragraph-model
normalization, separate date/time and vehicle values, saved-field suppression,
optional follow-ups, malformed fallback, JSON/NDJSON parity and persisted reload.
Desktop 1280px and mobile 390px component previews show native separate items,
natural wrapping and no horizontal overflow or duplicated fallback text. Real
PostgreSQL recreation and backup/restore preserve the added sections. Full live
model/Cognito/provider acceptance remains unverified; keep PR #26 draft.
