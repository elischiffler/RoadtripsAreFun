# Authentic 500-place pilot

This is the requested intake/acceptance plan for issue #36 and draft PR #40.
It contains no place records and approves no source. As of the fresh October 14
saved-environment recheck, the authenticated small Kaggle download was blocked by
proxy CONNECT 403; **zero authentic records have been acquired, accepted, staged
or activated**. All category/state coverage is currently missing. See
[access/validation evidence](catalog-validation.md) and the
[six-source review queue](catalog-source-review.md).

## Selection targets

Aim for roughly 500 unique destinations after eligibility review and conservative
deduplication. These are planning allocations, not reasons to weaken admission
checks. Report a smaller accepted batch when evidence is insufficient. Assign
each destination one primary reporting category so these counts do not double
count; retain other supported labels for discovery.

| Primary reporting category | Working target | Accepted now |
| --- | ---: | ---: |
| Niche/roadside stops | 80 | 0 |
| Entertainment destinations | 80 | 0 |
| Nature/scenic/trailhead destinations | 90 | 0 |
| Beaches with public arrivals | 60 | 0 |
| Landmarks/public art/historic stops | 70 | 0 |
| Museums | 70 | 0 |
| National parks with verified public arrivals | 50 | 0 |
| **Total unique destinations** | **500** | **0** |

Spread accepted destinations across Northeast, Southeast, Midwest, Mountain and
Pacific states, with Alaska and Hawaii explicitly represented or reported as
gaps. Include urban, rural and interstate-adjacent stops; identify actual useful
route clusters rather than implying that 500 scattered points provide national
coverage. Report every state/DC with zero accepted records. Territories remain
outside the existing US scope. Avoid letting the Boulder regional input or
multiple rides inside one theme park dominate the batch. Food/nightlife coverage
is a separate evening-flow requirement; this daytime allocation does not claim
to meet it.

## Evidence to retain outside Git

For each source, retain the original archive, exact Kaggle owner/slug and version,
retrieval timestamp, bytes/checksum, dataset metadata/README, original-source URL,
license/notice evidence and attribution. Record the actual inspected columns and
field mappings, filters, scanned/accepted/rejected counts and reasons. Use bounded
local extraction; do not send raw dumps, photographs, reviews or descriptions of
unresolved rights to Neon. If the file cannot be downloaded within approved bounds,
stop and revise acquisition explicitly rather than quietly increasing limits.

For each accepted destination, retain native source IDs and all contributing
source/version references, a factual name, explicit US state/DC, supported
category, verified practical WGS84 arrival point and point type (public entrance,
parking, trailhead or visitor facility). Keep the coordinate source and evidence
URL/date distinct from the original dataset date. Preserve dated operator or
official current-operation/public-access evidence, limitations and seasonal
restrictions; an old listing or valid coordinate is insufficient. Unknown opening
hours stay unknown. Do not assert future availability from an evidence date.

Natural-area centroids are not arrivals. Museum administrative addresses are not
automatically public venues. Collapse rides into park destinations only when
stable venue identity is established. Compare native IDs, normalized names,
addresses, websites and distances; inspect uncertain matches instead of merging
by name/proximity alone. Multiple useful entrances must not inflate destination
counts. Keep a cross-source mapping when a destination has more than one source.

## Implementation and validation still required

The existing pipeline is Overture-only:

- `backend/app/catalog/ingest.py` validates an official pinned Overture URL/release
  and an explicit Overture upstream allowlist.
- `backend/app/catalog/normalize.py` expects Overture fields and rejects generic
  natural-area centers. Kaggle evidence must not be disguised as Overture fields.
- `scripts/catalog_combine.py` combines only matching Overture releases/schemas;
  it is not a cross-source merge command.
- `backend/app/catalog/repository.py` currently emits `overture:` identities and
  source labels; the public attribution page describes only approved Overture
  upstreams.

After an authentic archive and its rights are reviewed, implement an explicit
adapter for its actual schema. Preserve source-specific stable identities,
version/attribution and independent access/operation evidence through staging,
discovery, itinerary/Studio output and backup/restore. Test that closed/uncertain
records, coordinate-less rows, raw park centers, unsupported rights and unresolved
deduplication are rejected. Do not add an adapter that fabricates missing source
facts or uses a blanket Kaggle permission rule. No candidate is cleared by this
plan; unresolved rights pause that candidate's import.

Validate the resulting bounded artifact in isolated PostgreSQL 18, including
idempotent staging, atomic activation/rollback, exact source/content counts,
attribution, indexed footprint and restore. Publish category/source/state counts
plus duplicates/rejects, gaps and sampled arrival/current-operation evidence.
Only then follow the existing [Neon rollout gates](neon-places-catalog.md), using
the existing authorized target and preserving application data and generations.
No production deployment, merge, paid capacity, credential configuration or
destructive import is authorized by this plan.

An activated nonempty catalog and green unit tests do not establish live flow.
Validate authenticated chat and Studio, daytime/evening discovery, Mapbox arrival
and detour checks, selected-stop scheduling, maps, saved-history reload,
attribution and explicit sparse-coverage behavior. Keep PR #40 draft until real
data and those acceptance results can be reviewed. The Vercel preview alone is
not that evidence.
