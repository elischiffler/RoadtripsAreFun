import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { resolveConfig } from 'vite';

// Use the public parser API of the React plugin's declared Babel dependency.
// This adds no package and remains valid when npm nests rather than hoists it.
const require = createRequire(import.meta.url);
const reactRequire = createRequire(require.resolve('@vitejs/plugin-react'));
const { parseSync } = reactRequire('@babel/core');
const frontend = fileURLToPath(new URL('../', import.meta.url));
const config = await resolveConfig(
  { root: frontend, configFile: false, envFile: false, logLevel: 'silent' },
  'serve'
);
const resolve = config.createResolver();
const filesystemKey = (value) => path.resolve(value).replaceAll('\\', '/').toLowerCase();

async function filesAt(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) =>
        entry.isDirectory()
          ? filesAt(path.join(directory, entry.name))
          : path.join(directory, entry.name)
      )
    )
  ).flat();
}

function importRequests(node, result = []) {
  if (!node || typeof node !== 'object') return result;
  const request = ['ImportDeclaration', 'ExportNamedDeclaration', 'ExportAllDeclaration'].includes(
    node.type
  )
    ? node.source?.value
    : node.type === 'CallExpression' && node.callee?.type === 'Import'
      ? node.arguments?.[0]?.value
      : undefined;
  if (typeof request === 'string' && request.startsWith('.')) result.push(request);
  for (const [key, child] of Object.entries(node)) {
    if (['loc', 'start', 'end', 'extra', 'comments'].includes(key)) continue;
    if (Array.isArray(child)) child.forEach((value) => importRequests(value, result));
    else if (child && typeof child === 'object') importRequests(child, result);
  }
  return result;
}

async function checkImports(source) {
  const files = await filesAt(source);
  const groups = new Map();
  for (const file of files) {
    const key = path.join(path.dirname(file), path.parse(file).name.toLowerCase());
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(file);
  }
  for (const [key, members] of groups) {
    if (new Set(members.map((file) => path.parse(file).name)).size < 2) groups.delete(key);
  }
  const imports = [];
  for (const importer of files.filter((file) => /\.(?:[cm]?[jt]s|[jt]sx)$/.test(file))) {
    const ast = parseSync(await readFile(importer, 'utf8'), {
      filename: importer,
      sourceType: 'module',
      babelrc: false,
      configFile: false,
      parserOpts: {
        plugins: /\.(?:[cm]?ts|tsx)$/.test(importer)
          ? ['typescript', ...(/\.tsx$/.test(importer) ? ['jsx'] : [])]
          : ['jsx'],
      },
    });
    for (const request of importRequests(ast)) {
      const target = path.resolve(path.dirname(importer), request.split('?')[0]);
      const spelling = path.extname(target) ? path.parse(target).name : path.basename(target);
      const key = path.join(path.dirname(target), spelling.toLowerCase());
      if (groups.has(key)) imports.push({ importer, request, key, spelling });
    }
  }

  const temporary = await mkdtemp(path.join(tmpdir(), 'roadtrips-import-portability-'));
  const namespaces = new Map();
  let sequence = 0;
  try {
    const namespace = async (key, spelling, folded) => {
      const id = `${key}:${folded ? '*' : spelling}`;
      if (namespaces.has(id)) return namespaces.get(id);
      const directory = path.join(temporary, String(sequence++));
      await mkdir(directory);
      const identities = new Map();
      const members = groups.get(key);
      const spellings = folded
        ? new Set([
            ...members.map((file) => path.parse(file).name),
            ...imports.filter((item) => item.key === key).map((item) => item.spelling),
          ])
        : new Set([spelling]);
      for (const member of members) {
        if (!folded && path.parse(member).name !== spelling) continue;
        for (const name of spellings) {
          const alias = path.join(directory, name + path.extname(member));
          const foldedAlias = filesystemKey(alias);
          if (identities.has(foldedAlias) && identities.get(foldedAlias) !== member)
            throw new Error(`Source files differ only by case: ${member}`);
          // Empty owned files are sufficient: the real Vite resolver chooses
          // extensions; neither application modules nor their side effects run.
          try {
            await writeFile(alias, '', { flag: 'wx' });
          } catch (error) {
            if (error.code !== 'EEXIST') throw error;
          }
          identities.set(foldedAlias, member);
        }
      }
      const importer = path.join(directory, '__importer__.jsx');
      await writeFile(importer, '');
      const result = { importer, identities };
      namespaces.set(id, result);
      return result;
    };
    const mismatches = [];
    for (const item of imports) {
      const request = './' + path.basename(item.request);
      const exact = await namespace(item.key, item.spelling, false);
      const folded = await namespace(item.key, item.spelling, true);
      const intendedId = await resolve(request, exact.importer);
      const foldedId = await resolve(request, folded.importer);
      const intended = intendedId && exact.identities.get(filesystemKey(intendedId.split('?')[0]));
      const actual = foldedId && folded.identities.get(filesystemKey(foldedId.split('?')[0]));
      if (!intended || actual !== intended)
        mismatches.push({
          importer: path.relative(source, item.importer),
          request: item.request,
          intended: intended && path.relative(source, intended),
          caseInsensitive: actual && path.relative(source, actual),
        });
    }
    return { checked: imports.length, mismatches };
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

test('frontend imports keep their intended target under case-insensitive lookup', async () => {
  const result = await checkImports(path.join(frontend, 'src'));
  assert.deepEqual(
    result.mismatches,
    [],
    'Case-insensitive resolution selects another module; use an explicit extension:\n' +
      JSON.stringify(result.mismatches, null, 2)
  );
});

test('the audit detects static, re-export and dynamic collisions and accepts explicit components/helpers', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'roadtrips-import-fixture-'));
  try {
    await mkdir(path.join(directory, 'controls'));
    await writeFile(
      path.join(directory, 'controls/Widget.jsx'),
      'export default function Widget() {}'
    );
    await writeFile(path.join(directory, 'controls/widget.js'), 'export const utility = 1;');
    await writeFile(path.join(directory, 'controls/Widget.css'), '');
    const importer = path.join(directory, 'panel.jsx');
    const source = `import Widget from './controls/Widget';
      export {default as Other} from './controls/Widget';
      export const later = () => import('./controls/Widget');
      import {utility} from './controls/widget';
      import './controls/Widget.css';
      export const view = <Widget value={utility} />;`;
    await writeFile(importer, source);
    const broken = await checkImports(directory);
    assert.equal(broken.checked, 5);
    assert.equal(broken.mismatches.length, 3);
    assert.ok(
      broken.mismatches.every(
        (item) =>
          item.intended === 'controls/Widget.jsx' && item.caseInsensitive === 'controls/widget.js'
      )
    );
    await writeFile(importer, source.replaceAll("'./controls/Widget'", "'./controls/Widget.jsx'"));
    assert.deepEqual((await checkImports(directory)).mismatches, []);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
  await assert.rejects(access(directory), { code: 'ENOENT' });
});
