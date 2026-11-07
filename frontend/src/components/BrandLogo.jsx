import PropTypes from 'prop-types';
import './BrandLogo.css';

/** Uses the selected route-pin artwork unchanged; decorative inside named controls. */
export default function BrandLogo({ wordmark = false, decorative = false, className = '' }) {
  return (
    <span
      className={`rt-brand${wordmark ? ' rt-brand--wordmark' : ''} ${className}`.trim()}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : 'RoadtripsAreFun'}
      aria-hidden={decorative ? 'true' : undefined}
    >
      <img
        className="logo-image"
        src="/favicon.svg"
        width="40"
        height="40"
        alt=""
        aria-hidden="true"
        draggable="false"
      />
      {wordmark && (
        <span className="rt-brand__type">
          <span className="rt-brand__name">Roadtrips</span>
          <span className="rt-brand__suffix">are fun</span>
        </span>
      )}
    </span>
  );
}

BrandLogo.propTypes = {
  wordmark: PropTypes.bool,
  decorative: PropTypes.bool,
  className: PropTypes.string,
};
