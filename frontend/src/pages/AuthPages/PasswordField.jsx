import { TextField, InputAdornment, IconButton } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import PropTypes from 'prop-types';

const PasswordField = ({
  label,
  password,
  onChange,
  showPassword,
  onTogglePasswordVisibility,
  ...props
}) => (
  <TextField
    label={label}
    type={showPassword ? 'text' : 'password'}
    variant="outlined"
    fullWidth
    margin="normal"
    required
    value={password}
    onChange={onChange}
    InputProps={{
      endAdornment: (
        <InputAdornment position="end">
          <IconButton onClick={onTogglePasswordVisibility}>
            {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
          </IconButton>
        </InputAdornment>
      ),
    }}
    {...props}
  />
);

PasswordField.propTypes = {
  label: PropTypes.string.isRequired,
  password: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  showPassword: PropTypes.bool.isRequired,
  onTogglePasswordVisibility: PropTypes.func.isRequired,
};

export default PasswordField;
