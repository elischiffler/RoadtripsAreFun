import React, { useState } from "react";
import { signUp, confirmSignUp } from "../../services/authService";
import {
  Box,
  Container,
  TextField,
  Button,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import LogoButton from "../../components/LogoButton";
import PasswordRequirement from "./PasswordRequirement";
import "./AuthPage.css";
import PasswordField from "./PasswordField";

const SignUpPage = () => {

  //initialize all useState to default values for the different sign up components
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmationCode, setConfirmationCode] = useState("");
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [username, setUsername] = useState("");

  // used an array to package all of the password requirements for ease of mapping
  const passwordValidation = [
    { fulfilled: /[A-Z]/.test(password), text: "At least one uppercase letter" },
    { fulfilled: /[a-z]/.test(password), text: "At least one lowercase letter" },
    { fulfilled: /[0-9]/.test(password), text: "At least one number" },
    { fulfilled: /[!@#$%^&*()_+{}\[\]:;"'<>,.?~`-]/.test(password), text: "At least one special character" },
    { fulfilled: password.length >= 8, text: "At least 8 characters long" },
  ];

  // basic toggle helper functions 
  const handleTogglePasswordVisibility = () => setShowPassword(!showPassword);
  const handleToggleConfirmPasswordVisibility = () => setShowConfirmPassword(!showConfirmPassword);

  // navigation helper function
  const navigate = useNavigate();

  // handles the AWS interfacing and sign up navigation
  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    {/* Determine whether the password has an outstanding confirmation request */}
    if (!isConfirmed) {
      {/* ensure password and confirmation password match then send information to AWS */}
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
      {/* If user is partially signed up send the users confirmation code to finalize account creation and navigate to login */}
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
          {/* Form to handle the sign ups with state dependent fields */}
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
