import PropTypes from 'prop-types';

function activity(stage, event) {
  if (stage === 'providers.activity') return activity(event.operation, {});
  if (['studio.inputs', 'studio.storage_begin'].includes(stage)) return 'Preparing your trip';
  if (stage === 'studio.endpoints') return 'Locating cities';
  if (['studio.initial_route', 'route.samples'].includes(stage)) return 'Finding the route';
  if (['route.gathering', 'route.detours'].includes(stage) || stage?.startsWith('attractions.'))
    return 'Finding places';
  if (['route.solver', 'route.model', 'route.solution', 'route.selected'].includes(stage))
    return 'Choosing places';
  if (['route.schedule', 'route.overnight'].includes(stage) || stage?.startsWith('hotels.'))
    return 'Planning stays';
  if (['route.final_reroute', 'route.validation'].includes(stage)) return 'Checking the route';
  if (stage === 'studio.itinerary') return 'Building your itinerary';
  if (stage === 'studio.storage_finish') return 'Saving your trip';
  return null;
}

export default function StudioProgress({ events }) {
  const current = events.reduce(
    (label, event) => (event.type === 'progress' ? (activity(event.stage, event) ?? label) : label),
    'Preparing your trip'
  );
  return (
    <div
      className="lab-pending studio-progress"
      role="status"
      aria-label="Current planning activity"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="studio-loading-text">
        {current}
        <span aria-hidden="true">…</span>
      </span>
    </div>
  );
}
StudioProgress.propTypes = { events: PropTypes.arrayOf(PropTypes.object).isRequired };
