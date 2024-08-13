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
import useLogin from "../../components/useLogin";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

const LoginPage = () => {
  // initializes all logic related to the actual sign-in
  const { username, password, setUsername, setPassword, error, setError, handleSubmit, showPassword, handleTogglePasswordVisibility, } = useLogin();

  // navigation helper function
  const navigate = useNavigate();

  // Attempt sign in to AWS and navigate or display errors
  const onSubmit = async (event) => {
    event.preventDefault();
    const success = await handleSubmit(username, password);
    if (success) {
      navigate("/");
    } else {
      setError("Failed to sign in. Please check your credentials and try again.");
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
          {/* Actual form components design and functionality */}
          <form onSubmit={onSubmit}>
            <TextField
              label="Username or Email"
              variant="outlined"
              fullWidth
              margin="normal"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="text-field"
            />
            <PasswordField 
              label = "Password"
              password= {password}
              onChange={(e) => setPassword(e.target.value)}
              showPassword={showPassword}
              onTogglePasswordVisibility={handleTogglePasswordVisibility}
              className="text-field"
            />
            {error && (
              <Typography
                color="error"
                variant="body2"
                className="error-message"
              >
                {error}
              </Typography>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              className="submit-button"
            >
              Log In
            </Button>
          </form>
          {/* Sign up redirection */}
          <Typography variant="body2" align="center" className="link-text">
            Don't have an account?{" "}
            <Link to="/signup" style={{ textDecoration: "underline" }}>
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
