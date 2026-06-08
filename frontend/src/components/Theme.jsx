import { createTheme } from '@mui/material';

/**
 * Earthy adventure palette
 *
 * cream    – warm off-white background surfaces
 * sand     – mid-tone warm neutral, cards / sidebars
 * bark     – rich brown, borders and dividers
 * soil     – deep warm brown, text / heavy accents
 * forest   – golden amber, primary action color (buttons, CTAs, links)
 * amber    – golden ochre, highlights / hover states
 */

// Primary palette constants — single source of truth referenced by both
// palette.primary and component styleOverrides.
const PRIMARY_MAIN = '#C4873A';
const PRIMARY_LIGHT = '#D9A55E';
const PRIMARY_DARK = '#9E6420';
const PRIMARY_CONTRAST = '#FBF8F3';

const customTheme = createTheme({
  palette: {
    // --- surface neutrals ---
    cream: {
      main: '#F5EFE6', // warm off-white
      light: '#FBF8F3', // near-white page background
      dark: '#E8DDD0', // slightly deeper warm tone
    },
    sand: {
      main: '#C4A882', // warm tan / medium sand
      light: '#D9C4A8', // lighter sand
      dark: '#A08060', // deeper sand / bark edge
    },
    bark: {
      main: '#7A5C44', // rich medium brown
      light: '#9C7A5E', // lighter bark
      dark: '#5C3D2E', // deep espresso brown
    },
    soil: {
      main: '#3B2A1A', // near-black warm brown (text)
    },

    // --- action colors ---
    forest: {
      main: PRIMARY_MAIN, // golden amber – primary action color
      light: PRIMARY_LIGHT,
      dark: PRIMARY_DARK,
      contrastText: PRIMARY_CONTRAST,
    },
    amber: {
      main: PRIMARY_MAIN, // alias of forest; used by GlobalHeader login button
      light: PRIMARY_LIGHT,
      dark: PRIMARY_DARK,
    },

    // --- MUI semantic aliases ---
    primary: {
      main: PRIMARY_MAIN,
      light: PRIMARY_LIGHT,
      dark: PRIMARY_DARK,
      contrastText: PRIMARY_CONTRAST,
    },
    background: {
      default: '#FBF8F3',
      paper: '#F5EFE6',
    },
    text: {
      primary: '#3B2A1A',
      secondary: '#7A5C44',
      disabled: '#A08060',
    },

    // --- legacy aliases so existing CSS vars still resolve ---
    white: {
      main: '#E8DDD0', // maps to former --white-main  → warm light tan
      light: '#FBF8F3', // maps to former --white-light → near-white cream
      dark: '#C4A882', // maps to former --white-dark  → mid sand
      black: '#5C3D2E', // maps to former --white-black → deep brown
    },
    green: {
      main: '#C4873A', // maps to --green-main → amber
    },
  },

  typography: {
    fontFamily: "'Inter', 'Roboto', sans-serif",

    h1: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontFamily: "'Playfair Display', Georgia, serif",
      fontWeight: 700,
      letterSpacing: '-0.01em',
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
      letterSpacing: '0.01em',
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
      letterSpacing: '0.04em',
      textTransform: 'none',
    },
  },

  shape: {
    borderRadius: 10,
  },

  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          padding: '10px 24px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 12px rgba(58, 42, 26, 0.2)',
          },
        },
        containedPrimary: {
          backgroundColor: PRIMARY_MAIN,
          color: PRIMARY_CONTRAST,
          '&:hover': {
            backgroundColor: PRIMARY_DARK,
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '8px',
            backgroundColor: '#FBF8F3',
            '& fieldset': {
              borderColor: '#C4A882',
            },
            '&:hover fieldset': {
              borderColor: '#7A5C44',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#4A6741',
            },
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#F5EFE6',
        },
      },
    },
  },
});

export default customTheme;
