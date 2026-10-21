import PropTypes from 'prop-types';
import { useId, useState } from 'react';
import { ChartHeading } from './ResearchInfo';
import { InspectionGroup, InspectMark } from './ResearchInspect';
import {
  distribution,
  finite,
  format,
  metricHelp,
  METRICS,
  runCount,
  paired,
  sample,
  interestLabel,
  settingLabel,
  metricText,
  metricRange,
  metricUnit,
  metricDifference,
  solverLabel,
} from './researchData';

export function SolverOutcomes({ counts }) {
  const [hovered, setHovered] = useState(null);
  const [focused, setFocused] = useState(null);
  const outcomes = Object.entries(counts);
  const total = outcomes.reduce((sum, [, count]) => sum + count, 0);
  const colors = {
    OPTIMAL: '#234a3c',
    FEASIBLE: '#477560',
    INFEASIBLE: '#ac4c43',
    UNKNOWN: '#a56b28',
    MODEL_INVALID: '#806381',
    EMPTY: '#706b62',
    NOT_RUN: '#756f66',
  };
  if (!total) return <p>No results yet.</p>;
  return (
    <div className="research-solver-outcomes">
      <div className="research-outcome-bar" role="group" aria-label="CP-SAT outcome percentages">
        {outcomes.map(([status, count]) => {
          if (!count) return null;
          const percent = (count / total) * 100;
          return (
            <div
              key={status}
              role="img"
              tabIndex={0}
              className="research-outcome-segment"
              aria-label={`${solverLabel(status)}: ${format(percent)}%, ${runCount(count)}`}
              style={{ width: `${percent}%`, background: colors[status] ?? '#756f66' }}
              onPointerEnter={() => setHovered(status)}
              onPointerLeave={() => setHovered(null)}
              onFocus={() => setFocused(status)}
              onBlur={() => setFocused(null)}
            >
              {percent >= 5 && <span aria-hidden="true">{format(percent)}%</span>}
            </div>
          );
        })}
      </div>
      <ul className="research-outcome-legend" aria-label="CP-SAT outcome counts">
        {outcomes.map(([status, count]) => (
          <li
            key={status}
            className={(hovered ?? focused) === status ? 'is-highlighted' : undefined}
          >
            <i style={{ background: colors[status] ?? '#756f66' }} aria-hidden="true" />
            <span>{solverLabel(status)}</span>
            <strong>{format(count, 0)}</strong>
            <small>{format((count / total) * 100)}%</small>
          </li>
        ))}
      </ul>
    </div>
  );
}
SolverOutcomes.propTypes = { counts: PropTypes.objectOf(PropTypes.number).isRequired };

export function Heatmap({ rows, trips, metric }) {
  const columns = ['nature', 'entertainment'].flatMap((persona) =>
    [1, 2, 3].map((density) => ({ persona, density }))
  );
  const cells = trips.map((trip) => ({
    ...trip,
    cells: columns.map(({ persona, density }) => {
      const matching = rows.filter(
        (row) => row.trip === trip.id && row.persona === persona && row.stops_per_day === density
      );
      return { persona, density, ...sample(matching, metric), attempts: matching.length };
    }),
  }));
  const values = distribution(cells.flatMap((trip) => trip.cells.map((cell) => cell.mean)));
  const firstCell = cells.flatMap((trip) => trip.cells).find((cell) => cell.n);
  const utility = metric.startsWith('utility');
  const span = Math.max(2 * (values.sd ?? 0), utility ? 5 : 10 ** -METRICS[metric].digits);
  const low = utility ? Math.max(0, (values.mean ?? 0) - span) : (values.mean ?? 0) - span;
  const high = utility ? Math.min(100, (values.mean ?? 0) + span) : (values.mean ?? 0) + span;
  const color = (value) => {
    const below = value < values.mean;
    const distance = below ? values.mean - low : high - values.mean;
    const strength = distance ? Math.min(1, Math.abs(value - values.mean) / distance) : 0;
    const neutral = [247, 244, 237];
    const end = below ? [216, 153, 98] : [111, 174, 163];
    return `rgb(${neutral.map((channel, i) => Math.round(channel + (end[i] - channel) * strength)).join(', ')})`;
  };
  return (
    <figure>
      <ChartHeading
        title={METRICS[metric].label}
        unit={metricUnit(metric)}
        help={`${metricHelp(metric)} Amber: below mean. Teal: above mean. Missing measurements excluded.`}
      />
      <div className="research-table-scroll">
        <InspectionGroup
          as="table"
          className="research-heatmap"
          aria-label={[METRICS[metric].label, metricUnit(metric)].filter(Boolean).join(' · ')}
        >
          <thead>
            <tr>
              <th scope="col">Trip</th>
              {columns.map(({ persona, density }) => (
                <th scope="col" key={`${persona}-${density}`}>
                  {interestLabel(persona)}
                  <small>
                    {density} {density === 1 ? 'stop' : 'stops'} per day
                  </small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cells.map((trip) => (
              <tr key={trip.id}>
                <th scope="row">{trip.label}</th>
                {trip.cells.map((cell) => (
                  <InspectMark
                    as="td"
                    key={`${cell.persona}-${cell.density}`}
                    first={cell === firstCell}
                    disabled={!cell.n}
                    style={cell.n ? { background: color(cell.mean) } : undefined}
                    label={`${trip.label}, ${interestLabel(cell.persona)}, ${cell.density} stops per day, ${metricText(cell.mean, metric, true)}, ${runCount(cell.n)} measured`}
                    insight={{
                      value:
                        cell.mean === values.mean
                          ? 'At mean'
                          : `${metricDifference(Math.abs(cell.mean - values.mean), metric)} ${cell.mean > values.mean ? 'above' : 'below'} mean`,
                      detail:
                        cell.attempts > cell.n
                          ? `${runCount(cell.attempts - cell.n)} unmeasured`
                          : undefined,
                    }}
                  >
                    {metricText(cell.mean, metric)}
                    <small>
                      {cell.n === cell.attempts
                        ? `${runCount(cell.n)} measured`
                        : `${cell.n} of ${runCount(cell.attempts)} measured`}
                    </small>
                    {cell.n > 1 && (
                      <small className="research-result-range">
                        {cell.min === cell.max
                          ? utility
                            ? 'Same utility score'
                            : 'Same result'
                          : `Range ${metricRange(cell.min, cell.max, metric)}`}
                      </small>
                    )}
                  </InspectMark>
                ))}
              </tr>
            ))}
          </tbody>
        </InspectionGroup>
      </div>
      {values.n > 0 && (
        <div className="research-heatmap-scale" aria-label="Heatmap color scale">
          {values.min === values.max ? (
            <span className="research-heatmap-flat">
              Mean {metricText(values.mean, metric, true)} · No variation
            </span>
          ) : (
            <>
              <div className="research-heatmap-gradient" aria-hidden="true" />
              <div className="research-heatmap-ticks">
                <span>≤ {metricText(low, metric, true)}</span>
                <span>Mean {metricText(values.mean, metric, true)}</span>
                <span>≥ {metricText(high, metric, true)}</span>
              </div>
            </>
          )}
        </div>
      )}
    </figure>
  );
}
Heatmap.propTypes = {
  rows: PropTypes.array.isRequired,
  trips: PropTypes.array.isRequired,
  metric: PropTypes.string.isRequired,
};

export function StatusColumns({ rows, trips }) {
  const categories = [
    ['Complete', (row) => row.completed, '#234a3c'],
    ['Partial', (row) => row.outcome === 'completed' && !row.completed, '#a56b28'],
    ['Failed', (row) => row.outcome === 'failed', '#ac4c43'],
    ['Interrupted', (row) => row.outcome === 'interrupted', '#8c857b'],
  ];
  const values = trips.map((trip) => ({
    ...trip,
    counts: categories.map(
      ([, test]) => rows.filter((row) => row.trip === trip.id && test(row)).length
    ),
  }));
  const max = Math.max(1, ...values.map((row) => row.counts.reduce((a, b) => a + b, 0)));
  return (
    <figure>
      <ChartHeading
        title="Run outcomes"
        help="Complete: every requested stop delivered with valid timing. Finished runs only."
      />
      <div className="research-legend">
        {categories.map(([label, , color]) => (
          <span key={label}>
            <i style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
      <InspectionGroup viewBox="0 0 640 290" role="group" aria-label="Run outcomes by trip type">
        <line x1="48" x2="610" y1="210" y2="210" stroke="#c8bcae" />
        {[0, 0.5, 1].map((ratio) => (
          <g key={ratio}>
            <text x="38" y={214 - ratio * 160} textAnchor="end">
              {format(max * ratio, 0)}
            </text>
            <line x1="48" x2="610" y1={210 - ratio * 160} y2={210 - ratio * 160} stroke="#e8ddd0" />
          </g>
        ))}
        {values.map((row, index) => {
          let base = 210;
          const x = 68 + index * 110;
          return (
            <g key={row.id}>
              {row.counts.map((count, c) => {
                const height = (count / max) * 160;
                base -= height;
                const times = distribution(
                  rows
                    .filter((item) => item.trip === row.id && categories[c][1](item))
                    .map((item) => item.runtime_seconds)
                );
                return (
                  <InspectMark
                    key={c}
                    disabled={!count || (c === 0 && !times.n)}
                    first={
                      row === values.find((item) => item.counts.some(Boolean)) &&
                      c === row.counts.findIndex(Boolean)
                    }
                    label={`${row.label}, ${categories[c][0]}`}
                    insight={{
                      value:
                        c === 0
                          ? `Median ${format(times.median)} s`
                          : `${runCount(count)} ${categories[c][0].toLowerCase()}`,
                      detail:
                        c === 0
                          ? times.max !== times.median
                            ? `Slowest ${format(times.max)} s`
                            : undefined
                          : `${format((count / row.counts.reduce((a, b) => a + b, 0)) * 100)}% of finished runs`,
                    }}
                  >
                    <rect x={x} y={base} width="52" height={height} fill={categories[c][2]} />
                  </InspectMark>
                );
              })}
              <text x={x + 26} y="236" textAnchor="middle" className="research-chart-detail">
                {row.label}
              </text>
              <text x={x + 26} y="252" textAnchor="middle">
                {runCount(row.counts.reduce((a, b) => a + b, 0))}
              </text>
              <text x={x + 26} y="270" textAnchor="middle">
                {row.counts.some(Boolean)
                  ? `${format((row.counts[0] / row.counts.reduce((a, b) => a + b, 0)) * 100)}% complete`
                  : 'Not tested yet'}
              </text>
            </g>
          );
        })}
      </InspectionGroup>
    </figure>
  );
}
StatusColumns.propTypes = { rows: PropTypes.array.isRequired, trips: PropTypes.array.isRequired };

export function RowChart({ rows, trips, metric }) {
  const values = trips.map((trip) => ({
    ...trip,
    ...sample(
      rows.filter((row) => row.trip === trip.id),
      metric
    ),
  }));
  const extent = values.flatMap((row) => [row.min, row.max]).filter(finite);
  const utility = metric.startsWith('utility') && extent.length > 0;
  const low = utility
    ? Math.max(0, Math.floor((Math.min(...extent) - 2) / 5) * 5)
    : Math.min(0, ...extent);
  const high = utility
    ? Math.min(100, Math.ceil((Math.max(...extent) + 2) / 5) * 5)
    : Math.max(1, ...extent);
  const x = (value) => ((value - low) / (high - low)) * 360;
  const unit = metricUnit(metric);
  const display = (value) => metricText(value, metric, true);
  return (
    <figure>
      <ChartHeading
        title={
          metric === 'utility_mean' ? 'Utility score by trip' : `${METRICS[metric].label} by trip`
        }
        unit={`Between runs${unit ? ` · ${unit}` : ''}`}
        help={`${metricHelp(metric)} Thin line: lowest to highest. Thick line: middle 50%. Tick: median. Dot: mean. Descriptive spread, not a confidence interval.`}
      />
      <InspectionGroup
        as="div"
        className="research-trip-chart"
        role="group"
        aria-label={`${METRICS[metric].label} by trip type`}
      >
        {values.map((row) => (
          <div className="research-trip-row" key={row.id}>
            <div className="research-trip-label">
              <span>{row.label}</span>
              <small>{runCount(row.n)} measured</small>
            </div>
            <div>
              <InspectMark
                as="div"
                disabled={!row.n}
                first={row === values.find((value) => value.n)}
                label={`${row.label}, measured range`}
                insight={{
                  value: `Range ${metricRange(row.min, row.max, metric)}`,
                  detail: `Middle 50%: ${metricRange(row.q1, row.q3, metric)}`,
                }}
              >
                <svg viewBox="-6 0 372 26" aria-hidden="true">
                  <line x1="0" x2="360" y1="13" y2="13" stroke="#e8ddd0" />
                  {finite(row.mean) && (
                    <>
                      <line
                        x1={x(row.min)}
                        x2={x(row.max)}
                        y1="13"
                        y2="13"
                        stroke="#557d6f"
                        strokeWidth="2"
                      />
                      <line x1={x(row.min)} x2={x(row.min)} y1="9" y2="17" stroke="#557d6f" />
                      <line x1={x(row.max)} x2={x(row.max)} y1="9" y2="17" stroke="#557d6f" />
                      <line
                        x1={x(row.q1)}
                        x2={x(row.q3)}
                        y1="13"
                        y2="13"
                        stroke="#b4cdc3"
                        strokeWidth="10"
                        strokeLinecap="round"
                      />
                      <line
                        x1={x(row.median)}
                        x2={x(row.median)}
                        y1="4"
                        y2="22"
                        stroke="#234a3c"
                        strokeWidth="2"
                      />
                      <circle
                        cx={x(row.mean)}
                        cy="13"
                        r="4"
                        fill="#a56b28"
                        stroke="#fffdf8"
                        strokeWidth="1.5"
                      />
                    </>
                  )}
                </svg>
              </InspectMark>
              <div className="research-trip-values">
                <span>
                  Mean <strong>{display(row.mean)}</strong>
                </span>
                <span>
                  Median <strong>{display(row.median)}</strong>
                </span>
              </div>
            </div>
          </div>
        ))}
        <div className="research-trip-axis" aria-hidden="true">
          <span>{display(low)}</span>
          <span>{display(high)}</span>
        </div>
      </InspectionGroup>
    </figure>
  );
}

RowChart.propTypes = {
  rows: PropTypes.array.isRequired,
  trips: PropTypes.array.isRequired,
  metric: PropTypes.string.isRequired,
};

export function ResponseCurve({ rows, variants, parameter, metric }) {
  const baseValue = parameter === 'quality_loss' ? 0.1 : 1;
  const conditions = variants
    .filter((row) => row.parameter === parameter || row.id === 'baseline')
    .map((row) => ({ ...row, x: row.id === 'baseline' ? baseValue : row.value }))
    .sort((a, b) => a.x - b.x);
  const series = ['nature', 'entertainment'].map((persona) => ({
    persona,
    points: conditions.map((condition) => ({
      ...sample(
        rows.filter((row) => row.persona === persona && row.variant === condition.id),
        metric
      ),
      x: condition.x,
      conditionId: condition.id,
      change:
        condition.id === 'baseline'
          ? null
          : paired(
              rows.filter((row) => row.persona === persona),
              condition.id,
              metric
            ),
    })),
  }));
  const firstPoint = series.flatMap((row) => row.points).find((point) => point.n);
  const values = series.flatMap((row) => row.points.map((p) => p.mean)).filter(finite);
  if (!values.length) return <p className="research-empty">No results yet.</p>;
  const minX = Math.min(...conditions.map((row) => row.x));
  const maxX = Math.max(...conditions.map((row) => row.x));
  const maxY = metric.startsWith('utility') ? 100 : Math.max(1, ...values) * 1.15;
  const minY = Math.min(0, ...values);
  const x = (v) => 64 + ((v - minX) / (maxX - minX || 1)) * 500;
  const y = (v) => 210 - ((v - minY) / (maxY - minY || 1)) * 160;
  return (
    <figure>
      <figcaption>
        {METRICS[metric].label}
        {metricUnit(metric) && <small>{metricUnit(metric)}</small>}
      </figcaption>
      <div className="research-legend research-personas">
        <span>● Nature</span>
        <span>■ Entertainment</span>
      </div>
      <InspectionGroup
        viewBox="0 0 640 280"
        role="group"
        aria-label={`${METRICS[metric].label} by ${parameter === 'quality_loss' ? 'allowed utility score drop' : 'added driving penalty'}`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <g key={ratio}>
            <line x1="64" x2="564" y1={210 - ratio * 160} y2={210 - ratio * 160} stroke="#e8ddd0" />
            <text x="54" y={214 - ratio * 160} textAnchor="end">
              {metricText(minY + ratio * (maxY - minY), metric)}
            </text>
          </g>
        ))}
        {conditions.map((row) => (
          <text key={row.id} x={x(row.x)} y="234" textAnchor="middle">
            {parameter === 'quality_loss' ? format(row.x * 100) : format(row.x)}
          </text>
        ))}
        {series.map((series, index) => (
          <g
            key={series.persona}
            fill={index ? '#a56b28' : '#234a3c'}
            stroke={index ? '#a56b28' : '#234a3c'}
          >
            {series.points.map((point, i) => {
              const previous = series.points[i - 1];
              return (
                finite(point.mean) && (
                  <g key={point.x}>
                    {previous && finite(previous.mean) && (
                      <line
                        x1={x(previous.x)}
                        x2={x(point.x)}
                        y1={y(previous.mean)}
                        y2={y(point.mean)}
                        strokeWidth="2"
                      />
                    )}
                    <InspectMark
                      key={point.x}
                      first={point === firstPoint}
                      label={`${interestLabel(series.persona)}, ${settingLabel({ id: point.conditionId, parameter, value: point.x })}, mean ${metricText(point.mean, metric, true)}`}
                      insight={
                        point.change?.n
                          ? {
                              value: `${metricDifference(point.change.mean, metric)} vs default settings`,
                              detail: `${point.change.n} matched comparisons`,
                            }
                          : {
                              value: `Median ${metricText(point.median, metric, true)}`,
                              detail: `Middle 50%: ${metricRange(point.q1, point.q3, metric)}`,
                            }
                      }
                    >
                      <circle
                        className="research-point-hit"
                        cx={x(point.x)}
                        cy={y(point.mean)}
                        r="12"
                        fill="transparent"
                        stroke="none"
                      />
                      {index ? (
                        <rect x={x(point.x) - 4} y={y(point.mean) - 4} width="8" height="8"></rect>
                      ) : (
                        <circle cx={x(point.x)} cy={y(point.mean)} r="4"></circle>
                      )}
                    </InspectMark>
                  </g>
                )
              );
            })}
          </g>
        ))}
        <text x="314" y="268" textAnchor="middle">
          {parameter === 'quality_loss'
            ? 'Allowed utility score drop (points)'
            : 'Added driving penalty'}
        </text>
      </InspectionGroup>
    </figure>
  );
}
ResponseCurve.propTypes = {
  rows: PropTypes.array.isRequired,
  variants: PropTypes.array.isRequired,
  parameter: PropTypes.string.isRequired,
  metric: PropTypes.string.isRequired,
};

export function Tradeoff({ rows, trips = [] }) {
  const points = rows.filter(
    (row) => row.completed && finite(row.extra_seconds) && finite(row.utility_mean)
  );
  if (!points.length)
    return (
      <figure>
        <ChartHeading
          title="Mean utility score vs added driving"
          help="Each point is a complete live trip. Farther right means more driving than the direct route."
        />
        <p className="research-empty">No results yet.</p>
      </figure>
    );
  const low = Math.min(0, ...points.map((row) => row.extra_seconds / 60));
  const high = Math.max(1, ...points.map((row) => row.extra_seconds / 60));
  return (
    <figure>
      <ChartHeading
        title="Mean utility score vs added driving"
        help="Each point is a complete live trip. Farther right means more driving than the direct route."
      />
      <div className="research-legend research-personas">
        <span>● Nature</span>
        <span>● Entertainment</span>
      </div>
      <InspectionGroup
        viewBox="0 0 640 280"
        role="group"
        aria-label="Mean utility score versus added driving scatter plot"
      >
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line x1="64" x2="564" y1={210 - value * 1.6} y2={210 - value * 1.6} stroke="#e8ddd0" />
            <text x="52" y={214 - value * 1.6} textAnchor="end">
              {value}%
            </text>
          </g>
        ))}
        {points.map((row) => (
          <InspectMark
            key={row.id}
            first={row === points[0]}
            label={`${trips.find((trip) => trip.id === row.trip)?.label ?? 'Trip'}, ${interestLabel(row.persona)}, run ${row.repeat}`}
            insight={{
              value: `${format(row.utility_mean * 100)}% mean utility score · ${format(row.extra_seconds / 60)} added minutes`,
              detail: finite(row.extra_meters)
                ? `Added distance: ${format(row.extra_meters / 1609.344)} miles`
                : undefined,
            }}
          >
            <circle
              className="research-point-hit"
              cx={64 + ((row.extra_seconds / 60 - low) / (high - low)) * 500}
              cy={210 - row.utility_mean * 160}
              r="12"
              fill="transparent"
              stroke="none"
            />
            <circle
              cx={64 + ((row.extra_seconds / 60 - low) / (high - low)) * 500}
              cy={210 - row.utility_mean * 160}
              r="4"
              opacity="0.55"
              fill={row.persona === 'nature' ? '#234a3c' : '#a56b28'}
            />
          </InspectMark>
        ))}
        <text x="64" y="234">
          {format(low)}
        </text>
        <text x="564" y="234" textAnchor="end">
          {format(high)}
        </text>
        <text x="314" y="268" textAnchor="middle">
          Added driving (minutes)
        </text>
      </InspectionGroup>
    </figure>
  );
}
Tradeoff.propTypes = { rows: PropTypes.array.isRequired, trips: PropTypes.array };

export function UtilitySpread({ rows }) {
  const descriptionId = useId();
  const scoredRuns = rows
    .filter((row) => row.completed)
    .map((row) =>
      (row.utility_values ?? []).filter((value) => finite(value) && value >= 0 && value <= 1)
    )
    .filter((values) => values.length);
  const values = scoredRuns.flat().map((value) => value * 100);
  const stats = distribution(values);
  const bins = Array.from({ length: 20 }, (_, index) => ({
    low: index * 5,
    high: (index + 1) * 5,
    count: 0,
  }));
  values.forEach((value) => {
    bins[Math.min(19, Math.floor(value / 5))].count += 1;
  });
  const peak = Math.max(1, ...bins.map((bin) => bin.count));
  const step = Math.max(1, Math.ceil(peak / 4));
  const top = step * 4;
  const x = (score) => 64 + score * 7.04;
  const y = (count) => 236 - (count / top) * 180;
  const binLabel = (bin) =>
    `${bin.low}% to ${bin.high === 100 ? '100%' : `below ${bin.high}%`}: ${format(bin.count, 0)} utility ${bin.count === 1 ? 'score' : 'scores'} (${format((bin.count / stats.n) * 100)}%)`;
  const summary = [
    { label: 'Lowest', value: stats.min },
    { label: 'Median', value: stats.median },
    { label: 'Mean', value: stats.mean },
    { label: 'Highest', value: stats.max },
  ];
  return (
    <figure>
      <ChartHeading
        title="Attraction utility scores"
        unit={`${format(stats.n, 0)} utility scores · ${runCount(scoredRuns.length)}`}
        help="Five-point ranges. Attractions count once per run; longer trips contribute more utility scores."
      />
      <div className="research-stat-row">
        {summary.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <strong>
              {format(item.value)}
              {stats.n ? '%' : ''}
            </strong>
          </div>
        ))}
      </div>
      {stats.n ? (
        <div className="research-score-histogram">
          <div className="research-legend" aria-label="Utility score reference lines">
            <span>
              <i className="research-mean-marker" />
              Mean
            </span>
            <span>
              <i className="research-median-marker" />
              Median
            </span>
          </div>
          <InspectionGroup
            viewBox="0 0 800 300"
            role="group"
            aria-label="Distribution of attraction utility scores"
            aria-describedby={descriptionId}
          >
            <desc id={descriptionId}>{bins.map(binLabel).join('; ')}</desc>
            <text x="64" y="24">
              Utility score count
            </text>
            {[0, 1, 2, 3, 4].map((index) => (
              <g key={index}>
                <line x1="64" x2="768" y1={y(index * step)} y2={y(index * step)} stroke="#e8ddd0" />
                <text x="54" y={y(index * step) + 4} textAnchor="end">
                  {format(index * step, 0)}
                </text>
              </g>
            ))}
            {bins.map((bin) => (
              <InspectMark
                key={bin.low}
                first={bin === bins.find((value) => value.count)}
                disabled={!bin.count}
                label={binLabel(bin)}
                insight={{
                  value: `${bin.low}–${bin.high}% · ${format((bin.count / stats.n) * 100)}% of utility scores`,
                }}
              >
                <rect
                  x={x(bin.low) + 2}
                  y={y(bin.count)}
                  width="31.2"
                  height={236 - y(bin.count)}
                  fill="#557d6f"
                  rx="2"
                />
                {bin.count > 0 && (
                  <text x={x(bin.low + 2.5)} y={y(bin.count) - 7} textAnchor="middle">
                    {format(bin.count, 0)}
                  </text>
                )}
              </InspectMark>
            ))}
            <line
              x1={x(stats.mean)}
              x2={x(stats.mean)}
              y1="46"
              y2="236"
              stroke="#ad7229"
              strokeWidth="2"
            />
            <line
              x1={x(stats.median)}
              x2={x(stats.median)}
              y1="46"
              y2="236"
              stroke="#775b87"
              strokeWidth="2"
              strokeDasharray="5 4"
            />
            {[0, 20, 40, 60, 80, 100].map((score) => (
              <text key={score} x={x(score)} y="259" textAnchor="middle">
                {score}%
              </text>
            ))}
            <text x="416" y="288" textAnchor="middle">
              Utility score
            </text>
          </InspectionGroup>
          <p className="research-muted research-score-middle">
            Middle 50% of utility scores: {format(stats.q1)}–{format(stats.q3)}%
          </p>
        </div>
      ) : (
        <p className="research-empty">No utility scores yet.</p>
      )}
    </figure>
  );
}
UtilitySpread.propTypes = { rows: PropTypes.array.isRequired };
