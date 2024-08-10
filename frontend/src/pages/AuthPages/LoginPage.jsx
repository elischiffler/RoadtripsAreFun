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
import { signIn } from "../../services/authService";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

const LoginPage = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      const authResult = await signIn(username, password);
      if (authResult) {
        navigate("/");
      }
    } catch (error) {
      setError(
        "Failed to sign in. Please check your credentials and try again."
      );
      console.error("Error signing in: ", error);
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
          <form onSubmit={handleSubmit}>
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
