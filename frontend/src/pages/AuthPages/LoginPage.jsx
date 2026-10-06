import { useState } from 'react';
import { signIn } from '../../services/authService';
import { Box, Container, TextField, Button, Typography } from '@mui/material';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import LogoButton from '../../components/LogoButton';
import './AuthPage.css';
import PasswordField from './PasswordField';
import { safeReturnPath } from '../../services/session';

const LoginPage = () => {
  // initializes all login dynamic state variable
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  // visibility toggle helper function
  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  // navigation helper function
  const navigate = useNavigate();
  const location = useLocation();

  // Attempt sign in to AWS and navigate or display errors
  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      const authResult = await signIn(username, password);
      if (authResult) {
        navigate(location.state?.returnTo ? safeReturnPath(location.state.returnTo) : '/', {
          replace: true,
        });
      }
    } catch (error) {
      setError('Failed to sign in. Please check your credentials and try again.');
    }
  };

  return (
    <Box className="auth-container">
      {/* Form Container */}
      <Box className="form-container">
        <Container maxWidth="sm">
          <Box className="form-header">
            <Typography variant="h4" gutterBottom>
              Log In
            </Typography>
            <LogoButton />
          </Box>
          {location.state?.sessionExpired && (
            <Typography role="status">
              Your session expired. Sign in again to continue. Your unsent message is kept for this
              account.
            </Typography>
          )}
          {/* Actual form components design and functionality */}
          <form onSubmit={handleSubmit}>
            <TextField
              label="Email"
              variant="outlined"
              fullWidth
              margin="normal"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="text-field"
            />
            <PasswordField
              label="Password"
              password={password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onTogglePasswordVisibility={handleTogglePasswordVisibility}
              className="text-field"
            />
            {error && (
              <Typography color="error" variant="body2" className="error-message">
                {error}
              </Typography>
            )}
            <Button type="submit" variant="contained" fullWidth className="submit-button">
              Log In
            </Button>
          </form>
          {/* Sign up redirection */}
          <Typography variant="body2" align="center" className="link-text">
            Don&apos;t have an account?{' '}
            <Link to="/signup" style={{ textDecoration: 'underline' }}>
              Sign up
            </Link>
          </Typography>
        </Container>
      </Box>
      {/* Banner Image */}
      <Box className="banner" />
    </Box>
  );
};

export default LoginPage;
