import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';

export default function TripProgress({ progress }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const entries = progress?.entries ?? [];
  const active = entries.findLast((entry) => entry.state === 'started');
  const latest = entries.at(-1);
  const label = active?.label ?? latest?.label ?? 'Getting started';
  const seconds = Math.max(0, Math.floor((now - (progress?.startedAt ?? now)) / 1000));
  const elapsed = seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return (
    <div className="trip-progress">
      <div className="trip-progress-heading" role="status" aria-live="polite">
        <span className="trip-progress-pulse" aria-hidden="true" />
        <strong>{label}…</strong>
      </div>
      <div className="trip-progress-meta">
        <span>{elapsed} elapsed</span>
        <span>Updates as each step runs</span>
      </div>
      {entries.length > 0 && (
        <details className="trip-progress-details">
          <summary>View progress</summary>
          <ol>
            {entries.map((entry, index) => (
              <li key={index} className={`trip-progress-step trip-progress-step--${entry.state}`}>
                <span aria-hidden="true">
                  {entry.state === 'completed' ? '✓' : entry.state === 'failed' ? '!' : '•'}
                </span>
                <span>{entry.label}</span>
                <span className="trip-progress-step-state">
                  {entry.state === 'started'
                    ? 'In progress'
                    : entry.state === 'failed'
                      ? 'Could not finish'
                      : 'Done'}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

TripProgress.propTypes = {
  progress: PropTypes.shape({
    startedAt: PropTypes.number,
    entries: PropTypes.arrayOf(
      PropTypes.shape({
        key: PropTypes.string,
        label: PropTypes.string.isRequired,
        state: PropTypes.string.isRequired,
        durationMs: PropTypes.number,
      })
    ),
  }),
};
