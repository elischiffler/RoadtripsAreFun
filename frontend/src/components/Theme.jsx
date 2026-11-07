import { createTheme } from '@mui/material';
import {
  MATERIAL_DESIGN as design,
  MATERIAL_LIGHT_COLORS,
  MATERIAL_DARK_COLORS,
} from '../design/materialPalette';

/** Bridge older Material components to the shared CSS design system. */
export function createRoadtripTheme(mode = 'light') {
  const colors = mode === 'dark' ? MATERIAL_DARK_COLORS : MATERIAL_LIGHT_COLORS;
  const primary = {
    main: colors.accent,
    light: colors.selected,
    dark: colors.accentHover,
    contrastText: colors.onAccent,
  };
  return createTheme({
    palette: {
      mode,
      primary,
      secondary: primary,
      error: { main: colors.error },
      background: { default: colors.page, paper: colors.surface },
      text: {
        primary: colors.textPrimary,
        secondary: colors.textSecondary,
        disabled: colors.textDisabled,
      },
      divider: colors.border,
      // Retain existing CSS aliases while using the same semantic colors.
      cream: { main: colors.surface, light: colors.page, dark: colors.surfaceRaised },
      sand: { main: colors.border, light: colors.surfaceInset, dark: colors.textDisabled },
      bark: { main: colors.textSecondary, light: colors.border, dark: colors.textPrimary },
      soil: { main: colors.textPrimary },
      forest: primary,
      amber: primary,
      white: {
        main: colors.surface,
        light: colors.page,
        dark: colors.surfaceRaised,
        black: colors.textPrimary,
      },
      green: { main: colors.accent },
    },
    typography: {
      fontFamily: design.font,
      h1: {
        fontSize: design.display,
        fontWeight: design.weight,
        lineHeight: 1.15,
        letterSpacing: '-0.025em',
      },
      h2: {
        fontSize: design.title,
        fontWeight: design.weight,
        lineHeight: design.titleLeading,
        letterSpacing: '-0.015em',
      },
      h3: { fontSize: design.title, fontWeight: design.weight, lineHeight: design.titleLeading },
      h4: { fontSize: design.title, fontWeight: design.weight, lineHeight: design.titleLeading },
      h5: { fontSize: design.title, fontWeight: design.weight, lineHeight: design.titleLeading },
      h6: { fontSize: design.body, fontWeight: design.weight, lineHeight: design.titleLeading },
      body1: { fontSize: design.body, lineHeight: design.bodyLeading },
      body2: { fontSize: design.small, lineHeight: design.bodyLeading },
      button: {
        fontSize: design.body,
        fontWeight: design.weight,
        lineHeight: design.bodyLeading,
        letterSpacing: '0',
        textTransform: 'none',
      },
    },
    spacing: 8,
    shape: { borderRadius: 16 },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: design.target,
            borderRadius: design.controlRadius,
            padding: `${design.space3} ${design.space4}`,
            boxShadow: 'none',
            '&:hover': { boxShadow: 'none' },
            '&.Mui-focusVisible': { outline: `3px solid ${colors.focus}`, outlineOffset: '3px' },
          },
          containedPrimary: {
            backgroundColor: colors.accent,
            color: colors.onAccent,
            '&:hover': { backgroundColor: colors.accentHover },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: { root: { minHeight: design.target, minWidth: design.target } },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: design.controlRadius,
              backgroundColor: colors.surface,
              '& fieldset': { borderColor: colors.controlBorder },
              '&:hover fieldset': { borderColor: colors.textSecondary },
              '&.Mui-focused fieldset': { borderColor: colors.accent },
            },
          },
        },
      },
      MuiPaper: { styleOverrides: { root: { backgroundColor: colors.surface } } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: design.sheetRadius } } },
    },
  });
}

const customTheme = createRoadtripTheme();
export default customTheme;
