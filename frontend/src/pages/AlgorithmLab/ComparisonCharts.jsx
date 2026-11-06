import PropTypes from 'prop-types';
import { useState } from 'react';
import { comparisonGroups } from './comparisonGroups';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const average = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const quantile = (values, fraction) => {
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * fraction;
  const lower = Math.floor(position);
  return (
    sorted[lower] + (position - lower) * ((sorted[lower + 1] ?? sorted[lower]) - sorted[lower])
  );
};

function BoxPlot({ title, values, unit }) {
  if (!values.length) return <p>{title}: Unassessed.</p>;
  const maximum = Math.max(...values, 1);
  const minimum = Math.min(...values, 0);
  const x = (value) => 45 + ((value - minimum) / (maximum - minimum || 1)) * 510;
  const q1 = quantile(values, 0.25);
  const q3 = quantile(values, 0.75);
  const mid = quantile(values, 0.5);
  const low = Math.min(...values.filter((value) => value >= q1 - 1.5 * (q3 - q1)));
  const high = Math.max(...values.filter((value) => value <= q3 + 1.5 * (q3 - q1)));
  return (
    <figure>
      <figcaption>
        {title} ({unit}) · n={values.length};{' '}
        {values.length < 4 ? 'observations only' : '1.5 × IQR whiskers'}
      </figcaption>
      <svg
        viewBox="0 0 600 100"
        role="img"
        aria-label={`${title}, ${values.length} assessed outputs`}
        style={{ width: '100%', maxWidth: 650 }}
      >
        <line x1="45" x2="555" y1="70" y2="70" stroke="currentColor" />
        {values.length >= 4 && (
          <g stroke="#225ea8" fill="#d9e8f5">
            <line x1={x(low)} x2={x(high)} y1="40" y2="40" />
            <rect x={x(q1)} y="25" width={x(q3) - x(q1)} height="30" />
            <line x1={x(mid)} x2={x(mid)} y1="25" y2="55" />
          </g>
        )}
        {values.map((value, index) => (
          <circle key={index} cx={x(value)} cy={40 + ((index % 5) - 2) * 3} r="3" fill="#225ea8">
            <title>
              {value.toFixed(3)} {unit}
            </title>
          </circle>
        ))}
        <text x="45" y="90">
          {minimum.toFixed(1)}
        </text>
        <text x="555" y="90" textAnchor="end">
          {maximum.toFixed(1)}
        </text>
      </svg>
      <details>
        <summary>Calculated observations</summary>
        <p>
          {values.map((value) => value.toFixed(3)).join(', ')} {unit}
        </p>
      </details>
    </figure>
  );
}
BoxPlot.propTypes = {
  title: PropTypes.string.isRequired,
  values: PropTypes.array.isRequired,
  unit: PropTypes.string.isRequired,
};

function Columns({ title, values, unit }) {
  const assessed = Object.entries(values).filter(([, value]) => finite(value));
  if (!assessed.length) return <p>{title}: Unassessed.</p>;
  const maximum = Math.max(...assessed.map(([, value]) => value), 1);
  return (
    <figure>
      <figcaption>
        {title} ({unit})
      </figcaption>
      <svg
        viewBox="0 0 650 210"
        role="img"
        aria-label={title}
        style={{ width: '100%', maxWidth: 700 }}
      >
        <line x1="35" x2="620" y1="155" y2="155" stroke="currentColor" />
        {assessed.map(([label, value], index) => {
          const width = 570 / assessed.length;
          const height = (value / maximum) * 115;
          return (
            <g key={label}>
              <rect
                x={40 + index * width}
                y={155 - height}
                width={Math.min(45, width - 5)}
                height={height}
                fill="#225ea8"
              />
              <text x={40 + index * width} y={145 - height}>
                {value.toFixed(1)}
              </text>
              <text x={40 + index * width} y="180" fontSize="10">
                {label}
              </text>
            </g>
          );
        })}
      </svg>
      <p>{assessed.map(([label, value]) => `${label}: ${value.toFixed(2)} ${unit}`).join('; ')}</p>
    </figure>
  );
}
Columns.propTypes = {
  title: PropTypes.string.isRequired,
  values: PropTypes.object.isRequired,
  unit: PropTypes.string.isRequired,
};

function MethodCharts({ rows }) {
  const valid = rows.filter(
    (row) =>
      row.status === 'completed' &&
      row.metrics.trip_evaluation?.completed &&
      row.metrics.trip_evaluation?.stop_fulfillment?.ratio === 1 &&
      row.metrics.trip_evaluation?.schedule_compliance?.violation_count === 0
  );
  const values = (get) => valid.map((row) => get(row.metrics.trip_evaluation)).filter(finite);
  const statuses = {};
  rows.forEach((row) => {
    const status = row.metrics.solver_status ?? 'NOT_RUN';
    statuses[status] = (statuses[status] ?? 0) + 1;
  });
  const hotelExcess = values((trip) => trip.hotel_costs?.above_target_total_usd);
  const hotelUtilization = values((trip) => trip.hotel_costs?.budget_utilization).map(
    (value) => value * 100
  );
  const overTarget = values((trip) => trip.hotel_costs?.over_target_fraction).map(
    (value) => value * 100
  );
  return (
    <>
      <BoxPlot
        title="Delivered attraction utility score"
        unit="%"
        values={values((trip) => trip.utility?.delivered?.mean).map((value) => value * 100)}
      />
      <BoxPlot
        title="Longest actual driving stretch"
        unit="minutes"
        values={values((trip) => trip.driving_gaps?.maximum_stretch_seconds).map(
          (value) => value / 60
        )}
      />
      <Columns title="Raw solver statuses, all recorded outcomes" unit="runs" values={statuses} />
      <Columns
        title="Mean quoted nightly room-target excess"
        unit="USD"
        values={{
          [`assessed n=${hotelExcess.length}`]: hotelExcess.length ? average(hotelExcess) : null,
        }}
      />
      <Columns
        title="Nightly room-target utilization and excess fraction"
        unit="%"
        values={{
          [`utilization n=${hotelUtilization.length}`]: hotelUtilization.length
            ? average(hotelUtilization)
            : null,
          [`over target n=${overTarget.length}`]: overTarget.length ? average(overTarget) : null,
        }}
      />
    </>
  );
}
MethodCharts.propTypes = { rows: PropTypes.array.isRequired };

function Group({ rows }) {
  const metrics = rows[0].metrics;
  const valid = rows.filter(
    (row) =>
      row.status === 'completed' &&
      row.metrics.trip_evaluation?.completed &&
      row.metrics.trip_evaluation?.stop_fulfillment?.ratio === 1 &&
      row.metrics.trip_evaluation?.schedule_compliance?.violation_count === 0
  );
  const sourceReleases = [
    ...new Set(
      (metrics.candidate_snapshot ?? [])
        .map((candidate) => candidate.source_release)
        .filter(Boolean)
    ),
  ];
  const generations = [
    ...new Set(
      (metrics.candidate_snapshot ?? [])
        .map((candidate) => candidate.source_generation)
        .filter(Boolean)
    ),
  ];
  return (
    <details>
      <summary>
        {rows[0].preset_id} · {valid.length} successful fulfilled / {rows.length} recorded on this
        page
      </summary>
      <p>
        Revision {metrics.revision}; metrics {metrics.metric_version}; evidence{' '}
        {metrics.evidence_layer ?? 'not recorded'}. Catalog generation:{' '}
        {generations.join(', ') || 'not recorded'}; releases:{' '}
        {sourceReleases.join(', ') || 'not recorded'}.
      </p>
      <p>
        Identical inputs and captured candidate hashes only. Target-day adherence is separate. Seed
        repeats describe solver variation. This chart does not establish access review or current
        availability.
      </p>
      {[...new Set(rows.map((row) => row.metrics.algorithm ?? 'cp_sat'))].map((method) => (
        <section key={method} aria-label={`${method} comparison series`}>
          <h4>{method}</h4>
          <MethodCharts
            rows={rows.filter((row) => (row.metrics.algorithm ?? 'cp_sat') === method)}
          />
        </section>
      ))}
    </details>
  );
}
Group.propTypes = { rows: PropTypes.array.isRequired };

export default function ComparisonCharts({ rows }) {
  const [expanded, setExpanded] = useState(false);
  const groups = comparisonGroups(rows);
  return (
    <section aria-label="Current page comparison charts">
      <h3>Current page comparisons</h3>
      <p>
        Quality distributions use completed, fulfilled, timing-valid live outputs. Status columns
        retain failures. Unassessed data and synthetic replay are excluded from quality plots.
      </p>
      {!groups.length && <p>No comparable measured live records on this page.</p>}
      {(expanded ? groups : groups.slice(0, 4)).map((group) => (
        <Group
          key={`${group[0].metrics.cohort_key}-${group[0].metrics.candidate_hash}-${group[0].metrics.revision}-${group[0].metrics.metric_version}`}
          rows={group}
        />
      ))}
      {groups.length > 4 && (
        <button type="button" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show first four groups' : `Show all ${groups.length} comparison groups`}
        </button>
      )}
    </section>
  );
}
ComparisonCharts.propTypes = { rows: PropTypes.array.isRequired };
