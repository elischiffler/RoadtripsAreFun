# Current study: original ratings with added nature destinations

Study **cffa789a-bd7c-4ec0-8be0-8223e1cff9bc** replaces the withdrawn re-rated
study `d0aee85d-bd6a-49c3-a74a-c5b5630549bf`. It ran October 24, 2026,
23:41:03–23:45:38 UTC from clean source
`af4f00e82c2b42300b9730efbf53eeb3d616acc8`, source hash
`5090a5b74057783f4f8ee15ff1e8112cb3e34f8987481e0c1d38038d01c5b4b4`.

## Fixed place ratings

At the user's direction, all **36 previously re-rated places** were restored
exactly to their original 14 attributes, provider, rating version, timestamp and
source context. The **three new reserves retain their first ratings**. The live
75-row table was backed up before restoration, and every restored value was
checked after commit. Stable source-identity lookup now ignores metadata/model/
prompt changes and legacy expiry. Database failures and corrupt stored ratings
stop estimation instead of requesting replacements. The subsequent live-discovery
guard in `eef029b` also refuses a disabled persistent store; it does not change
research selection or the inputs used here.

Every captured profile matches its original or first profile: **39 distinct
places, zero AI rating calls, zero rating misses and zero rating writes** during
this campaign. Traveler weights never enter the AI trait prompt. Utility is the
deterministic weighted sum of each place's stored attributes. Different personas
can have different utility for a place without altering its stored profile.

These are fixed, persona-independent **AI estimates**, not independently verified
or guaranteed unbiased quality measurements. Preserving original values also
preserves their limitations: the old market ratings have not been corrected or
recalibrated. The 36 old profiles retain the v2 model-provenance contract; the
three new profiles retain their first v3 destination-rubric estimates. This is
not a claim that all places were newly rated under one uniform rubric.

## Protocol

The design matches the earlier corridor and withdrawn nature studies: four routes,
two personas, 1/2/3 stops per day, seven settings, thirty seeds, fifteen seconds
per solve and one solver worker. Every admitted catalog place inside the initial
route's full bell-shaped corridor is considered, without a count cap. Width is
5 miles at endpoints and 25 miles at the midpoint, sigma 0.25.

Four fresh route preparations are reused across 24 captures and 5,040 trials.
The catalog still has 611 places and 192 calendars, including the three reviewed
CDFW trail accesses. Captured pools contain 13, 11, 10 and 24 places. Eligibility
is evaluated separately; the coast-to-coast historical laboratory destination
with unknown hours remains excluded. This evaluates attraction selection only:
no full-trip planning, hotel, scheduling or financial evaluation is performed.

## Results

**All 5,040 solver trials are OPTIMAL**, including all **720 baseline trials**.
Baseline selected mean utility is **0.571269**, compared with eligible-pool mean
**0.403046**, a **+16.8223 percentage-point** difference across equally represented
scenarios. All requested counts are fulfilled. Twenty-two baseline scenarios
improve over their pools; the three-stops/day SF–Denver cases are negative for
nature (−0.2528 points) and entertainment (−1.5056 points). The objective optimizes
spacing and solo detours within the quality bound; it does not maximize utility.

| Short single-day case | 1 stop | 2 stops | 3 stops |
| --- | ---: | ---: | ---: |
| Nature selected mean | 68.50% | 69.00% | 69.00% |
| Entertainment selected mean | 57.00% | 58.75% | 58.00% |

Nature selects Upper Newport Bay for one stop, Upper Newport Bay and Batiquitos
Lagoon for two, and all three reviewed reserves for three. Entertainment selects
Oceanside Farmers' Market for one, Orange Home Grown and Oceanside for two, and
Downey CFM plus those two for three. **All twelve Entertainment baseline scenario
means equal the original corridor study**, before the global re-rating. The
restoration does not change the solver to favor one persona.

All 24 baseline scenarios select the same sets across their 30 seeds. Repeated
seeds on fixed pools are not independent place samples or travelers. The old-to-new
nature comparison also changes catalog coverage and recaptures driving inputs;
it is not an isolated estimate of an algorithm improvement. The historical
300 zero-loss failures under the withdrawn v3 ratings remain preserved in that
packet. No solver rounding fix was made; those failures do not occur with the
restored inputs in this campaign.

Baseline mean solver time is 9.461 ms; complete trial wall time is 43.739 ms.
These are descriptive measurements on the same M4 Pro (12 logical CPUs, 24 GiB),
Python 3.12.14 and OR-Tools 9.10.4067. Development and verification work shared the
host, so these are not isolated performance benchmarks. Small regional pools do
not establish nationwide nature coverage or hundred-candidate scaling.

## Evidence

- [Restoration receipt](ratings-restoration.json) and [fixed place profiles](place-ratings.json)
- [Capture-level rating verification and original-study comparison](ratings-verification.json)
- [Exact database/export comparison](database-verification.json)
- [All case results](case-results.csv) and [summary](summary.json)
- [Reproducible analysis](analyze_export.py)
- [Candidate versus selected utility](candidate-selected-utility.png) ([SVG](candidate-selected-utility.svg))
- [Utility-change heatmap](utility-gain-heatmap.png) ([SVG](utility-gain-heatmap.svg))

Historical exports are retained without rewriting their observed data. Only this
replacement study is the current Research/paper dataset.
