import PropTypes from 'prop-types';
import { INTERESTS } from './setupModel';

export default function PreferenceProfile({ weights, label = 'Suggested interests' }) {
  const ranked = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  return (
    <figure className="setup-profile" aria-label={label}>
      <figcaption>{label}</figcaption>
      <p>
        Your share of interest in each kind of stop. These are editable preferences, not a
        prediction.
      </p>
      <ul>
        {ranked.map(([key, weight]) => (
          <li key={key}>
            <span>{INTERESTS[key]}</span>
            <span className="setup-bar" aria-hidden="true">
              <span style={{ width: weight * 100 + '%' }} />
            </span>
            <span>{(weight * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
PreferenceProfile.propTypes = { weights: PropTypes.object.isRequired, label: PropTypes.string };
