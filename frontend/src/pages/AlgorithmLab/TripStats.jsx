import PropTypes from 'prop-types';
import './TripStats.css';

const known = (value) => typeof value === 'number' && Number.isFinite(value);
const number = (value) =>
  known(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—';
const percent = (value) => (known(value) ? `${number(value * 100)}%` : '—');
const miles = (value) => (known(value) ? `${number(value / 1609.344)} mi` : '—');
const time = (seconds) => {
  if (!known(seconds)) return '—';
  if (seconds === 0) return '0 min';
  if (Math.abs(seconds) < 1) return `${number(seconds * 1000)} ms`;
  if (Math.abs(seconds) < 60) return `${number(seconds)} sec`;
  if (Math.abs(seconds) < 600) {
    const rounded = Math.round(Math.abs(seconds));
    return `${seconds < 0 ? '−' : ''}${Math.floor(rounded / 60)} min${rounded % 60 ? ` ${rounded % 60} sec` : ''}`;
  }
  const minutes = Math.round(Math.abs(seconds) / 60);
  const sign = seconds < 0 ? '−' : '';
  return `${sign}${minutes >= 60 ? `${Math.floor(minutes / 60)} hr ` : ''}${minutes % 60 || minutes < 60 ? `${minutes % 60} min` : ''}`.trim();
};

function Figures({ items, primary = false }) {
  return (
    <dl className={`trip-stats-figures${primary ? ' trip-stats-primary' : ''}`}>
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
Figures.propTypes = { items: PropTypes.array.isRequired, primary: PropTypes.bool };

function Bars({ title, rows, format = number, maximum }) {
  const scale = maximum ?? Math.max(0, ...rows.map(([, value]) => (known(value) ? value : 0)));
  return (
    <div className="trip-stats-bars" role="group" aria-label={title}>
      {rows.map(([label, value]) => (
        <div className="trip-stats-bar-row" key={label}>
          <span>{label}</span>
          <strong>{format(value)}</strong>
          <div className="trip-stats-track" aria-hidden="true">
            {known(value) && scale > 0 && (
              <span style={{ width: `${Math.max(0, Math.min(100, (value / scale) * 100))}%` }} />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
Bars.propTypes = {
  title: PropTypes.string.isRequired,
  rows: PropTypes.array.isRequired,
  format: PropTypes.func,
  maximum: PropTypes.number,
};

export default function TripStats({ result }) {
  const metrics = result.run_record?.metrics ?? {};
  const trip = metrics.trip_evaluation ?? {};
  const solver = result.explanation?.solver ?? {};
  const driving = trip.driving ?? {};
  const stops = trip.stop_fulfillment ?? {};
  const delivered =
    stops.delivered ??
    (Array.isArray(result.route?.stops)
      ? result.route.stops.filter((place) => ['stop', 'attraction'].includes(place.type)).length
      : null);
  const requested = stops.requested ?? solver.requested_stops ?? result.input_snapshot?.num_stops;
  const balanced = solver.objective_direction === 'minimize';
  const directTime = driving.direct_duration_seconds ?? result.direct_route?.duration;
  const finalTime = driving.final_duration_seconds ?? result.route?.duration;
  const extraTime =
    driving.extra_duration_seconds ??
    (known(directTime) && known(finalTime) ? finalTime - directTime : null);
  const directDistance = driving.direct_distance_meters ?? result.direct_route?.distance;
  const finalDistance = driving.final_distance_meters ?? result.route?.distance;
  const extraDistance =
    driving.extra_distance_meters ??
    (known(directDistance) && known(finalDistance) ? finalDistance - directDistance : null);
  const total = metrics.latency_ms?.total;
  return (
    <div className="trip-stats">
      <Figures
        primary
        items={[
          ['Attractions', `${number(delivered)} / ${number(requested)}`],
          ['Utility score', percent(trip.utility?.delivered?.mean)],
          ['Extra driving', time(extraTime)],
          ['Planning time', time(known(total) ? total / 1000 : null)],
        ]}
      />
      <div className="trip-stats-grid">
        <section className="trip-stats-card" aria-label="Driving">
          <h2>Driving</h2>
          <Bars
            title="Driving time"
            rows={[
              ['Direct', directTime],
              ['With stops', finalTime],
            ]}
            format={time}
          />
          <Figures
            items={[
              ['Extra distance', miles(extraDistance)],
              ['Longest gap', time(trip.driving_gaps?.maximum_attraction_gap_seconds)],
            ]}
          />
        </section>
        <section className="trip-stats-card" aria-label="Attractions">
          <h2>Attractions</h2>
          <Figures
            items={[
              [
                'Considered',
                number(metrics.candidate_count ?? result.explanation?.candidates?.length),
              ],
              ['Usable matches', number(solver.eligible_count)],
              [
                'Chosen',
                number(stops.solver_selected ?? solver.selected_count ?? metrics.selected_count),
              ],
              ['Selection time', time(solver.wall_time_seconds)],
            ]}
          />
          <Bars
            title="Utility scores"
            maximum={1}
            format={percent}
            rows={[
              [
                'Chosen utility score',
                trip.utility?.selected?.mean ?? (balanced ? solver.average_match : null),
              ],
              ['Best available', balanced ? solver.best_average_match : null],
            ]}
          />
        </section>
      </div>
    </div>
  );
}
TripStats.propTypes = { result: PropTypes.object.isRequired };
