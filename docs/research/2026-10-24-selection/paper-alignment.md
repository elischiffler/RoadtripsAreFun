# Paper alignment: selection-only research

Verified source: `dec327426244f10e4c3c34bb7fd00177224586a7`, branch
`codex/real-data-research`, RoadtripsAreFun PR #57 (target develop).
Study: `05fc366d-4623-4467-ba06-a93911147993`.

The user explicitly removed full trip planning from research after an earlier
combined campaign began. That campaign was stopped and removed from active stores
with a recovery copy. Its results and the preflights must not be pooled with this
study. Ordinary app trip planning is still implemented but is not evaluated here.

| Paper claim | Assessment and source | Replacement or qualification |
| --- | --- | --- |
| Fourteen normalized preference attributes | Verified: `backend/app/agent/persona.py:10`, `:49`; `routing/profiles.py:54` | Utility is the sum of normalized persona weights times AI-estimated attribute ratings. It measures estimated preference match, not traveler satisfaction. |
| At most 60 candidates | Verified: `backend/app/research/design.py:66`; `routing/cp_sat_selection.py:86` | Sixty is a cap. Report actual eligible pool sizes; never imply every scenario had 60 places. |
| Real source/AI/road inputs | Verified: `backend/app/research/collect.py:22`; `evidence.py:29`; `routing/planners/cp_sat.py:162` | Capture real pre-selection candidates with source provenance, persisted model-tagged traits, calendar checks and measured solo road routes. Freeze them across settings/seeds. |
| Select exactly K available attractions | Verified: `routing/cp_sat_selection.py:155` | K=min(requested, eligible). A valid optimal selection can still have fewer attractions than requested. Report selected/requested fulfillment separately. |
| Quality bound | Verified: `routing/cp_sat_selection.py:146` and `:170` | Compute the best top-K average before solving. The selected average must be at least that mean minus epsilon. Epsilon 0.10 is an absolute utility allowance. Utility is protected by a constraint rather than maximized directly. |
| Spacing and detour objective | Verified: `routing/cp_sat_selection.py:179` and `:205` | The ordered selected attractions form K+1 baseline gaps, including endpoints. Minimize total absolute deviation from equal spacing plus weighted summed solo detours. Baseline progress is not an actual arrival time. |
| Solo detours | Verified: `routing/planners/cp_sat.py:162` | Each estimate is max(0, measured origin–place–destination time minus baseline time); the raw signed difference is retained. Their sum is not actual extra itinerary driving. |
| Five-second solve limit / three seeds | Outdated: `backend/app/research/design.py:34`, `:66`; `routing/cp_sat_selection.py:292` | This study uses a 15-second limit, one solver worker and 30 seeds, numbered 0–29. |
| Scaling and zero-loss infeasibility | Verified: `routing/cp_sat_selection.py:146` and `:331` | Utilities are floored at scale 1,000,000; the required total is conservatively rounded upward with a small tolerance. Zero-loss infeasibility can be a rounding artifact. Report solver status honestly. Objective/bounds are converted back from integer gap/weight scaling. |
| Fixed two-hour visits | Inaccurate for current app: `routing/visit_duration.py:29`, `routing/sources/visit_durations.py` | The app uses bounded estimated visit durations with fallback. In this study these support candidate calendar eligibility; no complete schedule or trip duration is evaluated. |
| Four routes × two personas × three densities | Verified: `backend/app/research/design.py:83` | 24 scenarios: LA–SD (1/2/3 stops), SF–Boise (2/4/6), SF–Denver (3/6/9), SF–NY (5/10/15), each for nature and entertainment. Target days only set requested counts. |
| Paper sweeps | Verified: `backend/app/research/design.py:66` | Loss {0,.05,.10,.20}; detour weight {0,.25,1,4}; spacing weight1. Shared baseline appears once, giving seven configurations. 24×7×30=5,040 solver trials plus 24 preparation captures. |
| Full-pipeline evaluations | Removed at user's request: `backend/app/research/collect.py:22`, `worker.py:68`, `metrics.py:8` | Remove full-trip evaluation, successful itinerary delivery, actual trip length, final added distance/driving, hotel outcomes and all budget measurements from Methods/Results. Describe downstream scheduling only as unevaluated application context if needed. |
| Candidate-to-selected utility graph | Implemented: `backend/app/research/metrics.py:8`; `frontend/src/pages/StudioResearch/ResearchCharts.jsx` | Show eligible-pool mean and selected mean on the same frozen scenario, plus percentage-point difference and assessed denominators. Missing or failed values stay missing. |
| Persistence and reproducibility | Verified: `backend/app/research/store.py`, `database.py`, `evidence.py:84` | PostgreSQL retains protocol, all cases, captures, actual model/source provenance and outcomes. JSON `protocol.cases` is the full evidence export; CSV is per-case measurements. Source/capture hashes prevent mixed input comparisons. |

Paths beginning `routing/` are relative to `backend/app/`; `evidence.py`, `worker.py`,
`metrics.py` and `database.py` are in `backend/app/research/`.

## Writing and analysis constraints

- Preserve the user's simple first-person student style using the cloud
  `/workspace/write-like-me/SKILL.md`. Preserve the existing headings, Aptos12,
  plain black text, Plain Table3 and native editable equations. No abstract.
- Do not restore removed pseudocode/path-spacing equations automatically.
- Use the final `summary.json` and per-trial CSV, not protocol counts as outcomes.
  The summary script refuses a non-complete queue. Preflights are not observations.
- Report solver status counts and valid selections separately from selected/requested
  fulfillment and preparation success. Keep failures and empty inputs visible.
- Candidate pools are real but limited by the catalog, acquisition/calendar rules,
  discovery strategy, fixed departure and AI estimates. Do not claim comprehensive
  attraction coverage, subjective satisfaction or full itinerary feasibility.
- Thirty seeds are computational repeats of each fixed pool. They are not 30
  independent travelers or 30 independently collected place samples. Prefer
  descriptive scenario-level summaries; do not manufacture statistical significance.
- Compare parameter settings on matched scenario/seed pairs with valid results in
  both. Report the pair count; zero-loss failures can shrink that subset.
- Summed solo detours and baseline gaps describe the selection model. Do not call
  them actual final-route driving. Objective magnitudes across differently weighted
  models are not directly comparable as an unweighted quality score.
- Results/Discussion should explain observed changes and limitations without
  asserting that every optimized selection improves mean utility over the entire
  pool. The spacing/detour objective can trade away utility within its allowance.

## Document destination

The existing cloud chat is **Outline trip-planning research paper**. Its last
paper target was the SharePoint document with sourcedoc
`A3F0235B-5023-4DC1-B404-8EEEEB102E25` (Final Report.docx). A separate ambient browser
snapshot showed `71AD0D4D-7CFA-4BEB-A144-C2D1635B1A1A` (Eli Schiffler Route Planning
Project.docx). Confirm the active target from the writing chat's context and
connected document; do not silently overwrite a different document.
