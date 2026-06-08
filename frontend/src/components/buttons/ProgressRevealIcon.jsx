import { Box } from '@mui/material';
import PropTypes from 'prop-types';

/**
 * ProgressRevealIcon
 *
 * Wraps a button icon with a circular gray overlay that sweeps away
 * clockwise as `progress` goes from 0 → 1.
 *
 * At progress=0  → fully covered (gray).
 * At progress=1  → fully revealed (no overlay).
 */
const ProgressRevealIcon = ({ progress, children }) => {
  const clamped = Math.min(Math.max(progress, 0), 1);
  const degrees = clamped * 360;

  return (
    <Box sx={{ position: 'relative', width: 44, height: 44, flexShrink: 0 }}>
      {/* The actual icon content */}
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

      {/* Gray overlay, masked away clockwise as progress increases */}
      <Box
        aria-hidden="true"
        sx={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: 'rgba(180, 160, 130, 0.55)',
          // conic-gradient: gray from `degrees` → 360deg, transparent 0 → `degrees`
          // We rotate so the reveal starts from 12 o'clock (top)
          maskImage: `conic-gradient(from -90deg, transparent ${degrees}deg, black ${degrees}deg)`,
          WebkitMaskImage: `conic-gradient(from -90deg, transparent ${degrees}deg, black ${degrees}deg)`,
          transition: 'mask-image 0.4s ease, -webkit-mask-image 0.4s ease',
          pointerEvents: 'none',
        }}
      />
    </Box>
  );
};

ProgressRevealIcon.propTypes = {
  progress: PropTypes.number.isRequired,
  children: PropTypes.node.isRequired,
};

export default ProgressRevealIcon;
