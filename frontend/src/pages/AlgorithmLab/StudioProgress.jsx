import PropTypes from 'prop-types';

const phases = [
  [
    'inputs',
    'Validate your trip inputs',
    'Your form supplies the dates, travelers, room occupancy, nightly room target, attraction cap and interest weights. The server validates them and normalizes the weights.',
  ],
  [
    'endpoints',
    'Locate the cities',
    'OpenCage resolves the selected cities to coordinates and timezones, so departure and arrival times use local time.',
  ],
  [
    'base',
    'Get the starting road route',
    'Mapbox supplies the direct road geometry and driving time. The planner samples points along that drive to look for nearby attractions.',
  ],
  [
    'candidates',
    'Collect and score nearby places',
    'Live place records supply verified names and coordinates. AI estimates each place’s interest ratings; the backend calculates match = sum(weight × rating). Ratings are estimates, not provider facts.',
  ],
  [
    'selection',
    'Choose attractions with CP-SAT',
    'Candidates need a match of at least 0.60. Each gets a yes/no variable. CP-SAT maximizes integer-scaled match surplus, with a stable tie preference, under your attraction cap and at most one choice per route sample.',
  ],
  [
    'schedule',
    'Schedule visits and overnight stays',
    'A separate scheduler places visits into driving days. If an overnight stay is needed, dated Google Hotels offers provide room prices for your actual occupancy, checked against the nightly room target.',
  ],
  [
    'roads',
    'Check the final drive',
    'Mapbox recalculates real driving legs through the chosen stops. Local timezones, hotel cutoffs and the destination deadline are checked against those times.',
  ],
  [
    'itinerary',
    'Build the dated itinerary',
    'The itinerary uses the validated route and departure time to calculate each day’s arrivals, visits and departures. Hotel prices and road timing are checked after attraction selection; CP-SAT does not jointly optimize the whole trip.',
  ],
  [
    'saving',
    'Save the result',
    'Store the actual route, itinerary and measurements in this Studio session’s experiment history.',
  ],
];

function phaseFor(stage) {
  if (stage === 'studio.inputs' || stage === 'studio.storage_begin') return 'inputs';
  if (stage === 'studio.endpoints') return 'endpoints';
  if (stage === 'studio.initial_route' || stage === 'route.samples') return 'base';
  if (stage === 'route.gathering' || stage?.startsWith('attractions.')) return 'candidates';
  if (['route.solver', 'route.model', 'route.solution', 'route.selected'].includes(stage))
    return 'selection';
  if (stage === 'route.schedule' || stage === 'route.overnight' || stage?.startsWith('hotels.'))
    return 'schedule';
  if (['route.final_reroute', 'route.validation'].includes(stage)) return 'roads';
  if (stage === 'studio.itinerary') return 'itinerary';
  if (stage === 'studio.storage_finish') return 'saving';
  return null;
}

function describe(event) {
  const query = event.query ? `Route sample ${event.query} of ${event.queries}. ` : '';
  switch (event.stage) {
    case 'studio.inputs':
      return `${event.travelers} traveler${event.travelers === 1 ? '' : 's'}, ${event.rooms} room${event.rooms === 1 ? '' : 's'}, up to ${event.requestedStops} attractions, ${event.attributes} interest weights; $${event.budget} nightly target per room.`;
    case 'route.samples':
      return `${event.queries} drive-time sample points prepared for up to ${event.requestedStops} attractions.`;
    case 'attractions.provider':
      return `${query}Looking up live nearby place records and coordinates.`;
    case 'attractions.ratings':
      return `${query}AI is estimating interest ratings for ${event.candidates} provider-verified places.`;
    case 'attractions.query':
      return `${query}${event.collected} verified and scored candidates collected so far.`;
    case 'attractions.collected':
      return `${query}Scored ${event.name}. ${event.collected} candidates collected.`;
    case 'route.model':
      return `${event.eligible} of ${event.candidates} candidates meet the ${event.threshold} match threshold, across ${event.slots} route slots. Attraction cap: ${event.requestedStops}.`;
    case 'route.solution':
      return `${event.solverStatus}: selected ${event.selected} of ${event.eligible} eligible attractions.`;
    case 'route.selected':
      return `${event.selected} attractions selected; scheduling follows.`;
    case 'route.overnight':
      return `Finding an overnight stop for driving day ${event.day}, search attempt ${event.attempt}.`;
    case 'hotels.search_area':
      return `Checking dated hotel offers near ${event.city}, arriving ${event.checkIn}.`;
    case 'hotels.listings':
      return `${event.candidates} hotel listings found; checking offer details and location.`;
    case 'hotels.collected':
      return `Verified ${event.name}. ${event.hotels} hotel offers collected.`;
    case 'hotels.verified':
      return `${event.hotels} verified hotel offers available for scheduling.`;
    case 'hotels.verify_listing':
      return `Checking hotel identity, location and dated room price; listing attempt ${event.attempt}.`;
    case 'route.final_reroute':
      return `Recalculating the road route through ${event.waypoints} selected stops.`;
    default:
      return null;
  }
}

export default function StudioProgress({ events }) {
  const states = {};
  let current = null;
  let latestDetail = null;
  let elapsed = 0;
  for (const event of events) {
    if (event.type !== 'progress') continue;
    const phase = phaseFor(event.stage);
    if (!phase) continue;
    const resolved = phase;
    current = resolved;
    elapsed = event.elapsedMs ?? elapsed;
    const detail = describe(event);
    if (detail) latestDetail = detail;
    else if (states[resolved]?.detail) latestDetail = states[resolved].detail;
    else latestDetail = null;
    const terminal = [
      'studio.inputs',
      'studio.storage_begin',
      'studio.endpoints',
      'studio.initial_route',
      'route.samples',
      'route.gathering',
      'route.solver',
      'route.selected',
      'route.schedule',
      'route.validation',
      'studio.itinerary',
      'studio.storage_finish',
    ].includes(event.stage);
    const state =
      event.state === 'failed'
        ? 'failed'
        : terminal && event.state === 'completed'
          ? 'completed'
          : 'active';
    states[resolved] = { state, detail: detail || states[resolved]?.detail };
  }
  const activePhase = phases.find(([id]) => id === current);
  return (
    <div className="lab-pending studio-progress">
      <span className="lab-running-dot" />
      <div
        role="status"
        aria-label="Current planning activity"
        aria-live="polite"
        aria-atomic="true"
      >
        <h2>{activePhase?.[1] || 'Connecting to the trip planner'}</h2>
        <p>
          {latestDetail ||
            activePhase?.[2] ||
            'Waiting for the backend to validate your trip and report its first stage.'}
        </p>
      </div>
      {elapsed > 0 && (
        <p className="lab-note">
          Latest server update: {(elapsed / 1000).toFixed(1)} seconds into the run.
        </p>
      )}
      <ol className="studio-progress-steps" aria-label="Live planning stages">
        {phases.map(([id, title, explanation]) => {
          const entry = states[id];
          const state = entry?.state || 'pending';
          return (
            <li key={id} data-state={state} aria-current={current === id ? 'step' : undefined}>
              <details open={current === id}>
                <summary>
                  <span>{title}</span>
                  <small>
                    {state === 'pending'
                      ? 'Waiting'
                      : state === 'completed'
                        ? 'Done'
                        : state === 'failed'
                          ? 'Failed'
                          : 'In progress'}
                  </small>
                </summary>
                <p>{explanation}</p>
                {entry?.detail && <p className="studio-progress-detail">{entry.detail}</p>}
              </details>
            </li>
          );
        })}
      </ol>
      <p className="lab-note">
        Updates come from the running backend. Provider calls can take a while; waiting does not
        mean the solver has failed.
      </p>
    </div>
  );
}

StudioProgress.propTypes = { events: PropTypes.arrayOf(PropTypes.object).isRequired };
