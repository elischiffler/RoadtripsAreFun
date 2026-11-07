import { expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { URL as NodeURL } from 'node:url';
import { createRoadtripTheme } from '../components/Theme';
import {
  MATERIAL_DESIGN,
  MATERIAL_LIGHT_COLORS,
  MATERIAL_DARK_COLORS,
} from '../design/materialPalette';

const tokens = readFileSync(new NodeURL('../design/tokens.css', import.meta.url), 'utf8');
const [lightSource, darkSource] = tokens.split(":root[data-theme='dark'] .rt-design");
const declarations = (source) =>
  Object.fromEntries(
    [...source.matchAll(/--rt-([\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2]])
  );
const light = declarations(lightSource);
const dark = { ...light, ...declarations(darkSource) };
const colorMapping = {
  page: 'color-page',
  surface: 'color-surface',
  surfaceRaised: 'color-muted',
  surfaceInset: 'color-selected',
  textPrimary: 'color-text',
  textSecondary: 'color-secondary',
  textDisabled: 'color-secondary',
  border: 'color-border',
  controlBorder: 'color-control-border',
  accent: 'color-accent',
  accentHover: 'color-accent-hover',
  onAccent: 'color-on-accent',
  selected: 'color-selected',
  error: 'color-error',
  focus: 'color-focus',
};

it('keeps the bounded Material color and sizing adapter aligned with the CSS master', () => {
  for (const [palette, source] of [
    [MATERIAL_LIGHT_COLORS, light],
    [MATERIAL_DARK_COLORS, dark],
  ]) {
    for (const [key, token] of Object.entries(colorMapping))
      expect(palette[key]).toBe(source[token]);
  }
  for (const [key, token] of Object.entries({
    font: 'font',
    controlRadius: 'radius-control',
    sheetRadius: 'radius-sheet',
    target: 'target-min',
    small: 'text-small',
    body: 'text-body',
    title: 'text-title',
    display: 'text-display',
    space3: 'space-3',
    space4: 'space-4',
  }))
    expect(MATERIAL_DESIGN[key]).toBe(light[token]);
  expect(MATERIAL_DESIGN.weight).toBe(Number(light['weight-strong']));
  expect(MATERIAL_DESIGN.bodyLeading).toBe(Number(light['leading-body']));
  expect(MATERIAL_DESIGN.titleLeading).toBe(Number(light['leading-title']));
});

const luminance = (hex) => {
  const channels = hex
    .match(/[\da-f]{2}/gi)
    .map((value) => parseInt(value, 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
};
const contrast = (a, b) => {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
};

it.each(['light', 'dark'])(
  'uses matching native and Material actions, typography and readable colors in %s mode',
  (mode) => {
    const colors = mode === 'dark' ? MATERIAL_DARK_COLORS : MATERIAL_LIGHT_COLORS;
    const theme = createRoadtripTheme(mode);
    expect(theme.palette.mode).toBe(mode);
    expect(theme.spacing(1)).toBe(`${parseFloat(light['space-2']) * 16}px`);
    expect(theme.palette.primary.main).toBe(colors.accent);
    expect(theme.palette.background.default).toBe(colors.page);
    expect(theme.palette.background.paper).toBe(colors.surface);
    expect(theme.palette.green.main).toBe(colors.accent);
    expect(theme.palette.forest.main).toBe(colors.accent);
    expect(theme.palette.amber.main).toBe(colors.accent);
    expect(theme.typography.h1.fontFamily).toBe(MATERIAL_DESIGN.font);
    expect(theme.typography.body1.fontFamily).toBe(MATERIAL_DESIGN.font);
    const contained = theme.components.MuiButton.styleOverrides.containedPrimary;
    expect(contained.backgroundColor).toBe(colors.accent);
    expect(contained.color).toBe(colors.onAccent);
    expect(contained['&:hover'].backgroundColor).toBe(colors.accentHover);
    expect(theme.components.MuiButton.styleOverrides.root.minHeight).toBe(MATERIAL_DESIGN.target);
    expect(theme.components.MuiDialog.styleOverrides.paper.borderRadius).toBe(
      MATERIAL_DESIGN.sheetRadius
    );
    expect(contrast(colors.accent, colors.onAccent)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.accentHover, colors.onAccent)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.textSecondary, colors.surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.textPrimary, colors.surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.controlBorder, colors.surface)).toBeGreaterThanOrEqual(3);
  }
);
