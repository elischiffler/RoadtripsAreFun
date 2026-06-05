import { Box } from '@mui/material';
import MapIcon from '@mui/icons-material/Map';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import ThemedTooltip from '../ThemedTooltip';
import './ButtonStyles.css';

// Renders a circular progress ring around a child icon.
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

// MapButton — icon-only with progress ring
const MapButton = ({ route, currentStep = 1 }) => {
  const progress = Math.min((currentStep - 1) / 4, 1);

  const button = (
    <Box
      className={`icon-btn${!route ? ' icon-btn--disabled' : ''}`}
      role="button"
      aria-label="View Map"
    >
      <ProgressRingIcon progress={progress} disabled={!route}>
        <MapIcon sx={{ fontSize: 20, color: !route ? 'var(--sand-main)' : 'var(--bark-main)' }} />
      </ProgressRingIcon>
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
};

export default MapButton;
