import { createTheme } from "@mui/material";

/**
 * Earthy adventure palette
 *
 * cream    – warm off-white background surfaces
 * sand     – mid-tone warm neutral, cards / sidebars
 * bark     – rich brown, borders and dividers
 * soil     – deep warm brown, text / heavy accents
 * forest   – muted olive green, primary action color
 * amber    – golden ochre, highlights / hover states
 */
const customTheme = createTheme({
  palette: {
    // --- surface neutrals ---
    cream: {
      main: "#F5EFE6",   // warm off-white
      light: "#FBF8F3",  // near-white page background
      dark: "#E8DDD0",   // slightly deeper warm tone
    },
    sand: {
      main: "#C4A882",   // warm tan / medium sand
      light: "#D9C4A8",  // lighter sand
      dark: "#A08060",   // deeper sand / bark edge
    },
    bark: {
      main: "#7A5C44",   // rich medium brown
      light: "#9C7A5E",  // lighter bark
      dark: "#5C3D2E",   // deep espresso brown
    },
    soil: {
      main: "#3B2A1A",   // near-black warm brown (text)
    },

    // --- action colors ---
    forest: {
      main: "#4A6741",   // muted deep olive green
      light: "#6B8E5E",  // lighter forest green
      dark: "#2E4228",   // dark forest
      contrastText: "#FBF8F3",
    },
    amber: {
      main: "#C4873A",   // warm golden amber
      light: "#D9A55E",
      dark: "#9E6420",
    },

    // --- MUI semantic aliases ---
    primary: {
      main: "#4A6741",
      light: "#6B8E5E",
      dark: "#2E4228",
      contrastText: "#FBF8F3",
    },
    background: {
      default: "#FBF8F3",
      paper: "#F5EFE6",
    },
    text: {
      primary: "#3B2A1A",
      secondary: "#7A5C44",
      disabled: "#A08060",
    },

    // --- legacy aliases so existing CSS vars still resolve ---
    white: {
      main: "#E8DDD0",   // maps to former --white-main  → warm light tan
      light: "#FBF8F3",  // maps to former --white-light → near-white cream
      dark: "#C4A882",   // maps to former --white-dark  → mid sand
      black: "#5C3D2E",  // maps to former --white-black → deep brown
    },
    green: {
      main: "#4A6741",   // maps to former --green-main  → forest green
    },
  },

  typography: {
    fontFamily: "'Inter', 'Roboto', sans-serif",

    h1: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h2: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
      letterSpacing: "-0.01em",
    },
    h3: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
    },
    h4: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
    },
    h5: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 500,
      letterSpacing: "0.01em",
    },
    h6: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 600,
    },
    body1: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 400,
      lineHeight: 1.7,
    },
    body2: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 400,
      lineHeight: 1.6,
    },
    button: {
      fontFamily: "'Inter', sans-serif",
      fontWeight: 600,
      letterSpacing: "0.04em",
      textTransform: "none",
    },
  },

  shape: {
    borderRadius: 10,
  },

  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: "8px",
          padding: "10px 24px",
          boxShadow: "none",
          "&:hover": {
            boxShadow: "0 4px 12px rgba(58, 42, 26, 0.2)",
          },
        },
        containedPrimary: {
          backgroundColor: "#4A6741",
          color: "#FBF8F3",
          "&:hover": {
            backgroundColor: "#2E4228",
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            backgroundColor: "#FBF8F3",
            "& fieldset": {
              borderColor: "#C4A882",
            },
            "&:hover fieldset": {
              borderColor: "#7A5C44",
            },
            "&.Mui-focused fieldset": {
              borderColor: "#4A6741",
            },
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: "#F5EFE6",
        },
      },
    },
  },
});

export default customTheme;
