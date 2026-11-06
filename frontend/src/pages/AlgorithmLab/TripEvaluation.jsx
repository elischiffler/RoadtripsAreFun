import PropTypes from 'prop-types';

const value = (number, unit = '') =>
  typeof number === 'number' && Number.isFinite(number)
    ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`
    : 'Unassessed';

export default function TripEvaluation({ metrics }) {
  const trip = metrics?.trip_evaluation;
  if (!trip) return <p>Trip evaluation is unavailable for this older or unfinished run.</p>;
  const {
    driving,
    stop_fulfillment: stops,
    schedule,
    schedule_compliance: compliance,
    hotel_costs: hotels,
  } = trip;
  return (
    <section aria-label="Trip evaluation">
      <h3>Trip evaluation</h3>
      <p className="lab-note">
        {metrics.metric_version ?? 'Older metric version'} · Evidence:{' '}
        {metrics.evidence_layer?.replaceAll('_', ' ') ?? 'Not recorded'}
      </p>
      <dl className="lab-metrics">
        <div>
          <dt>Selected attraction utility score · mean / min / max / median</dt>
          <dd>
            {['mean', 'min', 'max', 'median']
              .map((key) =>
                value(
                  trip.utility?.selected?.[key] == null ? null : trip.utility.selected[key] * 100,
                  '%'
                )
              )
              .join(' / ')}
          </dd>
        </div>
        <div>
          <dt>Delivered attraction utility score · mean / min / max / median</dt>
          <dd>
            {['mean', 'min', 'max', 'median']
              .map((key) =>
                value(
                  trip.utility?.delivered?.[key] == null ? null : trip.utility.delivered[key] * 100,
                  '%'
                )
              )
              .join(' / ')}
          </dd>
        </div>
        <div>
          <dt>Maximum selection baseline gap</dt>
          <dd>
            {value(
              metrics.selection_measurements?.maximum_baseline_gap_seconds == null
                ? null
                : metrics.selection_measurements.maximum_baseline_gap_seconds / 3600,
              ' hours'
            )}
          </dd>
        </div>
        <div>
          <dt>Longest actual driving stretch</dt>
          <dd>
            {value(
              trip.driving_gaps?.maximum_stretch_seconds == null
                ? null
                : trip.driving_gaps.maximum_stretch_seconds / 3600,
              ' hours'
            )}
          </dd>
        </div>
        <div>
          <dt>Longest attraction-free driving gap</dt>
          <dd>
            {value(
              trip.driving_gaps?.maximum_attraction_gap_seconds == null
                ? null
                : trip.driving_gaps.maximum_attraction_gap_seconds / 3600,
              ' hours'
            )}
          </dd>
        </div>
        <div>
          <dt>Nightly room-target utilization</dt>
          <dd>
            {value(hotels.budget_utilization == null ? null : hotels.budget_utilization * 100, '%')}
          </dd>
        </div>
        <div>
          <dt>Extra driving distance</dt>
          <dd>
            {value(
              driving.extra_distance_meters == null
                ? null
                : driving.extra_distance_meters / 1609.344,
              ' miles'
            )}{' '}
            · {value(driving.extra_distance_percent, '%')}
          </dd>
        </div>
        <div>
          <dt>Extra driving time</dt>
          <dd>
            {value(
              driving.extra_duration_seconds == null ? null : driving.extra_duration_seconds / 3600,
              ' hours'
            )}{' '}
            · {value(driving.extra_duration_percent, '%')}
          </dd>
        </div>
        <div>
          <dt>Attractions delivered / requested</dt>
          <dd>
            {value(stops.delivered)} / {value(stops.requested)} ·{' '}
            {value(stops.ratio == null ? null : stops.ratio * 100, '%')} (
            {value(stops.solver_selected)} solver selected)
          </dd>
        </div>
        <div>
          <dt>Itinerary days / overnights</dt>
          <dd>
            {value(schedule.itinerary_days)} / {value(schedule.overnights)}
          </dd>
        </div>
        {trip.scenario_target?.target_days != null && (
          <div>
            <dt>Scenario days / daily attraction target</dt>
            <dd>
              {value(trip.scenario_target.target_days)} days ·{' '}
              {value(trip.scenario_target.target_stops_per_day)} stops/day · Days:{' '}
              {trip.scenario_target.days_met == null
                ? 'Unassessed'
                : trip.scenario_target.days_met
                  ? 'Pass'
                  : 'Fail'}{' '}
              · Density:{' '}
              {trip.scenario_target.density_met == null
                ? 'Unassessed'
                : trip.scenario_target.density_met
                  ? 'Pass'
                  : 'Fail'}
            </dd>
          </div>
        )}
        <div>
          <dt>Final arrival</dt>
          <dd>
            {schedule.final_arrival ?? 'Unassessed'} {schedule.final_timezone}
          </dd>
        </div>
        <div>
          <dt>Total elapsed trip</dt>
          <dd>
            {value(
              schedule.elapsed_trip_seconds == null ? null : schedule.elapsed_trip_seconds / 3600,
              ' hours'
            )}
          </dd>
        </div>
        <div>
          <dt>Deadline violations</dt>
          <dd>
            {value(compliance.violation_count)} ({value(compliance.assessed_stops)} stops assessed)
          </dd>
        </div>
        <div>
          <dt>Minimum deadline slack</dt>
          <dd>
            {value(
              compliance.min_deadline_slack_seconds == null
                ? null
                : compliance.min_deadline_slack_seconds / 60,
              ' minutes'
            )}
          </dd>
        </div>
        <div>
          <dt>Quoted hotel total (USD)</dt>
          <dd>
            {value(hotels.quoted_total_usd)} · {value(hotels.room_night_count)} room-nights
          </dd>
        </div>
        <div>
          <dt>Highest room-night quote (USD)</dt>
          <dd>{value(hotels.max_room_night_usd)}</dd>
        </div>
        <div>
          <dt>Room-nights above target</dt>
          <dd>
            {value(hotels.over_target_room_nights)} ·{' '}
            {value(hotels.above_target_total_usd, ' USD above target')}
          </dd>
        </div>
        <div>
          <dt>First failed stage</dt>
          <dd>
            {trip.first_failed_stage ?? 'None recorded'} {trip.error_code}
          </dd>
        </div>
      </dl>
      <p className="lab-note">
        Hotel quotes exclude fuel, food and admission; availability and booking are not guaranteed.
        Missing evidence is unassessed.
      </p>
      {[driving, stops, schedule, compliance, hotels].map(
        (part, index) =>
          part.assessment_reason && (
            <p key={index} className="lab-note">
              {['Driving', 'Stop fulfillment', 'Schedule', 'Deadlines', 'Hotel quotes'][index]}:{' '}
              {part.assessment_reason.replaceAll('_', ' ')}.
            </p>
          )
      )}
      {trip.warnings.map((warning, index) => (
        <p className="lab-warning" key={index}>
          {warning}
        </p>
      ))}
    </section>
  );
}

TripEvaluation.propTypes = { metrics: PropTypes.object };
