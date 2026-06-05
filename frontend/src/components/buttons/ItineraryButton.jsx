import { Box } from '@mui/material';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import ThemedTooltip from '../ThemedTooltip';
import ProgressRevealIcon from './ProgressRevealIcon';
import './ButtonStyles.css';

// ItineraryButton — icon-only, with reveal overlay on chat page, plain outlined elsewhere
const ItineraryButton = ({ itinerary, currentStep = 1, showRing = true }) => {
  const progress = Math.min((currentStep - 1) / 4, 1);
  const disabled = !itinerary;

  const icon = (
    <FormatListBulletedIcon
      sx={{ fontSize: 20, color: disabled ? 'var(--sand-main)' : 'var(--bark-main)' }}
    />
  );

  const button = (
    <Box
      className={`icon-btn${disabled ? ' icon-btn--disabled' : ''}`}
      role="button"
      aria-label="View Itinerary"
    >
      {showRing ? <ProgressRevealIcon progress={progress}>{icon}</ProgressRevealIcon> : icon}
    </Box>
  );

  return (
    <Link
      to={itinerary ? '/itinerary' : '#'}
      className="icon-btn-link"
      onClick={(e) => {
        if (!itinerary) e.preventDefault();
      }}
    >
      <ThemedTooltip
        title={itinerary ? 'View Itinerary' : 'Complete your trip first'}
        placement="right"
        arrow
      >
        <span>{button}</span>
      </ThemedTooltip>
    </Link>
  );
};

ItineraryButton.propTypes = {
  itinerary: PropTypes.array,
  currentStep: PropTypes.number,
  showRing: PropTypes.bool,
};

export default ItineraryButton;
