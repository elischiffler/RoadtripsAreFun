# Attraction eligibility and AI rating validation

Valid catalog places with neutral or specialized interest vectors could disappear
because discovery and selection each required an absolute utility of at least
0.60. Equal weights average fourteen distinct interests, so a nature specialist
can score below that threshold despite being the best available match.

Discovery and selection now share one policy: retain finite utility greater than
zero and at most one. Scores are not inflated or filled with defaults. The solver
still fills only the available requested count, keeps average match within ten
percentage points of the best achievable average, and minimizes spacing/detour
cost. Source identity, road verification, visit/hotel scheduling and final timing
validation remain authoritative. The policy is saved in diagnostics and comparison
fingerprints; historical run thresholds retain their original meaning.

Catalog facts supply identity, coordinates, categories and provenance. AI supplies
estimated ratings for all fourteen canonical attributes, each numeric in [0,1].
Missing fields, booleans, nonfinite/out-of-range values and unmatched place names
are not accepted as usable ratings. Each rating batch records parse/validation
counts, missing sources and name-match status without retaining raw model output.
When a batch has no usable matching rating, it gets at most one format repair
request. Existing transient transport retries remain bounded separately. If no
batch produces usable ratings, planning raises INVALID_ATTRIBUTE_RATINGS rather
than presenting the source pool as empty; the routing HTTP endpoint returns a safe
502. Partially usable batches retain valid source matches and report the omissions.

The offline regression uses twelve authentic CC0 Boulder arrivals re-admitted
from the retained source archive and official arrival evidence. Neutral complete
vectors and nature-specialist complete vectors pass discovery and permit two
selections under controlled route/detour fixtures, with original scores and place
facts unchanged. Complete zero vectors, absent catalog coverage and malformed AI
output remain distinguishable. These controlled AI vectors and route timings are
test inputs, not observations of a live model or real driving feasibility.

This fix cannot create geographic coverage. A separate read-only production
diagnosis found three recent runs with zero raw places at all saved five-mile
samples; their nearest stored place was over thirty miles away. The user's exact
failing route remains unconfirmed. The 214-place expansion stays paused, and no
coordinates, operating hours, prices, public access or rights evidence are invented.
