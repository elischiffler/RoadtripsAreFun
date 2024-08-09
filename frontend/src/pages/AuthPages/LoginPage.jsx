import React, { useState, useEffect } from "react";
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
import LogoButton from "../../components/LogoButton";
import { signIn } from "../../services/authService";
import "./AuthPage.css";

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

  //Import colors
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--white-main", customTheme.palette.white.main);
    root.style.setProperty("--white-light", customTheme.palette.white.light);
    root.style.setProperty("--white-dark", customTheme.palette.white.dark);
    root.style.setProperty("--white-black", customTheme.palette.white.black);
    root.style.setProperty("--green-main", customTheme.palette.green.main);
  }, []);

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
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
    </ThemeProvider>
  );
};

export default LoginPage;
