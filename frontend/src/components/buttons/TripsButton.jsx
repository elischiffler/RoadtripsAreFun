import { Box } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Link } from 'react-router-dom';
import ThemedTooltip from '../ThemedTooltip';
import './ButtonStyles.css';

// TripsButton — plain outlined circular back-to-trips button (no progress ring)
const TripsButton = () => {
  return (
    <Link to="/trips" className="icon-btn-link">
      <ThemedTooltip title="Saved trips" placement="right" arrow>
        <span>
          <Box className="icon-btn icon-btn--outlined" aria-label="Saved trips">
            <ArrowBackIcon sx={{ fontSize: 20, color: 'var(--bark-main)' }} />
          </Box>
        </span>
      </ThemedTooltip>
    </Link>
  );
};

export default TripsButton;
