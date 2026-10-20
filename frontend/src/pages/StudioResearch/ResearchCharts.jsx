import PropTypes from 'prop-types';
import { useId } from 'react';
import { ChartHeading } from './ResearchInfo';
import {
  distribution,
  finite,
  format,
  metricHelp,
  METRICS,
  runCount,
  sample,
} from './researchData';

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
        unit={METRICS[metric].unit}
        help={`${metricHelp(metric)} Cells show the average per-run value by trip and interests and stops per target day. The count below each score shows how many finished runs contributed. Runs without usable measurements stay out of the score and its observed range. A dash means missing data. Quality metrics require fully delivered, timing-valid runs; utility scores are estimates, not visitor ratings. Colors are centered on the equally weighted average of populated cells under these filters: amber below, cream at the average, teal above. The color range spans two standard deviations on either side, with a minimum of five score points for utility scores. End labels are color thresholds, not observed extremes. Higher does not mean better for every metric.`}
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
            {cells.map((trip) => (
              <tr key={trip.id}>
                <th scope="row">{trip.label}</th>
                {trip.cells.map((cell) => (
                  <td
                    key={`${cell.persona}-${cell.density}`}
                    style={cell.n ? { background: color(cell.mean) } : undefined}
                    title={
                      cell.n
                        ? `${format(cell.mean - values.mean, METRICS[metric].digits)} ${utility ? 'points' : METRICS[metric].unit} from the average`
                        : 'No usable measurements'
                    }
                  >
                    {format(cell.mean, METRICS[metric].digits)}
                    <small>
                      {cell.n === cell.attempts
                        ? `${runCount(cell.n)} ${utility ? 'scored' : 'measured'}`
                        : `${cell.n} of ${runCount(cell.attempts)} ${utility ? 'scored' : 'measured'}`}
                    </small>
                    {cell.n > 1 && (
                      <small className="research-result-range">
                        {cell.min === cell.max
                          ? utility
                            ? 'Same utility score'
                            : 'Same result'
                          : `Range ${format(cell.min, METRICS[metric].digits)}–${format(cell.max, METRICS[metric].digits)}${METRICS[metric].unit === '%' ? '%' : ` ${METRICS[metric].unit}`}`}
                      </small>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {values.n > 0 && (
        <div className="research-heatmap-scale" aria-label="Heatmap color scale">
          {values.min === values.max ? (
            <span className="research-heatmap-flat">
              Average {format(values.mean, METRICS[metric].digits)} {METRICS[metric].unit} · No
              variation
            </span>
          ) : (
            <>
              <div className="research-heatmap-gradient" aria-hidden="true" />
              <div className="research-heatmap-ticks">
                <span>
                  ≤ {format(low, METRICS[metric].digits)} {METRICS[metric].unit}
                </span>
                <span>
                  Average {format(values.mean, METRICS[metric].digits)} {METRICS[metric].unit}
                </span>
                <span>
                  ≥ {format(high, METRICS[metric].digits)} {METRICS[metric].unit}
                </span>
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
      <svg viewBox="0 0 640 290" role="img" aria-label="Run outcomes by trip type">
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
                {{
                  'short-1d': 'Short day',
                  'medium-2d': 'Two days',
                  'long-3d': 'Three days',
                  'coast-5d': 'Coast to coast',
                  'tight-2d': 'Tight budget',
                }[row.id] ?? row.label}
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
        help={`${metricHelp(metric)} Bars show the mean per-run value for each trip type under the selected filters. The count shows runs with usable measurements; missing values are excluded. Hover a bar for the observed lowest-to-highest range.`}
      />
      <svg viewBox="0 0 640 290" role="img" aria-label={`${METRICS[metric].label} by trip type`}>
        <line x1={x(0)} x2={x(0)} y1="10" y2="250" stroke="#c8bcae" />
        {values.map((row, index) => (
          <g key={row.id}>
            <text x="190" y={28 + index * 47} textAnchor="end">
              {row.label}
            </text>
            <text x="190" y={43 + index * 47} textAnchor="end" className="research-chart-detail">
              {runCount(row.n)} measured
            </text>
            {finite(row.mean) && (
              <rect
                x={Math.min(x(0), x(row.mean))}
                y={15 + index * 47}
                width={Math.abs(x(row.mean) - x(0))}
                height="22"
                rx="3"
                fill="#a56b28"
              >
                <title>
                  {runCount(row.n)} measured; average {format(row.mean, METRICS[metric].digits)}{' '}
                  {METRICS[metric].unit}; observed range {format(row.min, METRICS[metric].digits)}–
                  {format(row.max, METRICS[metric].digits)} {METRICS[metric].unit}
                </title>
              </rect>
            )}
            <text x={finite(row.mean) ? x(row.mean) + 8 : x(0) + 8} y={28 + index * 47}>
              {format(row.mean, METRICS[metric].digits)}
            </text>
          </g>
        ))}
        <text x="200" y="278">
          {format(low)}
        </text>
        <text x="560" y="278" textAnchor="end">
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
        aria-label={`${METRICS[metric].label} by ${parameter === 'quality_loss' ? 'allowed utility score drop' : 'extra driving penalty'}`}
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
                          {series.persona === 'nature' ? 'Nature' : 'Entertainment'}: average{' '}
                          {format(point.mean, METRICS[metric].digits)} {METRICS[metric].unit};{' '}
                          {runCount(point.n)} measured; observed range{' '}
                          {format(point.min, METRICS[metric].digits)}–
                          {format(point.max, METRICS[metric].digits)} {METRICS[metric].unit}
                        </title>
                      </rect>
                    ) : (
                      <circle cx={x(point.x)} cy={y(point.mean)} r="4">
                        <title>
                          {series.persona === 'nature' ? 'Nature' : 'Entertainment'}: average{' '}
                          {format(point.mean, METRICS[metric].digits)} {METRICS[metric].unit};{' '}
                          {runCount(point.n)} measured; observed range{' '}
                          {format(point.min, METRICS[metric].digits)}–
                          {format(point.max, METRICS[metric].digits)} {METRICS[metric].unit}
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
            ? 'Allowed utility score drop (points)'
            : 'Extra driving penalty'}
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

export function Tradeoff({ rows, trips = [] }) {
  const points = rows.filter(
    (row) => row.completed && finite(row.extra_seconds) && finite(row.utility_mean)
  );
  if (!points.length)
    return (
      <figure>
        <ChartHeading
          title="Utility score vs added driving"
          help="Each point is a fully delivered, timing-valid live trip. Higher utility scores mean a closer fit to the selected interests; farther right means more driving than the direct route. Nature is green; entertainment is amber. Only measured extra driving is plotted."
        />
        <p className="research-empty">No results yet.</p>
      </figure>
    );
  const low = Math.min(0, ...points.map((row) => row.extra_seconds / 60));
  const high = Math.max(1, ...points.map((row) => row.extra_seconds / 60));
  return (
    <figure>
      <ChartHeading
        title="Utility score vs added driving"
        help="Each point is a fully delivered, timing-valid live trip. Higher utility scores mean a closer fit to the selected interests; farther right means more driving than the direct route. Nature is green; entertainment is amber. Only measured extra driving is plotted."
      />
      <div className="research-legend research-personas">
        <span>● Nature</span>
        <span>● Entertainment</span>
      </div>
      <svg
        viewBox="0 0 640 280"
        role="img"
        aria-label="Utility score versus added driving scatter plot"
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
          <circle
            key={row.id}
            cx={64 + ((row.extra_seconds / 60 - low) / (high - low)) * 500}
            cy={210 - row.utility_mean * 160}
            r="4"
            opacity="0.55"
            fill={row.persona === 'nature' ? '#234a3c' : '#a56b28'}
          >
            <title>
              {trips.find((trip) => trip.id === row.trip)?.label ?? 'Trip'} ·{' '}
              {row.persona === 'nature' ? 'Nature' : 'Entertainment'} · {row.stops_per_day} stops
              per day · run {row.repeat}: {format(row.utility_mean * 100)}%,{' '}
              {format(row.extra_seconds / 60)} min
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
    { label: 'Average', value: stats.mean },
    { label: 'Highest', value: stats.max },
  ];
  return (
    <figure>
      <ChartHeading
        title="Attraction utility scores"
        unit={`${format(stats.n, 0)} utility scores · ${runCount(scoredRuns.length)}`}
        help="Each bar counts utility scores in a five-point range, from 0% to 100%. The lines mark the average and median. Scores come from the filtered, fully delivered, timing-valid runs. Repeated attractions count once per run, so longer trips contribute more scores. The middle-half range contains the central 50% of scores, not a confidence interval. Utility scores are estimates, not visitor ratings."
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
              <i className="research-average-marker" />
              Average
            </span>
            <span>
              <i className="research-median-marker" />
              Median
            </span>
          </div>
          <svg
            viewBox="0 0 800 300"
            role="img"
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
              <g key={bin.low}>
                <rect
                  x={x(bin.low) + 2}
                  y={y(bin.count)}
                  width="31.2"
                  height={236 - y(bin.count)}
                  fill="#557d6f"
                  rx="2"
                  aria-label={binLabel(bin)}
                >
                  <title>{binLabel(bin)}</title>
                </rect>
                {bin.count > 0 && (
                  <text x={x(bin.low + 2.5)} y={y(bin.count) - 7} textAnchor="middle">
                    {format(bin.count, 0)}
                  </text>
                )}
              </g>
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
          </svg>
          <p className="research-muted research-score-middle">
            Middle half of utility scores: {format(stats.q1)}–{format(stats.q3)}%
          </p>
        </div>
      ) : (
        <p className="research-empty">No utility scores yet.</p>
      )}
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
        title="Consistency across runs"
        unit="Utility score %"
        help="How average utility scores vary between runs. Each box contains the middle 50%; its line marks the median. The ends show the observed minimum and maximum, not confidence intervals. The count shows runs with usable utility scores. Fixed-data solver repeats measure solver variation, not independent real-world samples."
      />
      <svg viewBox="0 0 640 270" role="img" aria-label="Utility score distributions by trip type">
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
                    {runCount(group.n)} scored; lowest {format(group.min)}%, median{' '}
                    {format(group.median)}%, highest {format(group.max)}%
                  </title>
                </g>
              ) : null}
              <text x="570" y={y + 4}>
                {runCount(group.n)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
UtilityBoxes.propTypes = { rows: PropTypes.array.isRequired, trips: PropTypes.array.isRequired };
