# Retrospective release audit and Mac integration

These files are derived audit metadata, not original operator bodies or an
importable catalog. `README.export.md`, `audit-summary.json` and
`per-record-audit.json` preserve selected original export documents unchanged;
their historical sidecar-only statements describe the exported cloud commits.
The complete audit archive, including its original checksum manifest and detail
files, is preserved privately in the Mac transfer directory.

The current integration enforces the exact 133-ID sidecar at
`backend/app/catalog/release_holds.json`, pinned by its adjacent Python module.
`mac-integration.json` records distinct batch hashes, counts and unresolved release
requirements. See [integration behavior](../../catalog-cloud-integration-20261022.md).
No new production rows, itinerary qualifications or source approvals are granted.
