import { useId } from 'react';
import PropTypes from 'prop-types';
import { ChoiceGroup } from './Controls';

export function StageProgress({ stages, currentId, completedIds = [] }) {
  const labelId = useId();
  const completed = new Set(completedIds);
  const completeCount = stages.filter((stage) => completed.has(stage.id)).length;
  return (
    <div className="rt-stage-progress">
      <p id={labelId} className="rt-caption">
        {completeCount} of {stages.length} stages complete
      </p>
      <progress aria-labelledby={labelId} max={stages.length || 1} value={completeCount} />
      <ol className="rt-stage-list" aria-label="Trip setup stages">
        {stages.map((stage, index) => (
          <li key={stage.id} aria-current={stage.id === currentId ? 'step' : undefined}>
            {index + 1}. {stage.label}
            {completed.has(stage.id) ? ' · Complete' : ''}
          </li>
        ))}
      </ol>
    </div>
  );
}
StageProgress.propTypes = {
  stages: PropTypes.arrayOf(
    PropTypes.shape({ id: PropTypes.string.isRequired, label: PropTypes.string.isRequired })
  ).isRequired,
  currentId: PropTypes.string,
  completedIds: PropTypes.arrayOf(PropTypes.string),
};

/** A view preference, not ARIA tabs: the consumer owns panel visibility. */
export function TripViewSwitch({ value, onChange, name }) {
  return (
    <ChoiceGroup
      legend="Trip view"
      name={name}
      value={value}
      onChange={onChange}
      options={[
        { value: 'itinerary', label: 'Itinerary' },
        { value: 'map', label: 'Map' },
      ]}
    />
  );
}
TripViewSwitch.propTypes = {
  value: PropTypes.oneOf(['itinerary', 'map']).isRequired,
  onChange: PropTypes.func.isRequired,
  name: PropTypes.string,
};

const statusLabels = { complete: 'Visited', current: 'Current stop', upcoming: 'Upcoming' };
export function TripTimeline({ label, items }) {
  return (
    <ol className="rt-timeline" aria-label={label}>
      {items.map((item) => (
        <li
          key={item.id}
          className="rt-timeline__item"
          data-state={item.status || 'upcoming'}
          aria-current={item.status === 'current' ? 'step' : undefined}
        >
          <span className="rt-timeline__marker" aria-hidden="true" />
          <div className="rt-timeline__content">
            <time className="rt-caption" dateTime={item.dateTime}>
              {item.time}
            </time>
            <p className="rt-title">{item.title}</p>
            {item.description && <p className="rt-copy">{item.description}</p>}
            <span className="rt-caption">{statusLabels[item.status || 'upcoming']}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
TripTimeline.propTypes = {
  label: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      time: PropTypes.string.isRequired,
      dateTime: PropTypes.string,
      description: PropTypes.string,
      status: PropTypes.oneOf(['complete', 'current', 'upcoming']),
    })
  ).isRequired,
};
