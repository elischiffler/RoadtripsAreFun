import React, { useState } from "react";
import {
  Box,
  Container,
  TextField,
  Button,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import LogoButton from "../../components/LogoButton";
import { signUp, confirmSignUp } from "../../services/authService";
import PasswordRequirement from "./PasswordRequirement";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

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
            <PasswordField 
              label = "Password"
              password= {password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onTogglePasswordVisibility={handleTogglePasswordVisibility}
            />
            <PasswordField
              label = "Confirm Password"
              password ={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              showPassword={showConfirmPassword}
              onTogglePasswordVisibility={handleToggleConfirmPasswordVisibility}
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
                  fullWidth
                  className="submit-button"
                  disabled={isSubmitting}
                >
                  Confirm Account
                </Button>
              </>
            ) : (
              <Button
                type="submit"
                variant="contained"
                fullWidth
                sx={{ mt: 2 }}
                disabled={isSubmitting}
                className="submit-button"
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
              <PasswordRequirement
                fulfilled={hasUpperCase}
                text="At least one uppercase letter"
              />
              <PasswordRequirement
                fulfilled={hasLowerCase}
                text="At least one lowercase letter"
              />
              <PasswordRequirement
                fulfilled={hasNumber}
                text="At least one number"
              />
              <PasswordRequirement
                fulfilled={hasSpecialChar}
                text="At least one special character"
              />
              <PasswordRequirement
                fulfilled={isLengthValid}
                text="At least 8 characters long"
              />
            </Box>
          </Box>
        </Container>
      </Box>
      <Box className="banner" />
    </Box>
  );
};

export default SignUpPage;
