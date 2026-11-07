import { useId } from 'react';
import PropTypes from 'prop-types';

export default function PlanningProgress({ progress }) {
  const label = useId();
  return (
    <section className="connected-progress rt-stack" aria-labelledby={label}>
      <h2 id={label} className="rt-title">
        {progress.percent === 100 ? 'Ready for the road' : 'Bringing your trip together'}
      </h2>
      <progress max="100" value={progress.percent} aria-label="Trip planning milestones" />
      <p className="rt-copy" role="status">
        {progress.percent}% · {progress.label}
      </p>
      <p className="rt-caption">Completed milestones, not time remaining.</p>
    </section>
  );
}
PlanningProgress.propTypes = {
  progress: PropTypes.shape({
    percent: PropTypes.number.isRequired,
    label: PropTypes.string.isRequired,
  }).isRequired,
};
