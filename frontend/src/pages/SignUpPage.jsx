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
import { signUp, confirmSignUp } from "../authService"; // Ensure correct path

const SignUpPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [confirmationCode, setConfirmationCode] = useState("");
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false); // Add a loading state
  const navigate = useNavigate(); // Initialize useNavigate

  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleToggleConfirmPasswordVisibility = () => {
    setShowConfirmPassword(!showConfirmPassword);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true); // Set loading state to true

    if (!isConfirmed) {
      if (password !== confirmPassword) {
        alert("Passwords do not match!");
        setIsSubmitting(false); // Set loading state to false
        return;
      }
      try {
        const response = await signUp(email, password);
        console.log("Sign up success: ", response);
        alert("Please check your email for the confirmation code.");
        setIsConfirmed(true); // Set to true to switch to confirmation step
      } catch (error) {
        console.error("Error signing up: ", error);
        alert("Error signing up. Please try again.");
      }
    } else {
      try {
        await confirmSignUp(email, confirmationCode); // Adjust to use the username if needed
        alert("Account confirmed successfully!");
        navigate("/login"); // Redirect to login page or another page after confirmation
      } catch (error) {
        console.error("Error confirming sign up: ", error);
        alert("Error confirming sign up. Please try again.");
      }
    }

    setIsSubmitting(false); // Set loading state to false
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
                    disabled={isSubmitting} // Disable button when submitting
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
                  disabled={isSubmitting} // Disable button when submitting
                >
                  Sign Up
                </Button>
              )}
            </form>
            <Typography variant="body2" align="center" sx={{ mt: 2 }}>
              Already have an account?{" "}
              <Link to="/login" style={{ textDecoration: "underline" }}>
                Sign in
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

export default SignUpPage;
