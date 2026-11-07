// Legacy Material UI 5 computes colors from concrete values, so it cannot use
// the scoped CSS variables directly. Keep this bounded adapter aligned with
// tokens.css; native design components continue to consume the CSS master.
export const MATERIAL_DARK_COLORS = Object.freeze({
  page: '#111c18',
  surface: '#1c2c25',
  surfaceRaised: '#40584b',
  surfaceInset: '#2b4035',
  textPrimary: '#f1f6f2',
  textSecondary: '#b9cac0',
  textSubtle: '#d3e0d7',
  textDisabled: '#8b9d92',
  border: '#a5b9ac',
});
