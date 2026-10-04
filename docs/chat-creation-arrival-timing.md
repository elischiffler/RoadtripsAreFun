# Chat creation and final arrival

New authenticated trips await server creation before the first agent turn or
snapshot PUT. `DatabaseUtils.jsx` owns a shared creation promise per account's
`ChatLogs` instance and integer chat ID. Panel remounts share the promise; token
refresh for the same issuer/subject retains ready rows. Restored server rows are
already ready. Clearing user data releases the lifecycle; deletion clears its
ready entry. The backend still verifies ownership, and agent memory keeps its
separate UUID identity.

Creation happens when the traveler first submits. Failed creation retains the
input and invites another send to retry, without an agent request or PUT. Startup
waits for saved rows before choosing the new integer ID. Failed reads expose a
reload retry instead of allocating an ID that might overwrite a saved row.
Loading bubbles remain excluded from persistence. Pending trips remain hidden
from search until the existing route-ready callback exposes them. PUT's 404
recovery remains for genuinely stale rows, rather than ordinary chat creation.

`SchedulingPolicy.arrival_cutoff(final=True)` owns final destination timing for
both CP-SAT estimates and final Mapbox duration validation. Without late driving,
the default destination limit is **21:00 arrival-local time**, while hotels and
two-hour attraction visits retain **20:00**. This accepts the reported Boulder
arrival at **2026-10-19 20:30:38.484 -06:00** without enabling late driving. A
destination reached after the ordinary hotel cutoff carries a late-arrival
warning. Estimates can still differ from actual rerouted legs; actual validation
remains authoritative.

Optional `latest_destination_arrival` records an explicit final-arrival or
stop-driving deadline. It can narrow the default window; values later than 21:00
require explicit `late_driving` to take effect. Earlier hotel limits also
conservatively narrow the destination window. With explicit late driving, the
existing late cutoff (at most midnight) applies, bounded by any explicit
destination deadline. Extraction and saved-detail receipts expose the new
preference. Default `null` preserves existing saved late-driving policies.

Elapsed duration, IANA timezone/DST rules, booking nights and morning restart
are unchanged. A final route outside the bound explains the local deadline and
available replanning choices; completion preserves that explanation without
wrapping it as an invalid argument. No migration, dependency, production
deployment or provider call is introduced.

## Validation on October 4, 2026

- PASS: Node 24 `npm ci`, frontend formatting, lint, 186 coverage tests and build.
  Existing large-bundle warning remains.
- PASS: Python 3.12, pinned Ruff 0.16.7 checks, 619 backend tests and 85.57%
  coverage. An existing heartbeat ordering
  test failed during parallel application checks and passed in the serial full
  rerun; no thresholds/timeouts were changed.
- PASS: isolated browser/API fixture, including delayed creation, forced 503,
  retained input/retry, startup, New trip and restored-chat reload. Observed
  POST completion -> agent -> PUT; restored chat -> agent -> PUT. No initial
  PUT 404 or JavaScript page errors. Fixture uses no hosted data or providers.
- BLOCKED locally: container smoke (8002/8082 refused connections) and disposable
  PostgreSQL (Docker Linux engine unavailable). Remote CI results are recorded
  separately on PR #26.
- BLOCKED: live Cognito/model/provider journey and real-trip acceptance. Fixture
  timing establishes policy behavior, not a new live Tampa-Boulder route.

The existing PR stays draft. The user approves merges.
