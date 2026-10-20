import PropTypes from 'prop-types';
import { ChartHeading } from './ResearchInfo';
import { distribution, finite, format, metricHelp, METRICS, sample } from './researchData';

export function Heatmap({ rows, trips, metric }) {
  const range = sample(rows, metric);
  const maximum = metric.startsWith('utility')
    ? 100
    : Math.max(1e-6, Math.abs(range.min ?? 0), Math.abs(range.max ?? 0));
  const columns = ['nature', 'entertainment'].flatMap((persona) =>
    [1, 2, 3].map((density) => ({ persona, density }))
  );
  return (
    <figure>
      <ChartHeading
        title={METRICS[metric].label}
        unit={METRICS[metric].unit}
        help={`${metricHelp(metric)} Cells show the mean per-run value by trip, persona and stops per target day. n = usable measurements / finished attempts. A dash means missing data. Quality metrics require fully delivered, timing-valid runs; match scores are estimates, not visitor ratings.`}
      />
      <div className="research-table-scroll">
        <table
          className="research-heatmap"
          aria-label={`${METRICS[metric].label} · ${METRICS[metric].unit}`}
        >
          <thead>
            <tr>
              <th scope="col">Trip</th>
              {columns.map(({ persona, density }) => (
                <th scope="col" key={`${persona}-${density}`}>
                  {persona === 'nature' ? 'Nature' : 'Entertainment'}
                  <small>{density} / day</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trips.map((trip) => (
              <tr key={trip.id}>
                <th scope="row">{trip.label}</th>
                {columns.map(({ persona, density }) => {
                  const stats = sample(
                    rows.filter(
                      (row) =>
                        row.trip === trip.id &&
                        row.persona === persona &&
                        row.stops_per_day === density
                    ),
                    metric
                  );
                  const all = rows.filter(
                    (row) =>
                      row.trip === trip.id &&
                      row.persona === persona &&
                      row.stops_per_day === density
                  ).length;
                  return (
                    <td
                      key={`${persona}-${density}`}
                      style={
                        stats.n
                          ? {
                              background: `rgba(${stats.mean < 0 ? '165, 107, 40' : '69, 112, 75'}, ${0.06 + Math.min(1, Math.abs(stats.mean / maximum)) * 0.28})`,
                            }
                          : undefined
                      }
                    >
                      {format(stats.mean, METRICS[metric].digits)}
                      <small>
                        n={stats.n} / {all}
                      </small>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
        help="Finished attempts under the selected filters, including failures and interruptions. Complete means all requested stops were delivered with valid timing. Partial means a finished run did not meet those requirements. Pending runs are excluded."
      />
      <div className="research-legend">
        {categories.map(([label, , color]) => (
          <span key={label}>
            <i style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
      <svg viewBox="0 0 640 260" role="img" aria-label="Run outcomes by trip type">
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
                return (
                  <rect key={c} x={x} y={base} width="52" height={height} fill={categories[c][2]}>
                    <title>
                      {row.label}: {count} {categories[c][0].toLowerCase()}
                    </title>
                  </rect>
                );
              })}
              <text x={x + 26} y="236" textAnchor="middle">
                {row.id.replace('-1d', '').replace('-2d', '').replace('-3d', '').replace('-5d', '')}
              </text>
              <text x={x + 26} y="252" textAnchor="middle">
                n={row.counts.reduce((a, b) => a + b, 0)}
              </text>
            </g>
          );
        })}
      </svg>
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
  const low = Math.min(0, ...values.map((row) => row.mean).filter(finite));
  const high = Math.max(1, ...values.map((row) => row.mean).filter(finite));
  const x = (value) => 200 + ((value - low) / (high - low)) * 360;
  return (
    <figure>
      <ChartHeading
        title="By trip"
        unit={METRICS[metric].unit}
        help={`${metricHelp(metric)} Bars show the mean per-run value for each trip type under the selected filters. n counts assessed runs; missing values are excluded.`}
      />
      <svg viewBox="0 0 640 240" role="img" aria-label={`${METRICS[metric].label} by trip type`}>
        <line x1={x(0)} x2={x(0)} y1="10" y2="210" stroke="#c8bcae" />
        {values.map((row, index) => (
          <g key={row.id}>
            <text x="190" y={32 + index * 39} textAnchor="end">
              {row.label}
            </text>
            {finite(row.mean) && (
              <rect
                x={Math.min(x(0), x(row.mean))}
                y={17 + index * 39}
                width={Math.abs(x(row.mean) - x(0))}
                height="22"
                rx="3"
                fill="#a56b28"
              />
            )}
            <text x={finite(row.mean) ? x(row.mean) + 8 : x(0) + 8} y={32 + index * 39}>
              {format(row.mean, METRICS[metric].digits)} <tspan fill="#776553">n={row.n}</tspan>
            </text>
          </g>
        ))}
        <text x="200" y="230">
          {format(low)}
        </text>
        <text x="560" y="230" textAnchor="end">
          {format(high)} {METRICS[metric].unit}
        </text>
      </svg>
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
    })),
  }));
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
        <small>{METRICS[metric].unit}</small>
      </figcaption>
      <div className="research-legend research-personas">
        <span>● Nature</span>
        <span>■ Entertainment</span>
      </div>
      <svg
        viewBox="0 0 640 280"
        role="img"
        aria-label={`${METRICS[metric].label} response to ${parameter}`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <g key={ratio}>
            <line x1="64" x2="564" y1={210 - ratio * 160} y2={210 - ratio * 160} stroke="#e8ddd0" />
            <text x="54" y={214 - ratio * 160} textAnchor="end">
              {format(minY + ratio * (maxY - minY), METRICS[metric].digits)}
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
                    {index ? (
                      <rect x={x(point.x) - 4} y={y(point.mean) - 4} width="8" height="8">
                        <title>
                          {series.persona}: {format(point.mean)}; n={point.n}; SD={format(point.sd)}
                        </title>
                      </rect>
                    ) : (
                      <circle cx={x(point.x)} cy={y(point.mean)} r="4">
                        <title>
                          {series.persona}: {format(point.mean)}; n={point.n}; SD={format(point.sd)}
                        </title>
                      </circle>
                    )}
                  </g>
                )
              );
            })}
          </g>
        ))}
        <text x="314" y="268" textAnchor="middle">
          {parameter === 'quality_loss'
            ? 'Allowed utility loss (percentage points)'
            : 'Detour weight'}
        </text>
      </svg>
    </figure>
  );
}
ResponseCurve.propTypes = {
  rows: PropTypes.array.isRequired,
  variants: PropTypes.array.isRequired,
  parameter: PropTypes.string.isRequired,
  metric: PropTypes.string.isRequired,
};

export function Tradeoff({ rows }) {
  const points = rows.filter(
    (row) => row.completed && finite(row.extra_seconds) && finite(row.utility_mean)
  );
  if (!points.length)
    return (
      <figure>
        <ChartHeading
          title="Utility vs added driving"
          help="Each point is a fully delivered, timing-valid live trip. Higher means better estimated persona match; farther right means more driving than the direct route. Nature is green; entertainment is amber. Only measured extra driving is plotted."
        />
        <p className="research-empty">No results yet.</p>
      </figure>
    );
  const low = Math.min(0, ...points.map((row) => row.extra_seconds / 60));
  const high = Math.max(1, ...points.map((row) => row.extra_seconds / 60));
  return (
    <figure>
      <ChartHeading
        title="Utility vs added driving"
        help="Each point is a fully delivered, timing-valid live trip. Higher means better estimated persona match; farther right means more driving than the direct route. Nature is green; entertainment is amber. Only measured extra driving is plotted."
      />
      <div className="research-legend research-personas">
        <span>● Nature</span>
        <span>● Entertainment</span>
      </div>
      <svg viewBox="0 0 640 280" role="img" aria-label="Utility versus added driving scatter plot">
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line x1="64" x2="564" y1={210 - value * 1.6} y2={210 - value * 1.6} stroke="#e8ddd0" />
            <text x="52" y={214 - value * 1.6} textAnchor="end">
              {value}%
            </text>
          </g>
        ))}
        {points.map((row) => (
          <circle
            key={row.id}
            cx={64 + ((row.extra_seconds / 60 - low) / (high - low)) * 500}
            cy={210 - row.utility_mean * 160}
            r="4"
            opacity="0.55"
            fill={row.persona === 'nature' ? '#234a3c' : '#a56b28'}
          >
            <title>
              {row.trip} · {row.persona} · {row.stops_per_day}/day · repeat {row.repeat}:{' '}
              {format(row.utility_mean * 100)}%, {format(row.extra_seconds / 60)} min
            </title>
          </circle>
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
      </svg>
    </figure>
  );
}
Tradeoff.propTypes = { rows: PropTypes.array.isRequired };

export function UtilitySpread({ rows }) {
  const values = rows
    .filter((row) => row.completed)
    .flatMap((row) => row.utility_values ?? [])
    .map((value) => value * 100);
  const stats = distribution(values);
  const summary = [
    { label: 'Lowest', value: stats.min },
    { label: 'Median', value: stats.median },
    { label: 'Average', value: stats.mean },
    { label: 'Highest', value: stats.max },
  ];
  return (
    <figure>
      <ChartHeading
        title="Attraction utility"
        unit={`n=${stats.n}`}
        help="Scores pooled across individual attractions in the filtered, fully delivered, timing-valid runs. A repeated attraction counts once per run, so longer trips contribute more observations. Utility estimates persona match; it is not a visitor rating."
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
    </figure>
  );
}
UtilitySpread.propTypes = { rows: PropTypes.array.isRequired };

export function UtilityBoxes({ rows, trips }) {
  const groups = trips.map((trip) => ({
    ...trip,
    ...sample(
      rows.filter((row) => row.trip === trip.id),
      'utility_mean'
    ),
  }));
  const x = (value) => 190 + value * 3.6;
  return (
    <figure>
      <ChartHeading
        title="Repeat variation"
        unit="Utility %"
        help="Distribution of average utility per assessed run. Each box contains the middle 50%; its line marks the median. The ends show the observed minimum and maximum, not confidence intervals. n counts assessed runs. Fixed-data solver repeats measure solver variation, not independent real-world samples."
      />
      <svg viewBox="0 0 640 270" role="img" aria-label="Utility distributions by trip type">
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line x1={x(value)} x2={x(value)} y1="10" y2="230" stroke="#e8ddd0" />
            <text x={x(value)} y="256" textAnchor="middle">
              {value}%
            </text>
          </g>
        ))}
        {groups.map((group, index) => {
          const y = 30 + index * 43;
          return (
            <g key={group.id}>
              <text x="180" y={y + 4} textAnchor="end">
                {group.label}
              </text>
              {group.n ? (
                <g stroke="#234a3c">
                  <line x1={x(group.min)} x2={x(group.max)} y1={y} y2={y} />
                  <rect
                    x={x(group.q1)}
                    y={y - 9}
                    width={Math.max(1, x(group.q3) - x(group.q1))}
                    height="18"
                    fill="#cfddcb"
                  />
                  <line
                    x1={x(group.median)}
                    x2={x(group.median)}
                    y1={y - 9}
                    y2={y + 9}
                    strokeWidth="2"
                  />
                  <circle cx={x(group.min)} cy={y} r="2" fill="#234a3c" />
                  <circle cx={x(group.max)} cy={y} r="2" fill="#234a3c" />
                  <title>
                    n={group.n}; min {format(group.min)}, median {format(group.median)}, max{' '}
                    {format(group.max)}%
                  </title>
                </g>
              ) : null}
              <text x="570" y={y + 4}>
                n={group.n}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
UtilityBoxes.propTypes = { rows: PropTypes.array.isRequired, trips: PropTypes.array.isRequired };
