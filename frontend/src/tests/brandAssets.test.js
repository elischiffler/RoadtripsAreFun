import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const read = (path) => readFileSync(resolve(root, path));
const text = (path) => read(path).toString('utf8');
const pngSize = (path) => {
  const bytes = read(path);
  expect(bytes.subarray(1, 4).toString()).toBe('PNG');
  return `${bytes.readUInt32BE(16)}x${bytes.readUInt32BE(20)}`;
};

describe('route-pin brand assets', () => {
  it('uses a self-contained static SVG with the forest and sage palette', () => {
    const svg = new DOMParser().parseFromString(text('public/favicon.svg'), 'image/svg+xml');
    expect(svg.querySelector('parsererror')).toBeNull();
    expect(svg.documentElement.getAttribute('viewBox')).toBe('0 0 128 128');
    expect(svg.querySelector('path').getAttribute('fill')).toBe('#165B50');
    expect(svg.querySelector('rect').getAttribute('fill')).toBe('#D6EAE2');
    expect(svg.querySelector('circle').getAttribute('fill')).toBe('#E6F3EC');
    expect(svg.querySelector('script, image, foreignObject, animate, animateTransform')).toBeNull();
    expect(svg.querySelectorAll('path')).toHaveLength(2);
  });

  it('connects favicon, Apple icon, and install icons to valid local assets', () => {
    const html = new DOMParser().parseFromString(text('index.html'), 'text/html');
    expect(html.querySelector('[rel="icon"]').getAttribute('href')).toBe('/favicon.svg');
    const apple = html.querySelector('[rel="apple-touch-icon"]');
    expect(pngSize(`public${apple.getAttribute('href')}`)).toBe(apple.getAttribute('sizes'));
    const manifestLink = html.querySelector('[rel="manifest"]').getAttribute('href');
    const manifest = JSON.parse(text(`public${manifestLink}`));
    expect(manifest.name).toBe('RoadtripsAreFun');
    expect(manifest.start_url).toBe('/');
    expect(manifest.theme_color).toBe(html.querySelector('[name="theme-color"]').content);
    expect(manifest.icons.map(({ purpose }) => purpose)).toContain('maskable');
    expect(manifest.icons.map(({ sizes }) => sizes)).toEqual(['192x192', '512x512', '512x512']);
    for (const icon of manifest.icons) {
      expect(pngSize(`public${icon.src}`)).toBe(icon.sizes);
      expect(icon.type).toBe('image/png');
    }
  });

  it('keeps a 44px target, visible focus and reduced-motion support without a moving mark', () => {
    const css = text('src/components/LogoButton.css');
    expect(css).toMatch(/min-inline-size:\s*44px/);
    expect(css).toMatch(/min-block-size:\s*44px/);
    expect(css).toContain(':focus-visible');
    expect(css).toContain('@media (prefers-reduced-motion: reduce)');
    expect(css).not.toMatch(/@keyframes|animation:|transform:/);
  });
});
