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
import customTheme from "../components/Theme";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import LogoButton from "../components/LogoButton";
import SignupBannerBgImg from "../assets/LoginBanner.jpg";
import { signIn } from "../authService"; // Adjust the import path

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
        // Redirect to the home page or another page after successful login
        navigate("/home"); // Adjust the path according to your routing
      }
    } catch (error) {
      setError(
        "Failed to sign in. Please check your credentials and try again."
      );
      console.error("Error signing in: ", error);
    }
  };

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Box
        sx={{
          display: "flex",
          height: "100vh",
        }}
      >
        {/* Form Container */}
        <Box
          sx={{
            flex: "1",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            padding: 4,
            bgcolor: "pink.main",
          }}
        >
          <Container maxWidth="sm">
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
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
              {error && (
                <Typography color="error" variant="body2">
                  {error}
                </Typography>
              )}
              <Button
                type="submit"
                variant="contained"
                color="secondary"
                fullWidth
                sx={{ mt: 2 }}
              >
                Log In
              </Button>
            </form>
            <Typography variant="body2" align="center" sx={{ mt: 2 }}>
              Don't have an account?{" "}
              <Link to="/signup" style={{ textDecoration: "underline" }}>
                Sign up
              </Link>
            </Typography>
          </Container>
        </Box>

        {/* Banner Image */}
        <Box
          sx={{
            flex: "0 0 50%",
            backgroundImage: `url(${SignupBannerBgImg})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
      </Box>
    </ThemeProvider>
  );
};

export default LoginPage;
