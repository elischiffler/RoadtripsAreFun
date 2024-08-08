import React, { useState } from "react";
import {
  Box,
  Container,
  CssBaseline,
  TextField,
  Button,
  Typography,
  IconButton,
  InputAdornment,
  ThemeProvider,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import customTheme from "../../components/Theme";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import LogoButton from "../../components/LogoButton";
import { signUp, confirmSignUp } from "../../services/authService";
import "./AuthPage.css";

const SignUpPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [confirmationCode, setConfirmationCode] = useState("");
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [username, setUsername] = useState("");

  const navigate = useNavigate();

  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleToggleConfirmPasswordVisibility = () => {
    setShowConfirmPassword(!showConfirmPassword);
  };

  const hasUpperCase = /[A-Z]/.test(password);
  const hasLowerCase = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecialChar = /[!@#$%^&*()_+{}\[\]:;"'<>,.?~`-]/.test(password);
  const isLengthValid = password.length >= 8;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);

    if (!isConfirmed) {
      if (password !== confirmPassword) {
        alert("Passwords do not match!");
        setIsSubmitting(false);
        return;
      }
      try {
        const response = await signUp(email, password);
        alert("Please check your email for the confirmation code.");
        setUsername(response.Username);
        setIsConfirmed(true);
      } catch (error) {
        alert("Error signing up. Please try again.");
      }
    } else {
      try {
        await confirmSignUp(username, confirmationCode);
        alert("Account confirmed successfully!");
        navigate("/login");
      } catch (error) {
        alert("Error confirming sign up. Please try again.");
      }
    }

    setIsSubmitting(false);
  };

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Box className="auth-container">
        <Box className="form-container">
          <Container maxWidth="sm">
            <Box className="form-header">
              <Typography variant="h4" gutterBottom>
                {isConfirmed ? "Confirm Your Account" : "Create Your Account"}
              </Typography>
              <LogoButton />
            </Box>
            <form onSubmit={handleSubmit}>
              <TextField
                label="Email"
                type="email"
                variant="outlined"
                fullWidth
                margin="normal"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <TextField
                label="Password"
                type={showPassword ? "text" : "password"}
                variant="outlined"
                fullWidth
                margin="normal"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={handleTogglePasswordVisibility}>
                        {showPassword ? (
                          <VisibilityOffIcon />
                        ) : (
                          <VisibilityIcon />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                label="Confirm Password"
                type={showConfirmPassword ? "text" : "password"}
                variant="outlined"
                fullWidth
                margin="normal"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={handleToggleConfirmPasswordVisibility}
                      >
                        {showConfirmPassword ? (
                          <VisibilityOffIcon />
                        ) : (
                          <VisibilityIcon />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              {isConfirmed ? (
                <>
                  <TextField
                    label="Confirmation Code"
                    variant="outlined"
                    fullWidth
                    margin="normal"
                    required
                    value={confirmationCode}
                    onChange={(e) => setConfirmationCode(e.target.value)}
                  />
                  <Button
                    type="submit"
                    variant="contained"
                    color="secondary"
                    fullWidth
                    sx={{ mt: 2 }}
                    disabled={isSubmitting}
                  >
                    Confirm Account
                  </Button>
                </>
              ) : (
                <Button
                  type="submit"
                  variant="contained"
                  color="secondary"
                  fullWidth
                  sx={{ mt: 2 }}
                  disabled={isSubmitting}
                >
                  Sign Up
                </Button>
              )}
            </form>
            <Typography variant="body2" align="center" className="link-text">
              Already have an account?{" "}
              <Link to="/login" style={{ textDecoration: "underline" }}>
                Sign in
              </Link>
            </Typography>

            <Box sx={{ mt: 5 }}>
              <Typography variant="body1">Password Requirements:</Typography>
              <Box className="password-requirements">
                <Box className="requirement">
                  {hasUpperCase ? (
                    <CheckIcon sx={{ color: "green" }} />
                  ) : (
                    <CloseIcon sx={{ color: "gray" }} />
                  )}
                  <Typography variant="body2">
                    At least one uppercase letter
                  </Typography>
                </Box>
                <Box className="requirement">
                  {hasLowerCase ? (
                    <CheckIcon sx={{ color: "green" }} />
                  ) : (
                    <CloseIcon sx={{ color: "gray" }} />
                  )}
                  <Typography variant="body2">
                    At least one lowercase letter
                  </Typography>
                </Box>
                <Box className="requirement">
                  {hasNumber ? (
                    <CheckIcon sx={{ color: "green" }} />
                  ) : (
                    <CloseIcon sx={{ color: "gray" }} />
                  )}
                  <Typography variant="body2">At least one number</Typography>
                </Box>
                <Box className="requirement">
                  {hasSpecialChar ? (
                    <CheckIcon sx={{ color: "green" }} />
                  ) : (
                    <CloseIcon sx={{ color: "gray" }} />
                  )}
                  <Typography variant="body2">
                    At least one special character
                  </Typography>
                </Box>
                <Box className="requirement">
                  {isLengthValid ? (
                    <CheckIcon sx={{ color: "green" }} />
                  ) : (
                    <CloseIcon sx={{ color: "gray" }} />
                  )}
                  <Typography variant="body2">
                    At least 8 characters long
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Container>
        </Box>
        <Box className="banner" />
      </Box>
    </ThemeProvider>
  );
};

export default SignUpPage;
