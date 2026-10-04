# Location suggestions and confirmation validation

October 3, 2026 (America/Los_Angeles), on the shared CP-SAT feature lineage.

The reproduced conversation supplies SLO/Boulder, October 10, 10 AM, two stops
and a hotel budget, then corrects both locations to full city/state wording.
The previous recorder treated multiple matches as unresolved, lost the supplied
date, and placed choices outside the fixed chat panel. The new flow proposes an
exact provider address, requires an explicit owner/chat-scoped selection, keeps
alternative matches and date wording, and renders confirmations inside the log.

- PASS: Python 3.12, Ruff 0.16.7 format/lint; 597 tests, 85.44% backend coverage
  against the unchanged 63% requirement. New cases cover single-match consent,
  corrected multi-match suggestions, city-before-county query matching, stable
  choice IDs, retained date/time, request-time-relative dates in two timezones,
  invalid-date correction and origin changes without inheriting an old date.
- PASS: Node 24, npm ci, format/lint, 172 frontend tests with coverage thresholds,
  Vite build. Reload tests require the confirmation buttons to be inside the
  chat log and verify suggested and alternative selection payloads. The existing
  large-bundle build warning remains.
- PASS: isolated container preview and two container smoke tests. Disposable
  PostgreSQL verifies owner separation, pending departure wording/reference/time,
  recreation, outage recovery, backup/restore and populated-target refusal.
  Source/restore volumes and private backups remain preserved for
  `roadtrips-crud-4f85f25ebf`; test containers are stopped.
- CONFIRMED by read-only inspection of the existing local browser: the original
  SLO correction returned San Luis Obispo County, San Luis Obispo city and
  California City, and the destination returned Boulder city and county.
- PENDING: GitHub Actions on the delivered head. Full live model/provider,
  confirmation persistence/reload and complete-trip acceptance remain separate
  from fixture tests and disposable PostgreSQL evidence.

No dependencies, database migration, cloud resources or production deployment
are added. Existing confirmed trips remain compatible. Dates discarded by the
older implementation must be supplied again; the fix cannot recover them from
the old profile. The separate chat-update 404/create fallback is unchanged.
