export const finite = (v) => typeof v === 'number' && Number.isFinite(v);
export const mean = (values) =>
  values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
export function distribution(values) {
  const sorted = values.filter(finite).sort((a, b) => a - b);
  const n = sorted.length;
  const average = mean(sorted);
  const quantile = (fraction) => {
    if (!n) return null;
    const position = (n - 1) * fraction;
    const index = Math.floor(position);
    return (
      sorted[index] + (position - index) * ((sorted[index + 1] ?? sorted[index]) - sorted[index])
    );
  };
  return {
    n,
    mean: average,
    min: n ? sorted[0] : null,
    max: n ? sorted[n - 1] : null,
    median: n ? (sorted[Math.floor((n - 1) / 2)] + sorted[Math.ceil((n - 1) / 2)]) / 2 : null,
    sd:
      n > 1
        ? Math.sqrt(sorted.reduce((sum, value) => sum + (value - average) ** 2, 0) / (n - 1))
        : null,
    q1: quantile(0.25),
    q3: quantile(0.75),
  };
}
export const METRICS = {
  utility_mean: { label: 'Mean utility score', unit: '%', scale: 100, digits: 1 },
  utility_min: { label: 'Lowest utility score', unit: '%', scale: 100, digits: 1 },
  utility_median: { label: 'Median utility score', unit: '%', scale: 100, digits: 1 },
  utility_max: { label: 'Highest utility score', unit: '%', scale: 100, digits: 1 },
  max_gap_seconds: { label: 'Longest driving gap', unit: 'hours', scale: 1 / 3600, digits: 2 },
  extra_meters: {
    label: 'Added distance',
    unit: 'miles',
    scale: 1 / 1609.344,
    digits: 1,
    live: true,
  },
  extra_seconds: { label: 'Added driving', unit: 'minutes', scale: 1 / 60, digits: 1, live: true },
  candidate_utility_mean: {
    label: 'Candidate-pool mean utility',
    unit: '%',
    scale: 100,
    digits: 1,
  },
  selected_utility_mean: { label: 'Selected-place mean utility', unit: '%', scale: 100, digits: 1 },
  utility_gain: { label: 'Utility change after selection', unit: 'points', scale: 100, digits: 1 },
  runtime_seconds: { label: 'Planning time', unit: 's', scale: 1, digits: 2 },
  solver_seconds: { label: 'Selection time', unit: 'ms', scale: 1000, digits: 1 },
  fulfillment: { label: 'Requested stops delivered', unit: '%', scale: 100, digits: 1 },
  actual_days: { label: 'Actual trip length', unit: 'days', scale: 1, digits: 1, live: true },
};
export const metricValue = (row, metric) =>
  finite(row[metric]) ? row[metric] * METRICS[metric].scale : null;
export const format = (value, digits = 1) =>
  finite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
// Selection values are scaled to milliseconds by metricValue; persisted fields stay in seconds.
export function formatSelectionTime(milliseconds) {
  if (!finite(milliseconds)) return '—';
  const magnitude = Math.abs(milliseconds);
  if (magnitude > 0 && magnitude < 0.01) return milliseconds < 0 ? '>−0.01 ms' : '<0.01 ms';
  const [divisor, unit] =
    magnitude >= 3600000
      ? [3600000, 'h']
      : magnitude >= 60000
        ? [60000, 'min']
        : magnitude >= 1000
          ? [1000, 's']
          : [1, 'ms'];
  return `${format(milliseconds / divisor, 2)} ${unit}`;
}
export const metricUnit = (metric) => (metric === 'solver_seconds' ? '' : METRICS[metric].unit);
export function metricText(value, metric, includeUnit = false) {
  if (!finite(value)) return '—';
  if (metric === 'solver_seconds') return formatSelectionTime(value);
  return `${format(value, METRICS[metric].digits)}${includeUnit ? `${METRICS[metric].unit === '%' ? '' : ' '}${METRICS[metric].unit}` : ''}`;
}
export const metricDifference = (value, metric) =>
  METRICS[metric].unit === '%'
    ? `${metricText(value, metric)} points`
    : metricText(value, metric, true);
export function metricRange(low, high, metric) {
  if (metric === 'solver_seconds')
    return `${formatSelectionTime(low)}–${formatSelectionTime(high)}`;
  return `${metricText(low, metric)}–${metricText(high, metric)}${METRICS[metric].unit === '%' ? '' : ' '}${METRICS[metric].unit}`;
}
export function sample(rows, metric) {
  return distribution(
    rows
      .filter(
        (row) =>
          (['candidate_utility_mean', 'selected_utility_mean', 'utility_gain'].includes(metric)
            ? row.selection_assessed
            : row.completed) ||
          ['runtime_seconds', 'solver_seconds', 'fulfillment', 'actual_days'].includes(metric)
      )
      .map((row) => metricValue(row, metric))
  );
}
export function paired(rows, variant, metric) {
  const key = (row) =>
    `${row.study_id ?? ''}:${row.trip}:${row.persona}:${row.stops_per_day}:${row.repeat}`;
  const base = new Map(
    rows.filter((row) => row.variant === 'baseline' && row.completed).map((row) => [key(row), row])
  );
  return distribution(
    rows
      .filter((row) => row.variant === variant && row.completed)
      .map((row) => {
        const other = base.get(key(row));
        const a = metricValue(row, metric);
        const b = other ? metricValue(other, metric) : null;
        return finite(a) && finite(b) ? a - b : null;
      })
  );
}

const METRIC_HELP = {
  utility_mean: 'Mean estimated utility score across the attractions in a run.',
  utility_min: 'Utility score of the lowest-scoring attraction in each run.',
  utility_median: 'Median attraction utility score within each run.',
  utility_max: 'Utility score of the highest-scoring attraction in each run.',
  max_gap_seconds:
    'Longest driving gap between attractions, including the origin and destination. Stop selection runs use measured baseline progress; full trip planning runs use actual route legs, excluding overnight downtime.',
  extra_meters: 'Road distance added compared with the direct origin-to-destination route.',
  extra_seconds: 'Driving time added compared with the direct route; visit time is excluded.',
  candidate_utility_mean:
    'Mean utility of the eligible places supplied to the solver, before selection.',
  selected_utility_mean:
    'Mean utility of the solver-selected places. This describes selection even if later trip scheduling fails.',
  utility_gain:
    'Selected-place mean minus eligible candidate-pool mean, in percentage points. Each difference uses the same run and persona; positive values are not guaranteed.',
  runtime_seconds:
    'Full trip planning time, or model-and-solve time for stop selection runs. Failed runs retain measured time until failure.',
  solver_seconds:
    'Time inside the CP-SAT solver. Units adjust automatically; preparation time is excluded.',
  fulfillment:
    'Delivered stops divided by requested stops. 100% means every requested stop was delivered. Measured partial and failed runs remain included.',
  actual_days:
    'Number of calendar days in the resulting itinerary, which can differ from the target trip length.',
};
export const metricHelp = (metric) => METRIC_HELP[metric];

export function combineStudies(snapshots) {
  if (!snapshots.length) return null;
  const sources = snapshots.map(({ id, state, counts }) => ({ id, state, total: counts.total }));
  const active = sources.find((source) =>
    ['running', 'starting', 'pausing'].includes(source.state)
  );
  const incomplete = sources.find((source) => source.state !== 'complete');
  const union = (key) => [...new Set(snapshots.flatMap((study) => study.design[key]))];
  return {
    sources,
    state: active?.state ?? incomplete?.state ?? 'complete',
    counts: Object.fromEntries(
      ['total', 'pipeline', 'solver'].map((key) => [
        key,
        snapshots.reduce((sum, study) => sum + study.counts[key], 0),
      ])
    ),
    design: { trips: union('trips'), stops_per_day: union('stops_per_day') },
    variants: [
      ...new Map(
        snapshots.flatMap((study) => study.variants).map((variant) => [variant.id, variant])
      ).values(),
    ],
    solve_limits: [
      ...new Set(
        snapshots
          .flatMap((study) => study.variants.map((variant) => variant.config?.time_limit_seconds))
          .filter(finite)
      ),
    ],
    dataset_hashes: [...new Set(snapshots.map((study) => study.dataset_hash))],
    rows: snapshots.flatMap((study) =>
      study.rows.map((row) => ({
        ...row,
        id: `${study.id}:${row.id}`,
        case_id: row.id,
        study_id: study.id,
      }))
    ),
  };
}

export const runCount = (count) => `${format(count, 0)} ${count === 1 ? 'run' : 'runs'}`;
export const solverLabel = (status) =>
  ({
    OPTIMAL: 'Optimal',
    FEASIBLE: 'Feasible',
    INFEASIBLE: 'Infeasible',
    UNKNOWN: 'Unknown',
    MODEL_INVALID: 'Model invalid',
    EMPTY: 'Empty candidate set',
    NOT_RUN: 'Not run',
  })[status] ?? 'Unclassified result';

export const interestLabel = (persona) =>
  ({ nature: 'Nature', entertainment: 'Entertainment' })[persona] ?? persona;
export const settingLabel = (setting) =>
  setting.id === 'baseline'
    ? 'Default settings'
    : setting.parameter === 'quality_loss'
      ? `Allowed utility score drop: ${format(setting.value * 100)} points`
      : `Added driving penalty: ${format(setting.value)}×`;
