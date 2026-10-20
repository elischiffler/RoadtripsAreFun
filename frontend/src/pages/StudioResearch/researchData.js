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
  utility_mean: { label: 'Average utility', unit: '%', scale: 100, digits: 1 },
  utility_min: { label: 'Lowest utility', unit: '%', scale: 100, digits: 1 },
  utility_median: { label: 'Median utility', unit: '%', scale: 100, digits: 1 },
  utility_max: { label: 'Highest utility', unit: '%', scale: 100, digits: 1 },
  max_gap_seconds: { label: 'Longest gap', unit: 'hours', scale: 1 / 3600, digits: 2 },
  extra_meters: {
    label: 'Added distance',
    unit: 'miles',
    scale: 1 / 1609.344,
    digits: 1,
    live: true,
  },
  extra_seconds: { label: 'Added driving', unit: 'minutes', scale: 1 / 60, digits: 1, live: true },
  budget_utilization: { label: 'Hotel target used', unit: '%', scale: 100, digits: 1, live: true },
  budget_excess_usd: { label: 'Above hotel target', unit: 'USD', scale: 1, digits: 2, live: true },
  runtime_seconds: { label: 'Planning time', unit: 'seconds', scale: 1, digits: 2 },
  solver_seconds: { label: 'Selection time', unit: 'ms', scale: 1000, digits: 1 },
  fulfillment: { label: 'Requested stops delivered', unit: '%', scale: 100, digits: 1 },
  actual_days: { label: 'Actual trip length', unit: 'days', scale: 1, digits: 1, live: true },
};
export const metricValue = (row, metric) =>
  finite(row[metric]) ? row[metric] * METRICS[metric].scale : null;
export const format = (value, digits = 1) =>
  finite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
export function sample(rows, metric) {
  return distribution(
    rows
      .filter(
        (row) =>
          row.completed ||
          ['runtime_seconds', 'solver_seconds', 'fulfillment', 'actual_days'].includes(metric)
      )
      .map((row) => metricValue(row, metric))
  );
}
export function paired(rows, variant, metric) {
  const key = (row) => `${row.trip}:${row.persona}:${row.stops_per_day}:${row.repeat}`;
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
  utility_mean: 'Average estimated persona match across the attractions in a run.',
  utility_min: 'Match score of the lowest-scoring attraction in each run.',
  utility_median: 'Middle attraction match score within each run.',
  utility_max: 'Match score of the highest-scoring attraction in each run.',
  max_gap_seconds:
    'Longest driving gap between attractions, including the origin and destination. Solver trials use simulated baseline progress; live trips use actual route legs, excluding overnight downtime.',
  extra_meters: 'Road distance added compared with the direct origin-to-destination route.',
  extra_seconds: 'Driving time added compared with the direct route; visit time is excluded.',
  budget_utilization:
    'Quoted hotel cost divided by the room-night target. 100% is on target; above 100% is over. This covers hotels only. Missing quotes are unassessed.',
  budget_excess_usd:
    'Total quoted hotel dollars above the room-night targets; zero means none above target. This is not total-trip spending.',
  runtime_seconds:
    'Core planning time, or model-and-solve time for controlled trials. Failed attempts retain measured time until failure.',
  solver_seconds: 'Time inside the CP-SAT solver, shown in milliseconds.',
  fulfillment:
    'Delivered stops divided by requested stops. 100% means every requested stop was delivered. Assessed partial and failed attempts remain included.',
  actual_days:
    'Number of calendar days in the resulting itinerary, which can differ from the target trip length.',
};
export const metricHelp = (metric) => METRIC_HELP[metric];
