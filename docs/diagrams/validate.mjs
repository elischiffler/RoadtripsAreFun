// Validates every Mermaid diagram in the docs — both the standalone .mmd sources
// in ./src and the inline ```mermaid``` blocks in the ../*.md files — by parsing
// each with Mermaid itself (under a jsdom DOM so it runs headless in Node).
//
// Usage (from docs/diagrams/):
//   npm install      # first time, pulls mermaid + jsdom
//   npm run validate
//
// Exits non-zero if any diagram fails to parse, so it is CI-friendly.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.join(here, 'src');
const docsDir = path.join(here, '..');

// Set up a minimal DOM so mermaid can initialize in Node.
const dom = new JSDOM('<!DOCTYPE html><body></body>', { pretendToBeVisual: true });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.DOMPurify = undefined;

const { default: mermaid } = await import('mermaid');
mermaid.initialize({ startOnLoad: false });

/** @type {{ label: string, diagram: string }[]} */
const items = [];

// 1. Standalone .mmd sources.
for (const file of fs.readdirSync(srcDir).filter((f) => f.endsWith('.mmd'))) {
  items.push({
    label: `src/${file}`,
    diagram: fs.readFileSync(path.join(srcDir, file), 'utf8'),
  });
}

// 2. Inline ```mermaid``` blocks in the sibling markdown docs.
for (const file of fs.readdirSync(docsDir).filter((f) => f.endsWith('.md'))) {
  const text = fs.readFileSync(path.join(docsDir, file), 'utf8');
  const blocks = [...text.matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1]);
  blocks.forEach((diagram, i) => {
    items.push({ label: `${file} [block ${i + 1}]`, diagram });
  });
}

let failed = 0;
for (const { label, diagram } of items) {
  try {
    await mermaid.parse(diagram);
    console.log(`OK   ${label}`);
  } catch (e) {
    failed++;
    console.error(`FAIL ${label}`);
    console.error(
      String(e?.message || e)
        .split('\n')
        .slice(0, 6)
        .join('\n'),
    );
  }
}

console.log(`\n${items.length - failed}/${items.length} diagrams valid`);
process.exit(failed ? 1 : 0);
