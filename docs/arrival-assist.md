# Arrival assist

The reconciled feature is documented in [Foreground automatic arrivals](foreground-arrivals.md).
It uses one tracker/UI from the preserved `1554b2b` and `1d58445` source histories.
See that document for the current stricter confidence policy, explicit pause/restart,
arrival-event metadata, Undo suppression, route-edit reset and verification limits.

The initial `1554b2b` checkpoint passed 495 frontend tests, a final 29-test focused
run and mocked-position Chromium checks. Those are historical checkpoint results;
the reconciled candidate requires its own verification and the final integrated
signed API/PostgreSQL release gate. It must not be described as live GPS, native
or production acceptance.
