import { useState } from "react";
import { signUp, confirmSignUp } from "../services/authService";

const useSignUp = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmationCode, setConfirmationCode] = useState("");
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [username, setUsername] = useState("");

  const passwordValidation = [
    { fulfilled: /[A-Z]/.test(password), text: "At least one uppercase letter" },
    { fulfilled: /[a-z]/.test(password), text: "At least one lowercase letter" },
    { fulfilled: /[0-9]/.test(password), text: "At least one number" },
    { fulfilled: /[!@#$%^&*()_+{}\[\]:;"'<>,.?~`-]/.test(password), text: "At least one special character" },
    { fulfilled: password.length >= 8, text: "At least 8 characters long" },
  ];

  const handleTogglePasswordVisibility = () => setShowPassword(!showPassword);
  const handleToggleConfirmPasswordVisibility = () => setShowConfirmPassword(!showConfirmPassword);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    if (!isConfirmed) {
      if (password !== confirmPassword) {
        alert("Passwords do not match!");
        setIsSubmitting(false);
        return false;
      }
      try {
        const response = await signUp(email, password);
        alert("Please check your email for the confirmation code.");
        setUsername(response.Username);
        setIsConfirmed(true);
        setIsSubmitting(false)
        return true;
      } catch (error) {
        alert("Error signing up. Please try again.");
        setIsSubmitting(false);
        return false;
      }
    } else {
      try {
        await confirmSignUp(username, confirmationCode);
        alert("Account confirmed successfully!");
        return true;
      } catch (error) {
        alert("Error confirming sign up. Please try again.");
        setIsSubmitting(false);
        return false;
      }
    }
  };

  return {
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
  };
};

export default useSignUp;