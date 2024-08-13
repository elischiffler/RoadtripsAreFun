import { useState } from "react";
import { signIn } from "../services/authService";

const useLogin = () => {

    // initializes all login dynamic state variable
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");

    // visibility toggle helper function
    const handleTogglePasswordVisibility = () => {
      setShowPassword(!showPassword);
    };
    
    // handles the AWS sign in logic and catches errors
    const handleSubmit = async (username, password) => {
        try {
            const authResult = await signIn(username, password);
            return !!authResult;
          } catch (error) {
            console.error("Error signing in: ", error);
            setError("Authentication failed.");
            return false;
          }
    };
    

    return { username, password, setUsername, setPassword, error, setError, handleSubmit, showPassword, handleTogglePasswordVisibility };

};

export default useLogin;