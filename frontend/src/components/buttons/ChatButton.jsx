import { Box } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Link } from 'react-router-dom';
import ThemedTooltip from '../ThemedTooltip';
import './ButtonStyles.css';

// ChatButton — plain outlined circular back-to-chat button (no progress ring)
const ChatButton = () => {
  return (
    <Link to="/chat" className="icon-btn-link">
      <ThemedTooltip title="Back to Chat" placement="right" arrow>
        <span>
          <Box className="icon-btn icon-btn--outlined" role="button" aria-label="Back to Chat">
            <ArrowBackIcon sx={{ fontSize: 20, color: 'var(--bark-main)' }} />
          </Box>
        </span>
      </ThemedTooltip>
    </Link>
  );
};

export default ChatButton;
