# Historical study: nature coverage and destination-specific ratings

**Withdrawn as the current paper dataset:** the user directed restoration of all original place ratings. This packet preserves the re-rated experiment as historical evidence only. See [restoration and current results](../2026-10-24-restored/README.md).

Study **d0aee85d-bd6a-49c3-a74a-c5b5630549bf** replaces
`514e8250-12c7-4a22-bd2d-e550523fc7dc` as the current paper dataset. It ran
2026-10-24 23:03:24–23:07:58 UTC against clean commit
`e2d0bf8ed2861c3ca09f45c40f00cc283c866c9c`, source hash
`50360c9b05160e1e56fdc5400bbef998a4484a414ad8431a8c7cd6c18d22fdbf`.
All 5,064 case records match the PostgreSQL results mirror. The prior study was
removed from the active local and PostgreSQL stores after a verified recovery copy. The full original
export is retained privately with SHA-256
`ac7ed6e3765cdf5179624d29a73f7d694e46e1d13d53556a4a9305f0670b38c2`.

## What changed

The short route previously offered nine farmers markets and one amusement park,
with no dedicated nature destination. Three reviewed CDFW reserve trail arrivals
were added: Bolsa Chica south access, Upper Newport Bay Big Canyon access, and
Batiquitos Lagoon Gabbiano access. Their original OSM arrival coordinates, actual
road responses, official access evidence, rights notices and derived dated solar
windows are retained. See the [source review](../../catalog-nature-refresh-20261024.md).

All **39 distinct captured places** were rated through the actual configured
`mentro:Groq/openai/gpt-oss-120b` gateway using
`attraction-traits-v3-destination-rubric`, then persisted before the campaign.
The rubric distinguishes the destination itself from nearby attractions: market
stalls do not become hiking trails and coastal location alone does not establish
nature access. [The audit](rating-audit.json) preserves old/new traits and actual
model/timestamp provenance. These are AI estimates, not human-validated scores.

Catalog generation
`f4f8d0672d4c6e6bfa0f818b937837df40909eb00d8d52df933157e1eb516bcf`
contains **611 places / 192 calendar companions**, preserving all 608 parent rows
and 189 companions. A fresh catalog-only hosted backup was restored in a separate
local database and matched the active pointer, rows, calendars and manifest.

## Unchanged experiment

The design is exactly equal to the previous study: four routes, two personas,
1/2/3 stops per day, seven settings, 30 seeds, 15-second CP-SAT limit and one
solver worker. Geographic admission is uncapped and deterministic around the
full initial route, with a normalized Gaussian width of 5 miles at endpoints and
25 miles at the midpoint (sigma 0.25). Each of four fresh route preparations is
shared across its six scenario captures. There are 24 captures and 5,040 trials.
There is no full-trip planning, scheduling, hotel or budget evaluation.

Geographic/captured pools contain 13, 11, 10 and 24 places for LA–San Diego,
SF–Boise, SF–Denver and SF–New York respectively. Solver eligibility remains
separate: coast-to-coast has 23 eligible nature and 22 eligible entertainment
places. [Input audit](input-audit.json) records every exclusion; no count cap is
used to manufacture a fixed sample size.

## Results and limitations

All **720 baseline trials are OPTIMAL**, fulfilling all requested stops.
Across equally represented baseline scenarios, eligible-pool mean utility is
**0.255999**, selected mean utility **0.409306**, and gain **+15.3307 percentage
points**. Twenty-two scenarios improve; the two negative cases are entertainment
with three stops/day on SF–Denver (−1.6833 points) and SF–New York (−2.3439).
All 24 baseline scenarios select the same set across their 30 seeds. Of the 158
scenario/setting groups with valid selections, 155 are seed-invariant.

| Short-trip nature setting | Eligible pool mean | Selected mean | Selected destinations |
| --- | ---: | ---: | --- |
| 1 stop | 22.81% | 68.50% | Upper Newport Bay |
| 2 stops | 22.81% | 69.00% | Upper Newport Bay, Batiquitos Lagoon |
| 3 stops | 22.81% | 69.00% | Bolsa Chica, Upper Newport Bay, Batiquitos Lagoon |

The earlier three-stop value was 28.83%, but catalog coverage **and** the rating
rubric changed, and road inputs were recaptured. This is not an isolated causal
estimate of an algorithm improvement. The solver and sweep settings did not change.

Across all settings, **4,740 trials are OPTIMAL and 300 INFEASIBLE**. Every
infeasible case is in the zero-quality-loss setting: ten scenarios × thirty seeds.
The conservative encoding floors each utility at scale 1,000,000 but rounds the
required total upward. In these cases the required total exceeds the maximum
attainable integer total by 1–10 units. The stored diagnostic explicitly flags
this numerical boundary. It is not a provider failure, timeout or evidence that
the physical trip is infeasible. The [zero-loss audit](zero-loss-audit.json)
retains each affected scenario and bound. The other six settings are all optimal.
Do not summarize all 5,040 trials as successful or impute zero utility for failures.

Baseline mean solver time is **9.384 ms**; mean complete trial wall time is
**43.692 ms**. Timings are descriptive local measurements, not isolated hardware
benchmarks. Execution used macOS on an M4 Pro, 12 logical CPUs, 24 GiB RAM,
Python 3.12.14 and OR-Tools 9.10.4067. A clean temporary checkout and dependency
environment avoided local file-sync stalls; it retained the same source revision
and hardware. Development services ran on the same host. Seeds repeat fixed pools,
not independent travelers or place samples. Small regional pools do not establish
100-candidate scaling or nationwide nature coverage.

## Evidence and figures

- [All case results, including failures](case-results.csv)
- [Machine-readable summary](summary.json)
- [Exact database/local comparison](database-verification.json)
- [Reproducible analysis](analyze_export.py)
- [Candidate versus selected utility](candidate-selected-utility.png) ([SVG](candidate-selected-utility.svg))
- [Utility-change heatmap](utility-gain-heatmap.png) ([SVG](utility-gain-heatmap.svg))

The heatmap's dashes mean no valid selection in that cell; measured zero is shown
as 0.0. Cross-setting comparisons use only explicitly matched, assessed scenarios.
The older packet remains as clearly labeled historical evidence and must not be
pooled with this replacement dataset.
