import { useRef, useState } from 'react';
import { signIn } from '../../services/authService';
import { TextField, Button, Typography } from '@mui/material';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import './AuthPage.css';
import PasswordField from './PasswordField';
import { safeReturnPath } from '../../services/session';

const LoginPage = () => {
  // initializes all login dynamic state variable
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitting = useRef(false);

  // visibility toggle helper function
  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  // navigation helper function
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = location.state?.returnTo ? safeReturnPath(location.state.returnTo) : null;
  const enteringPlanner = returnTo?.split('?')[0] === '/plan';

  // Attempt sign in to AWS and navigate or display errors
  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setIsSubmitting(true);
    setError('');
    try {
      const authResult = await signIn(username, password);
      if (authResult) {
        navigate(returnTo || '/', {
          replace: true,
        });
      }
    } catch {
      setError('Failed to sign in. Please check your credentials and try again.');
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title={enteringPlanner ? 'Plan your trip' : 'Log In'}>
      {enteringPlanner && <Typography className="auth-copy">Log in to save your trip.</Typography>}
      {location.state?.sessionExpired && (
        <Typography role="status">
          Your session expired. Log in to continue. Your trip is kept.
        </Typography>
      )}
      {location.state?.accountCreated && (
        <Typography role="status">Account created. Log in to plan your trip.</Typography>
      )}
      {/* Actual form components design and functionality */}
      <form onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <TextField
          label="Email"
          autoComplete="username"
          variant="outlined"
          fullWidth
          margin="normal"
          required
          disabled={isSubmitting}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="text-field"
        />
        <PasswordField
          label="Password"
          autoComplete="current-password"
          password={password}
          onChange={(e) => setPassword(e.target.value)}
          showPassword={showPassword}
          onTogglePasswordVisibility={handleTogglePasswordVisibility}
          className="text-field"
          disabled={isSubmitting}
        />
        {error && (
          <Typography role="alert" color="error" variant="body2" className="error-message">
            {error}
          </Typography>
        )}
        <Button
          type="submit"
          variant="contained"
          fullWidth
          className="submit-button"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Logging in…' : 'Log In'}
        </Button>
      </form>
      {/* Sign up redirection */}
      <Typography variant="body2" align="center" className="link-text">
        Don&apos;t have an account?{' '}
        <Link to="/signup" state={returnTo ? { returnTo } : undefined}>
          Sign up
        </Link>
      </Typography>
    </AuthLayout>
  );
};

export default LoginPage;
