import PropTypes from 'prop-types';
import RunError from './RunError';
import { useState } from 'react';

const labels = {
  inputs: 'Validated trip inputs',
  endpoints: 'Resolved cities and timezones',
  initial_route: 'Starting road route',
  candidates: 'Verified candidates and scores',
  selection: 'CP-SAT selection',
  scheduling: 'Scheduled visits and hotels',
  reroute: 'Final road route',
  itinerary: 'Dated itinerary',
};
const number = (value, divisor = 1) =>
  Number.isFinite(value)
    ? (value / divisor).toLocaleString(undefined, { maximumFractionDigits: 1 })
    : null;

function retainedData(name, result) {
  const inputs = result.input_snapshot;
  const explanation = result.explanation;
  const route = result.route;
  switch (name) {
    case 'inputs':
      return inputs;
    case 'endpoints':
      return inputs?.start || inputs?.destination
        ? {
            start: inputs.start,
            destination: inputs.destination,
            departure: inputs.start_date,
          }
        : null;
    case 'initial_route':
      return result.direct_route;
    case 'candidates':
      return explanation
        ? {
            effective_weights: explanation.weights,
            query_points: explanation.query_points,
            candidates: explanation.candidates,
          }
        : null;
    case 'selection':
      return explanation?.solver
        ? {
            solver: explanation.solver,
            selected_candidates: explanation.candidates?.filter((candidate) => candidate.selected),
          }
        : null;
    case 'scheduling':
      return route
        ? {
            scheduling_policy: inputs?.scheduling_policy,
            traveler_count: inputs?.traveler_count,
            hotel_rooms: inputs?.hotel_rooms,
            nightly_target_per_room_usd: inputs?.budget,
            stops: route.stops,
            quoted_hotel_total_usd: route.cost,
            warnings: route.warnings,
          }
        : null;
    case 'reroute':
      return route;
    case 'itinerary':
      return result.itinerary;
    default:
      return null;
  }
}

function summary(name, data) {
  if (data == null) return 'No stage data retained';
  switch (name) {
    case 'inputs':
      return `${data.num_stops ?? 'Unknown'} attraction cap · ${data.traveler_count ?? 'Unknown'} travelers · $${data.budget ?? 'Unknown'} / room / night`;
    case 'endpoints':
      return (
        [data.start?.label, data.destination?.label].filter(Boolean).join(' → ') ||
        'Resolved location records'
      );
    case 'initial_route':
    case 'reroute':
      return (
        [
          number(data.distance, 1609.344) && `${number(data.distance, 1609.344)} miles`,
          number(data.duration, 3600) && `${number(data.duration, 3600)} driving hours`,
        ]
          .filter(Boolean)
          .join(' · ') || 'Road route record'
      );
    case 'candidates':
      return `${data.candidates?.length ?? 0} retained candidates${data.query_points ? ` · ${data.query_points.length} route sample${data.query_points.length === 1 ? '' : 's'}` : ''}`;
    case 'selection':
      return `${data.solver.status ?? 'Unknown status'} · ${data.solver.selected_count ?? 'Unknown'} selected / ${data.solver.eligible_count ?? 'Unknown'} eligible`;
    case 'scheduling':
      return `${data.stops?.filter((stop) => ['stop', 'attraction'].includes(stop.type)).length ?? 0} visits · ${data.stops?.filter((stop) => stop.type === 'hotel').length ?? 0} overnight stays`;
    case 'itinerary':
      return `${data.length} itinerary day${data.length === 1 ? '' : 's'}`;
    default:
      return 'Stage record';
  }
}

function StageRow({ stage, result }) {
  const [open, setOpen] = useState(false);
  const data = retainedData(stage.name, result);
  const diagnostic =
    stage.status === 'failed' && result.error
      ? { ...(data || {}), error: result.error, attempts: result.attempts || [] }
      : data;
  const label = labels[stage.name] || stage.name.replaceAll('_', ' ');
  return (
    <li>
      <details onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>
          <span className="lab-stage-summary">
            <strong>{label}</strong>
            <span className="lab-note">{summary(stage.name, data)}</span>
          </span>
          <span className={`lab-status lab-status-${stage.status}`}>
            {stage.status.replaceAll('_', ' ')}
          </span>
        </summary>
        {open && (
          <>
            <p>{stage.detail}</p>
            {stage.status === 'failed' && (
              <RunError error={result.error} attempts={result.attempts} />
            )}
            {stage.name === 'initial_route' && (
              <p className="lab-note">
                Only distance and duration were retained for the starting route.
              </p>
            )}
            {stage.name === 'scheduling' && data && (
              <p className="lab-note">
                Stops and timing come from the final validated route; an intermediate scheduler
                response was not saved.
              </p>
            )}
            {diagnostic == null ? (
              <p className="lab-note">No input or output data was retained for this stage.</p>
            ) : (
              <pre className="lab-stage-json" tabIndex={0} aria-label={`Raw data: ${label}`}>
                <code>{JSON.stringify(diagnostic, null, 2)}</code>
              </pre>
            )}
          </>
        )}
      </details>
    </li>
  );
}
StageRow.propTypes = { stage: PropTypes.object.isRequired, result: PropTypes.object.isRequired };

export default function StageRunData({ result }) {
  return (
    <section aria-labelledby="lab-stage-heading">
      <h2 id="lab-stage-heading">Run data by stage</h2>
      <p className="lab-note">
        Expand a stage to inspect its recorded inputs and outputs as JSON. Raw distances use meters
        and durations use seconds. Geometry uses [longitude, latitude]; place coordinates use
        [latitude, longitude].
      </p>
      <ol className="lab-stages lab-stage-data">
        {result.stages.map((stage) => (
          <StageRow key={stage.name} stage={stage} result={result} />
        ))}
      </ol>
    </section>
  );
}
StageRunData.propTypes = { result: PropTypes.object.isRequired };
