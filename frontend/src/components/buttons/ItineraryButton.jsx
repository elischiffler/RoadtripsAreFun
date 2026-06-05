import { Box } from '@mui/material';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import ThemedTooltip from '../ThemedTooltip';
import './ButtonStyles.css';

// Shared progress ring
const ProgressRingIcon = ({ progress, children, disabled }) => {
  const size = 44;
  const radius = 19;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = circumference * Math.min(Math.max(progress, 0), 1);
  const gap = circumference - filled;
  const trackColor = disabled ? 'rgba(160,128,96,0.2)' : 'rgba(196,135,58,0.2)';
  const fillColor = disabled ? 'rgba(160,128,96,0.4)' : 'rgba(196,135,58,0.9)';

  return (
    <Box sx={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg
        width={size}
        height={size}
        style={{ position: 'absolute', top: 0, left: 0 }}
        aria-hidden="true"
      >
        <circle cx={cx} cy={cy} r={radius} fill="none" stroke={trackColor} strokeWidth="2.5" />
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={fillColor}
          strokeWidth="2.5"
          strokeDasharray={`${filled} ${gap}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 0.4s ease' }}
        />
      </svg>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {children}
      </Box>
    </Box>
  );
};

ProgressRingIcon.propTypes = {
  progress: PropTypes.number.isRequired,
  children: PropTypes.node.isRequired,
  disabled: PropTypes.bool,
};

// ItineraryButton — icon-only with progress ring
const ItineraryButton = ({ itinerary, currentStep = 1 }) => {
  const progress = Math.min((currentStep - 1) / 4, 1);

  const button = (
    <Box
      className={`icon-btn${!itinerary ? ' icon-btn--disabled' : ''}`}
      role="button"
      aria-label="View Itinerary"
    >
      <ProgressRingIcon progress={progress} disabled={!itinerary}>
        <FormatListBulletedIcon
          sx={{ fontSize: 20, color: !itinerary ? 'var(--sand-main)' : 'var(--bark-main)' }}
        />
      </ProgressRingIcon>
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
};

export default ItineraryButton;
