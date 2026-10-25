# Paper completion handoff: uncapped bell-shaped corridor

Use only this folder's completed schema-v4 study,
`514e8250-12c7-4a22-bd2d-e550523fc7dc`, measured at `dc231e1` on
`codex/real-data-research` (RoadtripsAreFun PR #57, target develop).
The previous schema-v3 point-search results and cancelled full-trip campaign
are superseded and must not be pooled with this study.

The user explicitly removed full trip planning from research and replaced
sampled/capped candidate discovery with a purely logical distance rule around
the initial route. They then requested a bell-shaped corridor that is wider in
the middle and narrower at the endpoints. The implementation defaults to five
miles at endpoints and 25 at midpoint, with normalized Gaussian sigma 0.25.
Every admitted daytime place is checked against the full polyline. AI estimates
attributes only; it does not choose which identities enter the geographic pool.

## Verified paper corrections

All paths below are relative to the repository; line references describe dc231e1.

| Claim | Correct treatment | Code evidence |
| --- | --- | --- |
| Fourteen preference attributes | Normalize all 14 weights; utility is their weighted sum of estimated ratings. This is estimated match, not measured satisfaction. | `backend/app/agent/persona.py:10`, `:49`; `backend/app/routing/profiles.py:54` |
| 60 or 100 research candidates | No count cap. Four geographic pools contain 10, 11, 10 and 24 real places; eligible pools are 10, 11, 10 and 23. Ordinary app discovery still has its existing cap; do not claim the production planner was changed to this research protocol. | `backend/app/catalog/repository.py:334`; `backend/app/research/design.py`; `backend/app/routing/cp_sat_selection.py:239` |
| Candidate preparation | One active immutable catalog snapshot (602 admitted daytime records), full-polyline projection, deterministic bell-shaped membership. There are 36 distinct places across overlapping pools. | `backend/app/routing/corridor.py:37`, `:73`, `:97` |
| Route midpoint and progress | Corridor width uses fraction of polyline distance; model spacing continues to use baseline driving-time progress. Neither is an actual visit arrival time. | `backend/app/routing/corridor.py:73`; `backend/app/routing/geometry.py:RouteMeasure` |
| AI provenance | All geographic matches must have valid stored traits with actual upstream model identity; requests are batched but never truncate the pool. Campaign stored 15 missing trait entries; audit verified all 36 distinct inputs against the database. | `backend/app/research/corridor_inputs.py:26`; `backend/app/routing/sources/trait_cache.py` |
| Matched experiment inputs | Four measured route preparations are reused across 24 scenarios; persona scores are recomputed. Candidate identities/attributes/roads stay fixed across stop counts, settings and seeds. | `backend/app/research/preparation.py:52`; `backend/app/research/evidence.py` |
| Exact stop count | Select K=min(requested, eligible). All revised scenarios fulfill requested counts; this is not itinerary completion. | `backend/app/routing/cp_sat_selection.py:170` |
| Quality allowance | Protect selected mean >= top-K mean minus epsilon; epsilon 0.10 is an absolute allowance, not a relative 10% reduction. Utility is a constraint, not the directly maximized objective. | `backend/app/routing/cp_sat_selection.py:148`, `:157` |
| Spacing/detours | Minimize total absolute K+1 baseline-gap deviation plus weighted summed solo detours. Solo detour=max(0, measured origin–place–destination duration minus baseline); raw signed differences are retained. | `backend/app/routing/cp_sat_selection.py:197`, `:213`; `backend/app/routing/planners/cp_sat.py:162` |
| Five seconds, three seeds | Replace with 15 seconds, one worker and 30 seeds (0–29). Seven distinct one-factor configurations, 24 scenarios, 5,040 trials. | `backend/app/research/design.py`; `backend/app/routing/cp_sat_selection.py:20` |
| Integer scaling / zero tolerance | Utility scale is 1,000,000; floor utility coefficients, conservatively ceil the required total. Zero tolerance can cause rounding infeasibility generally, but it did not occur in this study. | `backend/app/routing/cp_sat_selection.py:148`, `:289` |
| Budget / full-trip outcomes | Remove them from the evaluation, its metrics and results. No hotel costs, final-route driving, itinerary completion, trip-duration or full-pipeline timing were measured. Downstream app modules may remain as system context, clearly unevaluated. | `backend/app/research/collect.py`; `backend/app/research/metrics.py` |
| Fixed two-hour visits | Not an input to this selection-only study. Ordinary app duration estimation and calendar-aware scheduling are separate; do not present a fixed two-hour visit assumption as measured here. | `backend/app/research/collect.py`; `backend/app/routing/sources/visit_durations.py` |
| Results versus planned counts | All 5,040 trials are verified OPTIMAL, 0 failed or missing; 720 baseline trials. PostgreSQL has all 5,064 completed queue items. | `summary.json`; `case-results.csv`; `input-audit.json` |

## Supported results and interpretation

Baseline eligible-pool mean: **0.4034354002**. Selected mean:
**0.5296371528**. Gain: **0.1262017526**, or **12.6202 percentage points**.
These equally weight scenarios/runs. Twenty-two baseline scenarios improve mean
utility and two decrease it; both decreases are on SF–Denver at nine requested
stops. A lower mean is compatible with the spacing/detour objective and allowed
utility loss. All 132 requested stops across a complete scenario pass are selected.

All 24 baseline groups choose the same identities for every seed. Three of the
168 scenario/configuration groups have more than one optimal selection; the
other 165 are invariant. Seeds are computational repeats, not independent users
or independent place samples. Do not infer statistical significance from 5,040
repeated trials alone.

Mean solver time: **10.3315 ms**, median **2.001 ms**, range **0.290–242.078 ms**.
Mean trial wall time: **43.7680 ms**, median **28.8718 ms**, range
**14.0511–310.7533 ms**. Wall time additionally includes capture-hash validation
and model preparation. Hardware: Apple M4 Pro, 12 logical CPUs, 24 GiB RAM,
Python 3.12.14, OR-Tools 9.10.4067; one solver worker. The 15-second limit was
not approached. These small real pools do not establish large-instance scaling.

Read README.md and summary.json for every variant and matched contrast. The
zero-loss setting has higher selected utility but worse mean spacing and solo
detours; allowing 0.20 loss trades utility for lower model costs. Detour weights
shift those costs without a monotonic selected-utility guarantee.

The chosen corridor widths are not empirically optimized. Catalog coverage,
admission rules, AI estimates and four routes/two fixed personas limit
external validity. The one excluded candidate, `nps-heritage:edis`, fails the
source-calendar validity check; source facts remain preserved. Date-specific
opening windows and full trip feasibility were not evaluated.

## Writing and Word document

Continue in the existing chat **Outline trip-planning research paper**, using
its `/workspace/write-like-me/SKILL.md` and its established document workflow.
The verified current paper target from that chat is:
https://cpslo-my.sharepoint.com/personal/dfrishbe_calpoly_edu/_layouts/15/Doc.aspx?sourcedoc=%7BA3F0235B-5023-4DC1-B404-8EEEEB102E25%7D
(Final Report.docx). A separate ambient tab once showed another document; do not
switch targets silently. Read the current paper before editing.

Finish the existing paper's Evaluation, Results, Discussion/Limitations and
Conclusion. Update earlier method claims to match this study. Preserve the user's
simple, direct first-person student style, 6–12 pages, no abstract, Aptos 12-point
black body text, existing headings, Plain Table 3, and native editable equations.
Do not restore removed pseudocode/path-spacing equations automatically. Use past
tense only for completed work. Preserve accurate existing references; verify any
new citations instead of inventing them.

Use candidate-selected-utility.png and utility-gain-heatmap.png (SVG versions are
also included), with truthful captions and denominators. The corridor diagram is
`docs/research/route-corridor.png`. Keep figures readable and fit the page budget;
a compact variant table may replace redundant prose/figures. Return the final
Word view link and a concise account of actual edits and any blockers.
