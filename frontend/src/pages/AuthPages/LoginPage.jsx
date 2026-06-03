import { useState } from "react";
import { signIn } from "../../services/authService";
import {
  Box,
  Container,
  TextField,
  Button,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import LogoButton from "../../components/LogoButton";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

const LoginPage = () => {

  // initializes all login dynamic state variable
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  // visibility toggle helper function
  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };


  // navigation helper function
  const navigate = useNavigate();

  // Attempt sign in to AWS and navigate or display errors
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
            Don&apos;t have an account?{" "}
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
