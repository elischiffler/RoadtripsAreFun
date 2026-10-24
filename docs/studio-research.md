# Studio research

`/studio/research` displays saved research from PostgreSQL, with scenario filters,
charts and CSV/JSON exports. The October 24 real-data protocol replaces the old
synthetic studies. Synthetic fixtures remain in automated software tests, but
cannot supply observations to this study.

## Protocol

Four routes × two personas (nature and entertainment) × three attraction densities
produce 24 scenarios. Each has two adults in one room, an 08:00 origin-local
departure, no car contribution and no evening suggestions. The departure date is
frozen when the study is created (default: seven days after the Los Angeles date).

| Route | Target days | Requested attractions |
| --- | --- | --- |
| Los Angeles–San Diego | 1 | 1 / 2 / 3 |
| San Francisco–Boise | 2 | 2 / 4 / 6 |
| San Francisco–Denver | 3 | 3 / 6 / 9 |
| San Francisco–New York | 5 | 5 / 10 / 15 |

Target days determine requested stop counts; actual itinerary days remain an
observed outcome. The tight-budget scenario is removed. Research does not measure
or persist budgets, financial quotes or costs. The shared trip planner still uses
its ordinary fixed nightly hotel target when executing live trips. This is an
operational setting, not an experimental factor, and ordinary trip planning is
unchanged.

Every solver trial uses a 15-second limit, at most 60 supplied candidates, one
OR-Tools worker and spacing weight 1. Each scenario has 30 seeds (0–29) under
seven one-factor configurations. The baseline is counted once:

| Configuration | Allowed mean utility loss | Detour weight |
| --- | --- | --- |
| Baseline | 0.10 | 1 |
| Quality sweep | 0 / 0.05 / 0.20 | 1 |
| Detour sweep | 0.10 | 0 / 0.25 / 4 |

That schedules **5,040 solver trials** and **240 fresh full-trip attempts** (ten
per scenario). These are planned counts, not claims of successful completion.

## Real inputs and execution order

The first full-trip attempt of each scenario runs before any controlled solver
trials. Its last actual selection input is captured with catalog identities,
source generations, facts/provenance, complete AI-estimated traits, persona
weights, utilities, baseline driving duration, measured route progress, solo
detours, query points and capture timestamp. Its first attempt is also one of the
ten full-trip repetitions, not an additional independent observation. A failure
after selection can still supply a valid measured candidate pool. Failure before
capture blocks that scenario's solver trials; no invented pool or replacement
attempt is substituted.

The capture retains all supplied candidates, including rejected ones, so the
eligibility denominator can be audited. Each capture is hashed and linked by case
ID. Every solver seed and parameter setting for that scenario reuses those exact
inputs. A tampered hash or mismatched scenario cannot be solved. Candidate pools
can contain fewer than 60 places; they are never padded. Only the currently active
catalog and normal admission/calendar/road checks supply live candidates.

The existing `place_attribute_traits` cache stores valid missing trait estimates
through the configured AI gateway. Utility is recomputed from frozen persona
weights and the 14 traits, never accepted as a model-supplied final score. Traits
remain AI estimates of real places, not human preference labels or visitor
satisfaction. Every candidate's estimates and source provenance also remain in
its research capture, independently of future cache expiry. The model-provenance
cache contract refreshes older unidentified estimates on demand. Every captured
candidate must have a persistent rating timestamp and served provider/model ID.

After the 24 initial attempts, solver trials execute serially without concurrent
live research work. Remaining live attempts run two at a time. Each live attempt
has a 20-minute deadline. Provider conditions, discovery and final routes may
vary across live repetitions; these do not isolate solver parameter effects.
The controlled repeats measure solver variation on the same captured pool, not
30 independent samples of places or travelers.

## Utility and other measurements

- `candidate_utility_mean`: mean over eligible candidate records before selection.
- `selected_utility_mean`: mean over solver-selected places for OPTIMAL/FEASIBLE
  outcomes, including cases where later scheduling fails.
- `utility_gain`: selected mean minus candidate mean, stored on the 0–1 scale and
  displayed in percentage points. `selection_assessed` identifies valid pairs.
- `best_available_utility_mean`: mean of the highest K eligible utility scores;
  `quality_loss` is this reference minus the selected mean. The objective still
  minimizes spacing deviations and estimated solo detours, not utility directly.
- `utility_mean/min/median/max` and `utility_values` describe fully delivered,
  timing-valid trips (or fully fulfilled solver selections). They are separate
  from the paired selection measurements.
- Spacing deviation, longest gap, estimated solo detours, actual added driving
  and distance, fulfillment, actual days, solver/runtime measurements, objective,
  bound, selected IDs and exact solver statuses remain available in exports.

The paired utility chart uses the same assessed runs on both sides of every
comparison. The metric selector also offers candidate mean, selected mean and
utility change in the scenario heatmap. Each chart retains its assessed count;
missing results never become zero. Distributions and ranges are descriptive,
not confidence intervals or independent-sample claims. Full-trip utility quality
plots require complete delivery and zero recorded timing violations.

OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, EMPTY and NOT_RUN remain
distinct. Failure, partial delivery, interruption and missing-capture blocking
remain in the dataset. Integer rounding can make the zero-loss quality bound
unattainable; that does not prove a real-world shortage of places.

## Storage and access

`app/research/store.py` owns the private SQLite execution queue under
`.artifacts/studio-research` (or `STUDIO_RESEARCH_DIR`). PostgreSQL stores protocols,
all declared cases and results in `studio_research_studies` and
`studio_research_runs`. Existing JSONB columns hold the new protocol and evidence;
no schema migration or production deployment is needed. Full live evidence is
also saved through the existing owner-scoped Lab storage, with financial fields
removed before persistence, and privately beside the local queue.

The first pipeline result of each scenario contains `capture`; every pipeline
result contains `live_evidence`. PostgreSQL stores these complete objects.
Lightweight chart snapshots omit them, while JSON exports include them. CSV
contains per-run observations, source identity, capture references and hashes.
The protocol's `dataset_hash` identifies its capture specification; each solver
row's `dataset_hash` identifies the actual frozen real input. Do not confuse the
two or describe the protocol hash as a captured dataset hash.

`STUDIO_RESEARCH_ENABLED`, `STUDIO_RESEARCH_DATABASE` and
`PLACE_TRAITS_CACHE_ENABLED` are local execution/persistence opt-ins; deployment
defaults stay disabled. Existing additive research/trait SQL must already be
applied explicitly. Database sync backfills the local queue and follows monotonic
completion cursors. Source/protocol conflicts fail closed. A valid Studio session
can read saved results across browsers; private study capabilities control work.

The new browser cache namespace prevents removed synthetic versions from being
restored by an old completed-study cache. Failed/partial provider work is retained
under its original deterministic run UUID. Restart never silently repeats paid
work. Three consecutive storage/auth/model-configuration failures pause unstarted
cases. Capture validation failures retain the original live evidence. Source-hash
changes prohibit resuming a mixed-code campaign. The detached macOS worker uses
`caffeinate` while running, but the computer must remain on.

## Local operation

From `backend/`, using the configured development environment:

```sh
.venv/bin/python -m app.research.manage create --control-file /absolute/private/new-study.json
.venv/bin/python -m app.research.manage status STUDY_UUID
```

Creation verifies database/cache opt-in, saves the immutable protocol and private
control key, mirrors it to PostgreSQL and starts the worker. To remove specifically
approved old studies, `manage remove --study-id UUID [--study-id UUID ...] --backup
/absolute/new/recovery-directory` first creates a verified SQLite backup and JSON
copies of the named PostgreSQL research/Lab records. It serializes against mirror
writes and refuses active studies, then removes only the named studies and their
local run directories. Recovery copies are outside the active dataset and never
participate in charts or paper results. This is an explicit local operator action,
not a public deletion endpoint.

Application checks and small live verification attempts are separate from the
paper campaign. See `docs/container-validation.md` for checks; report empirical
completion only from the saved campaign's actual outcomes.
