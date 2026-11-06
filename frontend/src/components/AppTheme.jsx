import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import customTheme from './Theme';
import GlobalStyles from './GlobalStyles';
import { useThemeMode } from '../services/themeMode';

export default function AppTheme({ children }) {
  const mode = useThemeMode();
  const theme = useMemo(
    () =>
      mode === 'light'
        ? customTheme
        : createTheme(customTheme, {
            palette: {
              mode: 'dark',
              background: { default: '#111c18', paper: '#1c2c25' },
              text: { primary: '#f1f6f2', secondary: '#b9cac0', disabled: '#8b9d92' },
              cream: { main: '#1c2c25', light: '#111c18', dark: '#40584b' },
              soil: { main: '#f1f6f2' },
              bark: { main: '#b9cac0', dark: '#d3e0d7' },
              sand: { main: '#a5b9ac', light: '#2b4035', dark: '#8b9d92' },
              white: { main: '#1c2c25', light: '#111c18', dark: '#40584b', black: '#f1f6f2' },
            },
            components: {
              MuiPaper: { styleOverrides: { root: { backgroundColor: '#1c2c25' } } },
              MuiTextField: {
                styleOverrides: {
                  root: { '& .MuiOutlinedInput-root': { backgroundColor: '#111c18' } },
                },
              },
            },
          }),
    [mode]
  );
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyles />
      {children}
    </ThemeProvider>
  );
}
AppTheme.propTypes = { children: PropTypes.node };
