# Permanent attraction ratings

Each source place has one reusable, persona-independent profile of the 14
canonical attraction attributes. The first persisted rating is retained. Adding
places, changing prompts/models, editing metadata, restarting the application or
repeating a study does not regenerate an existing place's ratings. Corrections
require explicit user direction and an audited data repair.

The attributes are AI estimates, not proof of objective or unbiased quality.
Traveler preferences are excluded from the rating prompt. `crossmatch` applies
those preferences to the stored profile deterministically: a nature traveler and
an entertainment traveler can have different utilities for the same place, but
unchanged preferences and ratings always produce the same utility.

## Storage and lookup

`backend/app/routing/sources/trait_cache.py` looks up the earliest persisted row
by stable `source_id`, including historical context-hashed rows. Legacy expiry
is ignored. New rows have an identity-only key and infinite expiry. Model,
rubric, source facts and rating timestamp remain provenance, not invalidation
triggers. No database migration is needed for this behavior.

Concurrent writes take a transaction-scoped advisory lock per source identity,
then check for an existing rating. The first stored profile wins; callers re-read
that profile. Writes never automatically replace expired, invalid or changed
ratings. Corrupt records and database outages fail closed instead of silently
asking AI for replacements or using unpersisted estimates.

Explicitly apply `backend/sql/place_attribute_traits.sql`, then enable
`PLACE_TRAITS_CACHE_ENABLED=true` for live attraction reuse. Research always
requires the persistent store. The configured local database is enabled; this
change does not deploy the application or change other deployments' settings.
Offline fixture providers remain independent of this live store.

Opening hours, road access, availability and visit-duration estimates remain
separate checks. Hotel behavior is unchanged. Stored ratings do not establish
that a destination is open or reachable.

## October 24 restoration

The nature refresh incorrectly regenerated all 36 existing places under a new
rubric. At the user's direction, every changed row was restored to its original
14 attributes and original model/version/timestamp/context provenance. The three
new CDFW destinations retain their first ratings. A complete 75-row pre-change
backup and exact database readback are preserved privately. The historical
research exports retain the values actually used; they must not be silently
rewritten to imply the restored ratings were used in those experiments.

Regression checks cover stable lookup across metadata/version/expiry changes,
legacy keys, concurrent first writers, corruption and storage failures, and zero
AI rating calls on repeated discovery or a failed lookup.
