# Stage 2 onboarding integration

Based on develop `614de8d68d26ffb35261e3084b8733b6bb6e0366`.

## Delivered

`/plan` remains the actual responsive app, with its landing-page introduction and
numbered navigation replaced by accessible percentage progress. Back, review
edits, owner-scoped drafts, errors and focus movement remain supported.

Place comparisons are optional disclosure content. The comparison profile stays
hidden; preference blending and API payloads are unchanged. Native interest sliders
support touch, pointer and arrow keys; their amounts remain relative weights.

Car collection is removed from onboarding. New drafts skip car input; older
unanswered drafts migrate without losing other answers. Existing provided car
values survive. Coordinate car editing with the trip-settings worker: this patch
does not implement that editor.

The early estimate displays returned route geometry and matched addresses, with
editable start/destination text fields above it. Endpoint changes abort and clear
the old estimate. Ambiguous provider results require explicit selection. Existing
service validation rejects unusable geometry and preserves drafts on failure.

Spacing, depth and transitions use existing tokens. Reduced-motion users receive
no entering/press animation. Natural document scrolling remains available for
expanded details, large text and short screens.

## Remaining integration and acceptance

- Driving time excludes stops, visits and meals. It cannot establish a complete
  candidate under 12 hours. The structured API has no explicit one-day/skip-hotels
  contract. Complete-candidate evidence and an explicit one-day choice require
  coordinated planning work before hiding hotel inputs or skipping hotels.
- Extraction from one free-text trip description is not added. Existing explicit
  start/destination text fields and confirmed provider matches remain authoritative.
- The requested Apple design skill was absent from local files and available skill
  catalogs. This patch uses repository tokens and does not claim skill review.
- Browser visual acceptance remains outstanding. `/plan` can be inspected directly
  in DevTools device mode; a separate mobile-only URL is not added.
- No production, database or live Mentro calls were made. Release remains with the
  parent, after integration, review and complete-trip acceptance.
