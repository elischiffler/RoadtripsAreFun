import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { createRoadtripTheme } from './Theme';
import GlobalStyles from './GlobalStyles';
import { useThemeMode } from '../services/themeMode';

export default function AppTheme({ children }) {
  const mode = useThemeMode();
  const theme = useMemo(() => createRoadtripTheme(mode), [mode]);
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyles />
      {children}
    </ThemeProvider>
  );
}
AppTheme.propTypes = { children: PropTypes.node };
