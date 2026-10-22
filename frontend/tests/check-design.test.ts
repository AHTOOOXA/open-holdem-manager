/**
 * Tests for scripts/check-design.mjs (design-token ratchet).
 * Run: cd frontend && npx tsx --test tests/check-design.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  analyzeSource,
  buildBaseline,
  compare,
  findColorFn,
  findHex,
  findInlineColor,
  findTextArbitrary,
  findToFixed,
  main,
  scanTree,
  stripComments,
} from '../scripts/check-design.mjs';

const n = (hits: unknown[]) => hits.length;

test('hex: colour literals in strings and class names', () => {
  assert.equal(n(findHex(`const c = '#22c55e'; const d = "#FFF";`)), 2);
  assert.equal(n(findHex('<i className="text-[#D3D3D3] bg-[#00000080]" />')), 2);
  assert.equal(n(findHex(`'#abcd'`)), 1);
});

test('hex: ignores ids, anchors, urls, comments', () => {
  assert.equal(n(findHex(`document.querySelector('#root')`)), 0);
  assert.equal(n(findHex(`<a href="#section">x</a>`)), 0);
  assert.equal(n(findHex(`const u = 'https://x.io/page#abc123';`)), 0);
  assert.equal(n(findHex(`<span>Hand #123</span>`)), 0);
  assert.equal(n(findHex(`const id = 'Hand #RC1234567';`)), 0);
  assert.equal(n(findHex(`// color: #fff\n/* #000000 */ const a = 1;`)), 0);
  assert.equal(n(findHex(`const x = '#ggg';`)), 0);
});

test('color-fn: colour functions', () => {
  assert.equal(n(findColorFn(`'rgb(1,2,3)' 'rgba(0,0,0,.5)' hsl(1 2% 3%) hsla( oklch(0.5 0 0) oklab( color-mix(in oklch, red, blue)`)), 7);
  assert.equal(n(findColorFn(`// rgb(1,2,3)\nconst a = rgbToHex(1);`)), 0);
  assert.equal(n(findColorFn(`const a = myrgb(1);`)), 0);
});

test('text-arbitrary: arbitrary font sizes only', () => {
  assert.equal(n(findTextArbitrary(`"text-[12px] md:text-[0.8rem] text-[1.1em]"`)), 3);
  assert.equal(n(findTextArbitrary(`"text-[#fff] text-[var(--fs)] text-sm text-xs"`)), 0);
});

test('inline-color: literal vs variable values', () => {
  assert.equal(n(findInlineColor(`<i style={{ color: '#fff', background: "red" }} />`)), 2);
  assert.equal(n(findInlineColor(`<i style={{ background: ws.color }} />`)), 0);
  assert.equal(n(findInlineColor(`<i style={{ color: 'var(--color-green)' }} />`)), 0);
  assert.equal(n(findInlineColor(`<i style={{ color: \`\${x}\` }} />`)), 0);
  assert.equal(n(findInlineColor(`<i style={{ width: 10, borderColor: 'tomato', fill: cond ? a : b }} />`)), 1);
  assert.equal(n(findInlineColor(`<i style={{\n  stroke: 'blue',\n  boxShadow: '0 0 1px red',\n}} />`)), 2);
  assert.equal(n(findInlineColor(`<i style={{ background: 'transparent' }} />`)), 0);
  assert.equal(n(findInlineColor(`const s = { color: 'red' };`)), 0); // outside style={{ }}
  assert.equal(n(findInlineColor(`<i style={{ backgroundImage: 'x', accentcolor: 'red' }} />`)), 0);
});

test('toFixed', () => {
  assert.equal(n(findToFixed(`a.toFixed(2) + (b).toFixed(1)`)), 2);
  assert.equal(n(findToFixed(`// a.toFixed(2)`)), 0);
});

test('stripComments keeps strings and line numbers', () => {
  const s = `const u = 'http://a.b'; // c\n/* x\ny */ z`;
  const out = stripComments(s);
  assert.ok(out.includes(`'http://a.b'`));
  assert.equal(out.split('\n').length, 3);
});

test('analyzeSource honours exemptions and reports lines', () => {
  const src = `a.toFixed(1);\nconst c = '#fff';`;
  const r = analyzeSource(src);
  assert.equal(r.toFixed[0].line, 1);
  assert.equal(r.hex[0].line, 2);
  assert.deepEqual(Object.keys(analyzeSource(src, ['toFixed'])), ['hex']);
});

function tmpTree(files: Record<string, string>) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'design-'));
  fs.mkdirSync(path.join(root, 'scripts'));
  for (const [f, c] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, f)), { recursive: true });
    fs.writeFileSync(path.join(root, f), c);
  }
  return root;
}

test('ratchet: compare, fail on new violation, update refuses increases', () => {
  const root = tmpTree({
    'src/a.tsx': `export const a = '#fff';\n`,
    'src/ok.ts': `export const b = 1;\n`,
    'src/lib/format/f.ts': `export const f = (x: number) => x.toFixed(2);\n`,
    'src/skip.d.ts': `declare const c: '#fff';\n`,
    'landing/l.tsx': `export const l = 'rgb(1,2,3)';\n`,
  });
  fs.writeFileSync(
    path.join(root, 'scripts/design-allow.json'),
    JSON.stringify({ allow: [{ prefix: 'src/lib/format/', rules: ['toFixed'] }] }),
  );
  const log = () => {};
  const bl = path.join(root, 'scripts/design-baseline.json');

  // no baseline: everything is new
  assert.equal(main([], root, log), 1);
  assert.equal(main(['--update'], root, log), 1); // refuses new nonzero files
  assert.equal(main(['--update', '--allow-increase'], root, log), 0);
  assert.deepEqual(JSON.parse(fs.readFileSync(bl, 'utf8')), {
    'landing/l.tsx': { 'color-fn': 1 },
    'src/a.tsx': { hex: 1 },
  });
  assert.equal(main([], root, log), 0);

  // regression: a second hex in an existing file, and a new file
  fs.appendFileSync(path.join(root, 'src/a.tsx'), `export const a2 = '#000000';\n`);
  assert.equal(main([], root, log), 1);
  const scan = scanTree(root, [{ prefix: 'src/lib/format/', rules: ['toFixed'] }]);
  const base = JSON.parse(fs.readFileSync(bl, 'utf8'));
  const { violations } = compare(scan, base);
  assert.deepEqual(violations.map((v) => [v.file, v.rule, v.base, v.count]), [['src/a.tsx', 'hex', 1, 2]]);
  assert.equal(buildBaseline(scan, base).increases.length, 1);
  assert.equal(main(['--update'], root, log), 1);
  assert.equal(JSON.parse(fs.readFileSync(bl, 'utf8'))['src/a.tsx'].hex, 1);

  // improvement: fix everything, passes, update lowers
  fs.writeFileSync(path.join(root, 'src/a.tsx'), `export const a = 1;\n`);
  const lines: string[] = [];
  assert.equal(main([], root, (s: string) => lines.push(s)), 0);
  assert.ok(lines.join('\n').includes('lint:design:update'));
  assert.equal(main(['--update'], root, log), 0);
  assert.deepEqual(Object.keys(JSON.parse(fs.readFileSync(bl, 'utf8'))), ['landing/l.tsx']);

  fs.rmSync(root, { recursive: true });
});
