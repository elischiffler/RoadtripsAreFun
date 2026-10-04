import PropTypes from 'prop-types';

export default function TripProgress({ progress }) {
  const entries = progress?.entries ?? [];
  const active = entries.findLast((entry) => entry.state === 'started');
  const label = progress?.message ?? active?.label ?? 'Thinking';
  return (
    <span className="trip-progress" role="status" aria-live="polite">
      {label}…
    </span>
  );
}

TripProgress.propTypes = {
  progress: PropTypes.shape({
    message: PropTypes.string,
    entries: PropTypes.arrayOf(
      PropTypes.shape({
        label: PropTypes.string.isRequired,
        state: PropTypes.string.isRequired,
      })
    ),
  }),
};
