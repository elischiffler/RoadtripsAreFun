import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import "bootstrap/dist/css/bootstrap.css";
import { RouterProvider } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import customTheme from "./components/Theme";
import { CssBaseline } from "@mui/material";
import router from "./Router";
import { UserDataProvider } from "./states/UserDataContext";

// Globally setting the css variables
const GlobalStyles = () => {
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--white-main", customTheme.palette.white.main);
    root.style.setProperty("--white-light", customTheme.palette.white.light);
    root.style.setProperty("--white-dark", customTheme.palette.white.dark);
    root.style.setProperty("--white-black", customTheme.palette.white.black);
    root.style.setProperty("--green-main", customTheme.palette.green.main);
  }, []);

  return null;
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <UserDataProvider>
      <ThemeProvider theme={customTheme}>
        <CssBaseline />
        <GlobalStyles />
        <RouterProvider router={router} />
      </ThemeProvider>
    </UserDataProvider>
  </React.StrictMode>
);
