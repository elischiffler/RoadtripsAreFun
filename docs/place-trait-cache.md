# Reusable attraction traits

Live attraction discovery reuses a small JSON object of estimated traits for each
source place. These are the same 14 canonical attributes already used by persona
matching: scenery, nature, hiking/outdoors, food, history, culture/arts, nightlife,
shopping, beaches/water, adventure, relaxation, unique local experiences, family
friendliness and crowd avoidance. Values remain numbers from 0 to 1.

Before this change, traits were retained inside saved trip explanations/results,
but a later live trip did not look them up. Run-local request deduplication did
not provide reuse across trips or API restarts.

## Lookup, estimation and scoring

`backend/app/routing/sources/trait_cache.py` supplies `get_many(places)` and
`put_many(entries, provider)`. The live attraction source reads the cache after
source identity and calendar eligibility checks. It sends only missing places to
the existing rating provider, validates complete 14-attribute responses, matches
their names to the supplied source records, and persists the successful estimates.
Same-name records are rated in separate requests so one name cannot conflate two
source identities. Supplied facts distinguish each place; traveler preferences
are not sent in the trait-rating prompt.

The cache contains traits, source context, rating-contract version, provider,
creation timestamp and expiry. It does **not** contain persona weights or a final
utility score. Each trip recomputes utility and per-attribute contributions with
`crossmatch(current_weights, cached_traits)`. A valid zero trait is not a missing
value. Unknown, incomplete, boolean, non-finite or out-of-range estimates are
never accepted as reusable traits.

The key hashes the stable source ID, name, coordinates, address, categories,
activities and description, plus the gateway identity and explicit rating-contract
version. Changed place facts or a version change cause a miss. Estimates expire
after 90 days. The served provider is retained, but the gateway does not expose
an exact model revision; a gateway model/prompt policy change should bump the
rating-contract version if immediate invalidation is needed. Expiry supplies a
bounded refresh even when the gateway changes independently.

Opening-hours evidence, entrances, availability, prices, dated room quotes,
visit-duration estimates and persona utility are separate. Reusing traits does
not waive any live source/calendar/road checks. Hotel ratings retain their
existing behavior. Historical and synthetic research candidates are not inserted
into the live attraction cache, and the active controlled CP-SAT batch is unchanged.

## Database and failure behavior

Explicitly apply `backend/sql/place_attribute_traits.sql`, then set backend-only
`PLACE_TRAITS_CACHE_ENABLED=true` for live reuse. Startup never creates schema.
The configured local Neon database has this additive table and local cache
opt-in; deployments default to disabled until explicitly configured. No immutable
catalog rows, account data or production application deployment is changed.

The application uses its existing PostgreSQL pool and honors the database write
gate. Writes are bounded transactions. The first valid unexpired writer wins;
concurrent trips re-read the canonical winner. Expired or invalid entries can be
refreshed. A database/cache failure falls back to fresh model estimates and does
not discard a valid generated result. Provider failures retain their existing
error/retry behavior. Cache access adds no new public endpoint.

Fresh/cached origin, provider, estimate timestamp and rating version accompany the
candidate's provenance. Discovery diagnostics include cache enabled state, hits,
misses and successful stores so later evaluations can distinguish reused traits
from newly generated estimates. Trait persistence reduces repeated rating calls;
other provider calls, including visit-duration estimates, may still be required.

## Verification

Tests cover reuse across two runs with different personas and different resulting
utility scores, generating only missing traits, distinct same-name source IDs,
rejecting unmatched AI names, fact/version invalidation, invalid JSON, database
failure, real PostgreSQL persistence, first-writer behavior, expiry refresh,
repairing an invalid stored entry and the write gate. The disposable PostgreSQL
workflow includes the real cache tests before its backup/recovery checks.

October 20 validation: backend Ruff formatting/lint and the full suite passed
(2,018 tests, 130 skipped, 80.45% coverage). The disposable PostgreSQL workflow
passed with six research/cache checks, including the real cache migration and
expiry/repair test. The additive migration was applied to the configured Neon
database over verified direct TLS and local live reuse was enabled. No provider
requests were made to seed estimates; the cache fills on live attraction searches.
