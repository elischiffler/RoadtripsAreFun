/** Run from any directory with Node 24 and Inkscape installed. No network or AI calls. */
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const publicDir = join(root, 'frontend/public');
const source = readFileSync(join(publicDir, 'favicon.svg'), 'utf8');
const fullBleed = source.replace('rx="32"', '');
// Put the whole pin safely inside the central 80% circle used by app launchers.
const maskable = fullBleed
  .replace(/(  <path)/, '  <g transform="translate(10.24 10.24) scale(0.84)">\n$1')
  .replace('</svg>', '  </g>\n</svg>');
const temp = mkdtempSync(join(tmpdir(), 'roadtrips-brand-'));
const outputs = [
  ['app-icon-192.png', 192, source],
  ['app-icon-512.png', 512, source],
  ['app-icon-maskable-512.png', 512, maskable],
  ['apple-touch-icon.png', 180, fullBleed],
];

try {
  mkdirSync(join(publicDir, 'icons'), { recursive: true });
  for (const [name, size, svg] of outputs) {
    const input = join(temp, `${name}.svg`);
    writeFileSync(input, svg);
    execFileSync('inkscape', [
      input,
      '--export-type=png',
      `--export-width=${size}`,
      `--export-height=${size}`,
      `--export-filename=${join(publicDir, 'icons', name)}`,
    ]);
    console.log(`Generated ${name} (${size} × ${size})`);
  }
} finally {
  rmSync(temp, { recursive: true, force: true });
}
