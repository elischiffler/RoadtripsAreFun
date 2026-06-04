import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
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
    // legacy aliases (all existing CSS uses these)
    root.style.setProperty("--white-main", customTheme.palette.white.main);
    root.style.setProperty("--white-light", customTheme.palette.white.light);
    root.style.setProperty("--white-dark", customTheme.palette.white.dark);
    root.style.setProperty("--white-black", customTheme.palette.white.black);
    root.style.setProperty("--green-main", customTheme.palette.green.main);
    // new earthy semantic tokens
    root.style.setProperty("--cream-main", customTheme.palette.cream.main);
    root.style.setProperty("--cream-light", customTheme.palette.cream.light);
    root.style.setProperty("--cream-dark", customTheme.palette.cream.dark);
    root.style.setProperty("--sand-main", customTheme.palette.sand.main);
    root.style.setProperty("--sand-light", customTheme.palette.sand.light);
    root.style.setProperty("--sand-dark", customTheme.palette.sand.dark);
    root.style.setProperty("--bark-main", customTheme.palette.bark.main);
    root.style.setProperty("--bark-dark", customTheme.palette.bark.dark);
    root.style.setProperty("--soil-main", customTheme.palette.soil.main);
    root.style.setProperty("--forest-main", customTheme.palette.forest.main);
    root.style.setProperty("--forest-light", customTheme.palette.forest.light);
    root.style.setProperty("--forest-dark", customTheme.palette.forest.dark);    root.style.setProperty("--amber-main", customTheme.palette.amber.main);
    root.style.setProperty("--amber-light", customTheme.palette.amber.light);
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
