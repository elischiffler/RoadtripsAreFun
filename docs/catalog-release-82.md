# Bounded catalog release candidate — October 15, 2026

The release candidate has **82 unique places across 36 states**, covering all
seven requested primary categories: roadside 1, entertainment 1, nature 12,
beaches 12, landmarks 11, museums 9 and national parks 36. It is **418 short**
of the approximate 500 target; coverage remains sparse and has no food/nightlife
batch. It does not establish nationwide route coverage. Empty areas must remain
explicitly empty, with no Tripadvisor fallback.

The [aggregate receipt](evidence/catalog-release-82-20261015.json) records source,
state and category counts, original evidence fingerprints, immutable generation,
authentic local activation/rollback and exact restore. The earlier 400-record
evaluation and all 72-place bundles remain intact. This candidate supersedes
their current-eligibility claims; it does not rewrite their historical receipts.

## Eligibility corrections and heritage arrivals

An audit found active published seasonal/renovation closure exceptions at six
previous NPS facilities. The new Kaggle NPS manifest explicitly enables dated
closure exclusion. Four parent parks retain one destination each through actual
alternative facilities: Badlands uses Ben Reifel Visitor Center; Denali uses
Murie Science and Learning Center; Redwood uses Thomas H. Kuchel Visitor Center;
Voyageurs uses Rainy Lake Visitor Center. Kenai Fjords and Yellowstone have no
passing current facility in the inspected snapshots and are withheld. This does
not assert that those entire parks are closed. No replacement coordinate is
guessed, and alternative facilities do not increase destination counts.

The new `nps-heritage-arrivals/1` source adds 12 government-published visitor
arrivals, including the National Prisoner of War Museum and 11 heritage-unit
landmarks. Original NPS facility coordinates, explicit facility states, listed
auto parking, current public schedules and directions are required. The public
NPS map inventory supplies native identity/designation only: its geometry and
cartographic state labels are never used for arrivals or facility jurisdiction.
Every admitted point passed a driving **destination** check within 75 metres;
Antietam's `NoSegment` result is withheld. These checks do not promise parking
availability, future hours or access to every feature of a site.

The shared facility parser keeps government-only provenance separate from Kaggle
identity provenance and never labels a heritage unit as a national park. It
rejects boolean/nonfinite coordinates, unknown jurisdiction, missing parking,
restricted driving, closure evidence and unresolved duplicate native facilities.
Known remote information-office substitutions are excluded. Dated-closure checks
conservatively handle recurring cross-year periods and ambiguous dated closures;
they do not implement holiday or future operating-hours prediction.

Only the first inspected, verified heritage batch enters this release. Additional
downloaded candidate snapshots remain outside it. No photographs, descriptive
prose, source-page dumps, publisher browser keys, user data or credentials enter
the catalog or repository.

## Validation and rollout boundary

Generation: `cfdb55a51fe8abfe015fcbb12b8d23c7a09fa71945d95758bd00756ec502ada0`.
The candidate revalidates original source artifacts and hash-pinned sidecars
under the existing 500-place / 20 MiB pilot bounds: 17,373,539 inspected bytes.
The custom local dump is 37,998 bytes, SHA-256
`52b816ba913d094fc5ebffd5f39bff7dfac309aed38501b1bcb087debd3be522`.
An empty separate PostgreSQL 18 database restored all three tables, exact content
digests and active pointer. Existing 72-place and 400-record databases are
unchanged. Actual legacy/persona discovery returns `nps-heritage:arpo`; culture
discovery returns Wing Luke's native Overture ID, with zero HTTP/Tripadvisor calls.

Full backend validation passes **957 tests, 88.03% coverage**, including five real
PostgreSQL cases, above the unchanged 63% floor. An existing wall-clock concurrency
test failed under simultaneous validation load; its isolated recheck and the full
quiet rerun passed without changing its 30% threshold. Frontend format/lint,
314 tests and build pass. Exact final-head CI and review remain separate gates.

A guarded staging transaction was compiled from the admitted original-source
recipe and rehearsed in another empty local PostgreSQL 18 database. It creates
only the checked-in additive catalog schema, locks catalog mutation, enforces
storage/count/immutable-content checks, and inserts these public records without
activation or updates to existing rows. Idempotence, altered-content refusal and
storage-ceiling refusal passed; all 82 stored records exactly match admission.
Its JSON statement-list SHA-256 is
`c1d35b3e3ceefc83eb692ee0421236f1ec162cfac8dd6ebac1eaef577f0a7422`.
The original-source recipe, transaction and archives remain outside Git.

The fresh pre-change host backup and isolated exact-object restore were confirmed
privately. No private backup data is copied here. Apply the staged rollout and
rollback gates in [the runbook](neon-places-catalog.md): staging, explicit activation,
checked-main release and actual production acceptance are distinct steps. The
independent acceptance worker must receive the actual deployed frontend/backend
revisions and active generation. Local validation is not production proof.
