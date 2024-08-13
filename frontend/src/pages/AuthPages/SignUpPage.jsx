import React from "react";
import {
  Box,
  Container,
  TextField,
  Button,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import LogoButton from "../../components/LogoButton";
import useSignUp from "../../components/useSignUp";
import PasswordRequirement from "./PasswordRequirement";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

const SignUpPage = () => {

  // initialized constants where possible in the 
  const {
    email,
    password,
    confirmPassword,
    confirmationCode,
    isConfirmed,
    isSubmitting,
    showPassword,
    showConfirmPassword,
    setEmail,
    setPassword,
    setConfirmPassword,
    setConfirmationCode,
    handleTogglePasswordVisibility,
    handleToggleConfirmPasswordVisibility,
    handleSubmit,
    passwordValidation,
  } = useSignUp();

  // navigation helper function
  const navigate = useNavigate();

  // handles the AWS interfacing and sign up navigation
  const onSubmit = async (event) => {
    event.preventDefault();
    const success = await handleSubmit();
    if (success && isConfirmed) {
      navigate("/login");
    }
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
          {/* Form to handle the sign ups with state dependent fields */}
          <form onSubmit={onSubmit}>
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
          
          {/* The login redirection link */}
          <Typography variant="body2" align="center" className="link-text">
            Already have an account?{" "}
            <Link to="/login" style={{ textDecoration: "underline" }}>
              Sign in
            </Link>
          </Typography>

          {/* Mapping all the password requirements with toggleable icons */}
          <Box sx={{ mt: 5 }}>
            <Typography variant="body1">Password Requirements:</Typography>
            <Box className="password-requirements">
              {passwordValidation.map(({ fulfilled, text }, index) => (
                <PasswordRequirement
                  key={index}
                  fulfilled={fulfilled}
                  text={text}
                />
              ))}
            </Box>
          </Box>
        </Container>
      </Box>
      <Box className="banner" />
    </Box>
  );
};

export default SignUpPage;
