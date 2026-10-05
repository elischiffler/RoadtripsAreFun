import { Box } from '@mui/material';
import PropTypes from 'prop-types';

// Show planning progress through the icon's opacity without covering it with a disk.
const ProgressRevealIcon = ({ progress, children }) => {
  const clamped = Math.min(Math.max(progress, 0), 1);

  return (
    <Box
      sx={{
        width: 44,
        height: 44,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 0.65 + clamped * 0.35,
        transition: 'opacity 0.4s ease',
      }}
    >
      {children}
    </Box>
  );
};

ProgressRevealIcon.propTypes = {
  progress: PropTypes.number.isRequired,
  children: PropTypes.node.isRequired,
};

export default ProgressRevealIcon;
