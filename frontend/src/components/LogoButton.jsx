import PropTypes from 'prop-types';
import BrandLogo from './BrandLogo';
import { useNavigate } from 'react-router-dom';
import './LogoButton.css';

/** Shared home control. The same vector mark is also the browser favicon. */
export default function LogoButton({ wordmark = false }) {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      className={`logo-btn${wordmark ? ' logo-btn--wordmark' : ''}`}
      onClick={() => navigate('/')}
      aria-label="RoadtripsAreFun home"
    >
      <BrandLogo wordmark={wordmark} decorative />
    </button>
  );
}

LogoButton.propTypes = { wordmark: PropTypes.bool };
