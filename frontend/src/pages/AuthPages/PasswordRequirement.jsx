import { Box, Typography } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import './AuthPage.css';
import PropTypes from 'prop-types';

const PasswordRequirement = ({ fulfilled, text }) => (
  <Box className="requirement">
    {fulfilled ? (
      <CheckIcon data-testid="password-requirement-check" sx={{ color: 'green' }} />
    ) : (
      <CloseIcon data-testid="password-requirement-close" sx={{ color: 'gray' }} />
    )}
    <Typography variant="body2">{text}</Typography>
  </Box>
);

PasswordRequirement.propTypes = {
  fulfilled: PropTypes.bool.isRequired,
  text: PropTypes.string.isRequired,
};

export default PasswordRequirement;
