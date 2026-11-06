# Authentic 500-place pilot

This is the requested intake/acceptance plan for issue #36 and PR #40.
The [latest arrival review](catalog-arrival-review.md) validates a separate
72-arrival local bundle: one roadside, one entertainment, 12 nature, 12 beaches,
nine museums and 37 national parks across 24 states. It is 428 short of the roughly
500 target, with no dedicated landmark batch and no DC record. The original
400-record evaluation below is preserved for further review.
The [October 15 mixed-source pilot](catalog-mixed-pilot.md) now records 400
unique authentic **local evaluation** records across 30 states and DC. Of those,
69 have documented Boulder/NPS arrival evidence; current public-access/arrival
review remains incomplete for 331 Overture candidates. No production catalog
was loaded. Earlier archive findings remain in [source review](catalog-source-review.md).

## Selection targets

Aim for roughly 500 unique destinations after eligibility review and conservative
deduplication. These are planning allocations, not reasons to weaken admission
checks. Report a smaller accepted batch when evidence is insufficient. Assign
each destination one primary reporting category so these counts do not double
count; retain other supported labels for discovery.

| Primary reporting category                   | Working target |                  Local evaluation now |
| -------------------------------------------- | -------------: | ------------------------------------: |
| Niche/roadside stops                         |             80 |      1 in separate reviewed bundle |
| Entertainment destinations                   |             80 |                         56 candidates |
| Nature/scenic/trailhead destinations         |             90 |           33 (12 documented arrivals) |
| Beaches with public arrivals                 |             60 |                12 documented arrivals |
| Landmarks/public art/historic stops          |             70 |                         31 candidates |
| Museums                                      |             70 |       231 (8 documented NPS arrivals) |
| National parks with verified public arrivals |             50 |                37 documented arrivals |
| **Total unique destinations**                |        **500** | **400 local; 69 documented arrivals** |

The 100-record total shortfall does not describe category balance: museums are
overrepresented while roadside intake is limited to one documented venue. Candidate counts are not
production eligibility claims. See the mixed-pilot receipt for every state gap.

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

The original Overture pipeline and atomic generation operations remain intact.
Explicit source adapters now cover reviewed Boulder trailheads, Kaggle NPS park
identities enriched with official facility arrivals, official beach parking and
the explicit Kaggle/LOC Corn Palace roadside profile.
The bounded mixed-generation assembler re-admits original child artifacts and
retains separate source identity, release, licensing and attribution. The
Overture combiner remains source-specific. See [implementation and real local
proof](catalog-mixed-pilot.md); these capabilities do not clear unresolved data.

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
This document itself grants no deployment, merge, capacity, credential or
destructive-change authority; the active user instructions govern authorization.
Production recovery/data gates remain necessary within that authorized scope.

An activated nonempty catalog and green unit tests do not establish live flow.
Validate saved account trips and Studio, daytime/evening discovery, Mapbox arrival
and detour checks, selected-stop scheduling, maps, saved-history reload,
attribution and explicit sparse-coverage behavior. PR #40 is ready for code
review; review status does not clear production acceptance gates. The Vercel preview alone is
not that evidence.
