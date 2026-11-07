import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import customTheme from './Theme';
import GlobalStyles from './GlobalStyles';
import { useThemeMode } from '../services/themeMode';
import { MATERIAL_DARK_COLORS as dark } from '../design/materialPalette';

export default function AppTheme({ children }) {
  const mode = useThemeMode();
  const theme = useMemo(
    () =>
      mode === 'light'
        ? customTheme
        : createTheme(customTheme, {
            palette: {
              mode: 'dark',
              background: { default: dark.page, paper: dark.surface },
              text: {
                primary: dark.textPrimary,
                secondary: dark.textSecondary,
                disabled: dark.textDisabled,
              },
              cream: { main: dark.surface, light: dark.page, dark: dark.surfaceRaised },
              soil: { main: dark.textPrimary },
              bark: { main: dark.textSecondary, dark: dark.textSubtle },
              sand: { main: dark.border, light: dark.surfaceInset, dark: dark.textDisabled },
              white: {
                main: dark.surface,
                light: dark.page,
                dark: dark.surfaceRaised,
                black: dark.textPrimary,
              },
            },
            components: {
              MuiPaper: { styleOverrides: { root: { backgroundColor: dark.surface } } },
              MuiTextField: {
                styleOverrides: {
                  root: { '& .MuiOutlinedInput-root': { backgroundColor: dark.page } },
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
