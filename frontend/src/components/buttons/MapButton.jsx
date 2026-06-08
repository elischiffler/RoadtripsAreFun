import { Box } from '@mui/material';
import MapIcon from '@mui/icons-material/Map';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import ThemedTooltip from '../ThemedTooltip';
import ProgressRevealIcon from './ProgressRevealIcon';
import './ButtonStyles.css';

// MapButton — icon-only, with reveal overlay on chat page, plain outlined elsewhere
const MapButton = ({ route, currentStep = 1, showRing = true }) => {
  const progress = Math.min((currentStep - 1) / 4, 1);
  const disabled = !route;

  const icon = (
    <MapIcon sx={{ fontSize: 20, color: disabled ? 'var(--sand-main)' : 'var(--bark-main)' }} />
  );

  const button = (
    <Box
      className={`icon-btn${disabled ? ' icon-btn--disabled' : ''}`}
      role="button"
      aria-label="View Map"
    >
      {showRing ? <ProgressRevealIcon progress={progress}>{icon}</ProgressRevealIcon> : icon}
    </Box>
  );

  return (
    <Link
      to={route ? '/map' : '#'}
      className="icon-btn-link"
      onClick={(e) => {
        if (!route) e.preventDefault();
      }}
    >
      <ThemedTooltip
        title={route ? 'View Map' : 'Complete your trip first'}
        placement="right"
        arrow
      >
        <span>{button}</span>
      </ThemedTooltip>
    </Link>
  );
};

MapButton.propTypes = {
  route: PropTypes.object,
  currentStep: PropTypes.number,
  showRing: PropTypes.bool,
};

export default MapButton;
