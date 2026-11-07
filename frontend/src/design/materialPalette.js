// Material UI 5 needs concrete colors for its color calculations. This bounded
// adapter mirrors tokens.css; parity tests prevent drift from the CSS master.
export const MATERIAL_LIGHT_COLORS = Object.freeze({
  page: '#f4f6f3',
  surface: '#ffffff',
  surfaceRaised: '#edf1ee',
  surfaceInset: '#e0efe8',
  textPrimary: '#172b25',
  textSecondary: '#50635a',
  textDisabled: '#50635a',
  border: '#b7c6bd',
  controlBorder: '#7a8d82',
  accent: '#165b50',
  accentHover: '#10483f',
  onAccent: '#ffffff',
  selected: '#e0efe8',
  error: '#a52428',
  focus: '#175bc1',
});

export const MATERIAL_DARK_COLORS = Object.freeze({
  page: '#111c18',
  surface: '#1c2c25',
  surfaceRaised: '#283d32',
  surfaceInset: '#284d3e',
  textPrimary: '#f1f6f2',
  textSecondary: '#b9cac0',
  textDisabled: '#b9cac0',
  border: '#526b5c',
  controlBorder: '#8ca797',
  accent: '#9bdcc7',
  accentHover: '#bae9d9',
  onAccent: '#102b22',
  selected: '#284d3e',
  error: '#ffb5b7',
  focus: '#a9ceff',
});

export const MATERIAL_DESIGN = Object.freeze({
  font: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
  controlRadius: '1rem',
  sheetRadius: '1.75rem',
  target: 'max(44px, 2.75rem)',
  small: '0.875rem',
  body: '1rem',
  title: '1.25rem',
  display: 'clamp(1.75rem, 5vw, 2.25rem)',
  space3: '0.75rem',
  space4: '1rem',
  weight: 650,
  bodyLeading: 1.5,
  titleLeading: 1.3,
});
