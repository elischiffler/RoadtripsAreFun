import { useRef, useState } from 'react';
import { signUp, confirmSignUp } from '../../services/authService';
import { TextField, Button, Typography } from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import PasswordRequirement from './PasswordRequirement';
import './AuthPage.css';
import PasswordField from './PasswordField';
import { safeReturnPath } from '../../services/session';

const SignUpPage = () => {
  //initialize all useState to default values for the different sign up components
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [confirmationCode, setConfirmationCode] = useState('');
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const submitting = useRef(false);

  // used an array to package all of the password requirements for ease of mapping
  const passwordValidation = [
    { fulfilled: /[A-Z]/.test(password), text: 'At least one uppercase letter' },
    { fulfilled: /[a-z]/.test(password), text: 'At least one lowercase letter' },
    { fulfilled: /[0-9]/.test(password), text: 'At least one number' },
    {
      fulfilled: /[!@#$%^&*()_+{}[\]:;"'<>,.?~`-]/.test(password),
      text: 'At least one special character',
    },
    { fulfilled: password.length >= 8, text: 'At least 8 characters long' },
  ];

  // basic toggle helper functions
  const handleTogglePasswordVisibility = () => setShowPassword(!showPassword);
  const handleToggleConfirmPasswordVisibility = () => setShowConfirmPassword(!showConfirmPassword);

  // navigation helper function
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = location.state?.returnTo ? safeReturnPath(location.state.returnTo) : null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting.current) return;
    if (!isConfirmed && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    submitting.current = true;
    setIsSubmitting(true);
    setError('');
    try {
      if (!isConfirmed) {
        const response = await signUp(email, password);
        setUsername(response.Username);
        setIsConfirmed(true);
        setPassword('');
        setConfirmPassword('');
      } else {
        await confirmSignUp(username, confirmationCode);
        navigate('/login', { state: { accountCreated: true, ...(returnTo ? { returnTo } : {}) } });
      }
    } catch {
      setError(
        isConfirmed
          ? 'Code could not be confirmed. Try again.'
          : 'Account could not be created. Try again.'
      );
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title={isConfirmed ? 'Confirm Your Account' : 'Create Your Account'}>
      <form onSubmit={handleSubmit} aria-busy={isSubmitting}>
        {isConfirmed ? (
          <>
            <Typography role="status" className="auth-copy">
              Code sent to {email}.
            </Typography>
            <TextField
              label="Confirmation Code"
              autoComplete="one-time-code"
              autoFocus
              variant="outlined"
              fullWidth
              margin="normal"
              required
              disabled={isSubmitting}
              value={confirmationCode}
              onChange={(e) => setConfirmationCode(e.target.value)}
            />
          </>
        ) : (
          <>
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              variant="outlined"
              fullWidth
              margin="normal"
              required
              disabled={isSubmitting}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <PasswordField
              label="Password"
              autoComplete="new-password"
              password={password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onTogglePasswordVisibility={handleTogglePasswordVisibility}
              disabled={isSubmitting}
              inputProps={{ 'aria-describedby': 'password-guidance' }}
            />
            <Typography id="password-guidance" className="auth-copy" variant="body2">
              8+ characters with uppercase, lowercase, a number and a symbol.
            </Typography>
            <PasswordField
              label="Confirm Password"
              autoComplete="new-password"
              password={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              showPassword={showConfirmPassword}
              onTogglePasswordVisibility={handleToggleConfirmPasswordVisibility}
              disabled={isSubmitting}
            />
            <details className="auth-password-details">
              <summary>Password requirements</summary>
              <div className="password-requirements">
                {passwordValidation.map(({ fulfilled, text }) => (
                  <PasswordRequirement key={text} fulfilled={fulfilled} text={text} />
                ))}
              </div>
            </details>
          </>
        )}
        {error && (
          <Typography role="alert" className="error-message">
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
          {isSubmitting
            ? isConfirmed
              ? 'Confirming…'
              : 'Creating account…'
            : isConfirmed
              ? 'Confirm Account'
              : 'Sign Up'}
        </Button>
      </form>
      <Typography variant="body2" align="center" className="link-text">
        Already have an account?{' '}
        <Link to="/login" state={returnTo ? { returnTo } : undefined}>
          Sign in
        </Link>
      </Typography>
    </AuthLayout>
  );
};

export default SignUpPage;
