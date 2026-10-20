import PropTypes from 'prop-types';
import { localTimestamp } from '../../components/placeTiming';
import './TripStats.css';

const known = (value) => typeof value === 'number' && Number.isFinite(value);
const number = (value) =>
  known(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—';
const percent = (value) => (known(value) ? `${number(value * 100)}%` : '—');
const money = (value) =>
  known(value) ? `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—';
const miles = (value) => (known(value) ? `${number(value / 1609.344)} mi` : '—');
const time = (seconds) => {
  if (!known(seconds)) return '—';
  if (seconds === 0) return '0 min';
  if (Math.abs(seconds) < 0.1) return `${seconds < 0 ? '−' : ''}<0.1 sec`;
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
  const candidates = result.explanation?.candidates ?? [];
  const driving = trip.driving ?? {};
  const schedule = trip.schedule ?? {};
  const hotels = trip.hotel_costs ?? {};
  const compliance = trip.schedule_compliance ?? {};
  const stops = trip.stop_fulfillment ?? {};
  const deliveredIds = new Set(
    result.route?.stops
      ?.filter((place) => ['stop', 'attraction'].includes(place.type))
      .map((place) => place.provider_id)
      .filter(Boolean)
  );
  const delivered =
    stops.delivered ??
    (Array.isArray(result.route?.stops)
      ? result.route.stops.filter((place) => ['stop', 'attraction'].includes(place.type)).length
      : null);
  const requested = stops.requested ?? solver.requested_stops ?? result.input_snapshot?.num_stops;
  const balanced = solver.objective_direction === 'minimize';
  const selectedMatch = trip.utility?.selected?.mean ?? (balanced ? solver.average_match : null);
  const directTime = driving.direct_duration_seconds ?? result.direct_route?.duration;
  const finalTime = driving.final_duration_seconds ?? result.route?.duration;
  const directDistance = driving.direct_distance_meters ?? result.direct_route?.distance;
  const finalDistance = driving.final_distance_meters ?? result.route?.distance;
  const extraTime =
    driving.extra_duration_seconds ??
    (known(directTime) && known(finalTime) ? finalTime - directTime : null);
  const extraDistance =
    driving.extra_distance_meters ??
    (known(directDistance) && known(finalDistance) ? finalDistance - directDistance : null);
  const latency = metrics.latency_ms ?? {};
  const discovery = result.explanation?.discovery;
  const candidateCount =
    metrics.candidate_count ?? (result.explanation?.candidates ? candidates.length : null);
  const countChosen = stops.solver_selected ?? solver.selected_count ?? metrics.selected_count;
  const calls = metrics.external_calls ?? {};
  const callLabels = {
    catalog: 'Catalog searches',
    mapbox: 'Road requests',
    language_model: 'AI requests',
    gateway_auth: 'AI sign-ins',
    google_hotels: 'Hotel requests',
    opencage: 'City lookups',
    tripadvisor: 'Past place searches',
  };
  const scoredPlaces = [...candidates].sort(
    (a, b) => Number(Boolean(b.selected)) - Number(Boolean(a.selected))
  );
  return (
    <div className="trip-stats">
      <Figures
        primary
        items={[
          ['Attractions', `${number(delivered)} / ${number(requested)}`],
          ['Match estimate', percent(trip.utility?.delivered?.mean)],
          ['Extra driving', time(extraTime)],
          ['Planning time', time(known(latency.total) ? latency.total / 1000 : null)],
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
          <Bars
            title="Driving distance"
            rows={[
              ['Direct', directDistance],
              ['With stops', finalDistance],
            ]}
            format={miles}
          />
          <Figures
            items={[
              ['Extra distance', miles(extraDistance)],
              [
                'Extra time',
                known(driving.extra_duration_percent)
                  ? `${number(driving.extra_duration_percent)}%`
                  : '—',
              ],
              [
                'Extra distance %',
                known(driving.extra_distance_percent)
                  ? `${number(driving.extra_distance_percent)}%`
                  : '—',
              ],
              ['Longest drive', time(trip.driving_gaps?.maximum_stretch_seconds)],
              [
                'Driving between attractions',
                time(trip.driving_gaps?.maximum_attraction_gap_seconds),
              ],
            ]}
          />
        </section>
        <section className="trip-stats-card" aria-label="Attractions">
          <h2>Attractions</h2>
          <Figures
            items={[
              ['Considered', number(candidateCount)],
              ['Usable matches', number(solver.eligible_count)],
              ['Chosen', number(countChosen)],
              ['On trip', number(delivered)],
            ]}
          />
          <Bars
            title="Match estimates"
            maximum={1}
            format={percent}
            rows={[
              ['Chosen match', selectedMatch],
              ['Trip match', trip.utility?.delivered?.mean],
              ['Best available', balanced ? solver.best_average_match : null],
            ]}
          />
          <Figures
            items={[
              ['Lowest trip match', percent(trip.utility?.delivered?.min)],
              ['Highest trip match', percent(trip.utility?.delivered?.max)],
              ['Middle trip match', percent(trip.utility?.delivered?.median)],
              ['Lowest chosen match', percent(trip.utility?.selected?.min)],
              ['Highest chosen match', percent(trip.utility?.selected?.max)],
              ['Middle chosen match', percent(trip.utility?.selected?.median)],
              [
                'Match difference',
                balanced && known(solver.quality_loss)
                  ? `${number(solver.quality_loss * 100)} points`
                  : '—',
              ],
            ]}
          />
        </section>
      </div>
      {scoredPlaces.length > 0 && (
        <section className="trip-stats-card" aria-label="Place match estimates">
          <div className="trip-stats-heading">
            <h2>Place match estimates</h2>
            {candidates.some(
              (place) => place.source_attribution || place.profile?.source_attribution
            ) && <a href="/catalog-attribution.html">Sources</a>}
          </div>
          <ul className="trip-stats-places" aria-label="Place matches" tabIndex={0}>
            {scoredPlaces.map((place, index) => (
              <li key={`${place.provider_id ?? 'place'}-${index}`}>
                <div>
                  <span>{place.name}</span>
                  <small>
                    {deliveredIds.has(place.provider_id)
                      ? 'On trip'
                      : place.selected
                        ? 'Chosen'
                        : 'Not chosen'}
                  </small>
                </div>
                <Bars
                  title={`${place.name} match`}
                  maximum={1}
                  format={percent}
                  rows={[['Match', place.utility]]}
                />
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="trip-stats-grid">
        <section className="trip-stats-card" aria-label="Hotel quotes (USD)">
          <h2>
            Hotel quotes <small>USD</small>
          </h2>
          <Figures
            items={[
              ['Total', money(hotels.quoted_total_usd)],
              ['Room nights', number(hotels.room_night_count)],
              ['Highest room / night', money(hotels.max_room_night_usd)],
              ['Nightly target used', percent(hotels.budget_utilization)],
              ['Quotes over target', number(hotels.over_target_room_nights)],
              ['Amount over target', money(hotels.above_target_total_usd)],
            ]}
          />
        </section>
        <section className="trip-stats-card" aria-label="Schedule">
          <h2>Schedule</h2>
          <Figures
            items={[
              ['Days', number(schedule.itinerary_days)],
              ['Nights', number(schedule.overnights)],
              ['Total trip time', time(schedule.elapsed_trip_seconds)],
              ['Attraction visits', time(schedule.visit_seconds)],
              ['Overnight rest', time(schedule.overnight_downtime_seconds)],
              ['Late stops', number(compliance.violation_count)],
              ['Stops checked', number(compliance.assessed_stops)],
              ['Smallest time cushion', time(compliance.min_deadline_slack_seconds)],
              ['Arrival', localTimestamp(schedule.final_arrival, schedule.final_timezone) ?? '—'],
            ]}
          />
        </section>
      </div>
      {Object.keys(trip.scenario_target?.daily_active_seconds ?? {}).length > 0 && (
        <section className="trip-stats-card" aria-label="Time on the go">
          <h2>Time on the go</h2>
          <Bars
            title="Daily driving, visits and waiting"
            format={time}
            rows={Object.entries(trip.scenario_target.daily_active_seconds).map(([day, value]) => [
              `Day ${day}`,
              value,
            ])}
          />
        </section>
      )}
      <section className="trip-stats-card" aria-label="Planning">
        <h2>Planning</h2>
        <Figures
          items={[
            ['Search points', number(metrics.discovery_requests ?? discovery?.queries?.length)],
            ['Sections with few places', number(discovery?.sparse_sections?.length)],
            ['Choosing time', time(solver.wall_time_seconds)],
            ...Object.entries(calls)
              .filter(([key]) => key in callLabels)
              .map(([key, value]) => [callLabels[key], number(value)]),
            ['AI response retries', number(metrics.provider_events?.llm_empty_retries)],
          ]}
        />
        <Bars
          title="Planning stage times"
          format={time}
          rows={[
            ['Finding places', known(latency.gathering) ? latency.gathering / 1000 : null],
            ['Choosing places', known(latency.solving) ? latency.solving / 1000 : null],
            ['Building itinerary', known(latency.generation) ? latency.generation / 1000 : null],
            ['Checking route', known(latency.validation) ? latency.validation / 1000 : null],
          ]}
        />
      </section>
    </div>
  );
}
TripStats.propTypes = { result: PropTypes.object.isRequired };
