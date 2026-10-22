#!/usr/bin/env node
/**
 * Design-token ratchet. See scripts/README.md.
 *
 *   node scripts/check-design.mjs                 check against baseline
 *   node scripts/check-design.mjs --update        lower the baseline (refuses increases)
 *   node scripts/check-design.mjs --update --allow-increase
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const RULES = ['hex', 'color-fn', 'text-arbitrary', 'inline-color', 'toFixed'];
export const SCAN_DIRS = ['src', 'landing'];

/** Replace // and block comments with spaces (newlines kept so line numbers hold). String-aware. */
export function stripComments(src) {
  let out = '';
  let i = 0;
  let quote = null;
  while (i < src.length) {
    const c = src[i];
    const n = src[i + 1];
    if (quote) {
      out += c;
      if (c === '\\' && i + 1 < src.length) {
        out += n;
        i += 2;
        continue;
      }
      // ' and " strings never span lines (also recovers from JSX text apostrophes)
      if (c === quote || (c === '\n' && quote !== '`')) quote = null;
      i++;
      continue;
    }
    if (c === '/' && n === '/') {
      while (i < src.length && src[i] !== '\n') {
        out += ' ';
        i++;
      }
      continue;
    }
    if (c === '/' && n === '*') {
      i += 2;
      out += '  ';
      while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) {
        out += src[i] === '\n' ? '\n' : ' ';
        i++;
      }
      if (i < src.length) {
        out += '  ';
        i += 2;
      }
      continue;
    }
    if (c === '"' || c === "'" || c === '`') quote = c;
    out += c;
    i++;
  }
  return out;
}

function lineOf(src, index) {
  let line = 1;
  for (let i = 0; i < index; i++) if (src.charCodeAt(i) === 10) line++;
  return line;
}

function lineText(src, line) {
  return (src.split('\n')[line - 1] ?? '').trim();
}

function regexHits(src, re, accept) {
  const hits = [];
  const g = new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g');
  for (const m of src.matchAll(g)) {
    if (accept && !accept(m, src)) continue;
    hits.push({ line: lineOf(src, m.index), match: m[0] });
  }
  return hits;
}

export const HEX_RE = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])/g;
export const COLOR_FN_RE = /(?<![\w$.])(?:rgba?|hsla?|oklch|oklab|color-mix)\(/g;
export const TEXT_ARBITRARY_RE = /(?<![\w-])text-\[-?(?:\d+\.?\d*|\.\d+)(?:px|rem|em)\]/g;
export const TO_FIXED_RE = /\.toFixed\(/g;
const INLINE_KEYS = 'color|background|backgroundColor|borderColor|fill|stroke|outlineColor|boxShadow|textShadow';
const INLINE_KEY_RE = new RegExp(`(?<![\\w$.-])(?:${INLINE_KEYS})\\s*:\\s*(['"\`])`, 'g');
const INLINE_KEYWORDS = /^(?:none|transparent|inherit|initial|unset|currentcolor)$/i;

/** `#abc`, `#aabbcc` ... not preceded by a word char, `/`, `&`, `.`; all-digit only after a quote, `[` or `(`. */
export function findHex(src) {
  return regexHits(stripComments(src), HEX_RE, (m, s) => {
    const prev = s[m.index - 1] ?? '';
    if (/[\w/&.\-#]/.test(prev)) return false;
    if (/^#\d+$/.test(m[0]) && !/['"`[(]/.test(prev)) return false; // "Hand #123"
    return true;
  });
}

export function findColorFn(src) {
  return regexHits(stripComments(src), COLOR_FN_RE);
}

export function findTextArbitrary(src) {
  return regexHits(stripComments(src), TEXT_ARBITRARY_RE);
}

export function findToFixed(src) {
  return regexHits(stripComments(src), TO_FIXED_RE);
}

/** Text of the balanced `{...}` starting at index of its `{`. */
function balanced(src, start) {
  let depth = 0;
  let quote = null;
  for (let i = start; i < src.length; i++) {
    const c = src[i];
    if (quote) {
      if (c === '\\') i++;
      else if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') quote = c;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return { end: i, text: src.slice(start, i + 1) };
  }
  return null;
}

/** Colour-ish keys inside `style={{ ... }}` whose value is a plain string literal. */
export function findInlineColor(src) {
  const clean = stripComments(src);
  const hits = [];
  for (const s of clean.matchAll(/style\s*=\s*\{\s*\{/g)) {
    const open = clean.indexOf('{', s.index + s[0].indexOf('{') + 1);
    const obj = balanced(clean, open);
    if (!obj) continue;
    for (const m of obj.text.matchAll(INLINE_KEY_RE)) {
      const q = m[1];
      const valStart = m.index + m[0].length;
      const valEnd = obj.text.indexOf(q, valStart);
      if (valEnd < 0) continue;
      const value = obj.text.slice(valStart, valEnd);
      if (q === '`' && value.includes('${')) continue; // expression, not a literal
      if (/^\s*var\(/.test(value) || INLINE_KEYWORDS.test(value.trim())) continue;
      // `'a' + x`, `'#fff' ? ..` style continuations are still literals-led; count them.
      hits.push({ line: lineOf(clean, open + m.index), match: m[0] + value });
    }
  }
  return hits;
}

export const MATCHERS = {
  hex: findHex,
  'color-fn': findColorFn,
  'text-arbitrary': findTextArbitrary,
  'inline-color': findInlineColor,
  toFixed: findToFixed,
};

/** { rule: [{line, match}] } for non-empty rules, minus `exempt` rules. */
export function analyzeSource(src, exempt = []) {
  const res = {};
  for (const rule of RULES) {
    if (exempt.includes(rule)) continue;
    const hits = MATCHERS[rule](src);
    if (hits.length) res[rule] = hits;
  }
  return res;
}

export function exemptRules(file, allow) {
  const rules = new Set();
  for (const e of allow) if (file.startsWith(e.prefix)) for (const r of e.rules) rules.add(r);
  return [...rules];
}

function walk(dir, root, out) {
  if (!fs.existsSync(dir)) return;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === 'node_modules' || ent.name.startsWith('dist')) continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full, root, out);
    else if (/\.(ts|tsx)$/.test(ent.name) && !ent.name.endsWith('.d.ts')) {
      out.push(path.relative(root, full).split(path.sep).join('/'));
    }
  }
}

/** { file: { rule: [{line, match}] } } for files with at least one hit. */
export function scanTree(root, allow = []) {
  const files = [];
  for (const d of SCAN_DIRS) walk(path.join(root, d), root, files);
  files.sort();
  const res = {};
  for (const f of files) {
    const hits = analyzeSource(fs.readFileSync(path.join(root, f), 'utf8'), exemptRules(f, allow));
    if (Object.keys(hits).length) res[f] = hits;
  }
  return res;
}

export function toCounts(scan) {
  const out = {};
  for (const [f, rules] of Object.entries(scan)) {
    out[f] = Object.fromEntries(Object.entries(rules).map(([r, h]) => [r, h.length]));
  }
  return out;
}

/** Compare a scan with a baseline. */
export function compare(scan, baseline) {
  const violations = []; // {file, rule, count, base, isNew}
  const improvements = []; // {file, rule, count, base}
  const files = new Set([...Object.keys(scan), ...Object.keys(baseline)]);
  for (const file of [...files].sort()) {
    for (const rule of RULES) {
      const count = scan[file]?.[rule]?.length ?? 0;
      const base = baseline[file]?.[rule] ?? 0;
      if (count > base) violations.push({ file, rule, count, base, isNew: !(file in baseline), hits: scan[file][rule] });
      else if (count < base) improvements.push({ file, rule, count, base });
    }
  }
  return { violations, improvements };
}

/** Next baseline from a scan. Returns { baseline, increases }. */
export function buildBaseline(scan, baseline) {
  const next = {};
  const increases = [];
  for (const [file, rules] of Object.entries(toCounts(scan)).sort(([a], [b]) => a.localeCompare(b))) {
    next[file] = {};
    for (const rule of RULES) {
      if (!rules[rule]) continue;
      next[file][rule] = rules[rule];
      const base = baseline[file]?.[rule] ?? 0;
      if (rules[rule] > base) increases.push({ file, rule, count: rules[rule], base });
    }
  }
  return { baseline: next, increases };
}

function readJson(p, fallback) {
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : fallback;
}

export function loadAllow(p) {
  return readJson(p, { allow: [] }).allow ?? [];
}

export function main(argv, root, log = console.log) {
  const baselinePath = path.join(root, 'scripts/design-baseline.json');
  const allow = loadAllow(path.join(root, 'scripts/design-allow.json'));
  const baseline = readJson(baselinePath, {});
  const scan = scanTree(root, allow);

  if (argv.includes('--update')) {
    const { baseline: next, increases } = buildBaseline(scan, baseline);
    if (increases.length && !argv.includes('--allow-increase')) {
      log('Refusing to raise the baseline (pass --allow-increase to override):');
      for (const i of increases) log(`  ${i.file} [${i.rule}] ${i.base} -> ${i.count}`);
      return 1;
    }
    fs.writeFileSync(baselinePath, JSON.stringify(next, null, 2) + '\n');
    log(`Baseline written: ${Object.keys(next).length} files.`);
    return 0;
  }

  const { violations, improvements } = compare(scan, baseline);
  for (const v of violations) {
    log(`${v.file} [${v.rule}] ${v.isNew ? 'new file with violations' : `${v.base} -> ${v.count}`}`);
    const src = fs.readFileSync(path.join(root, v.file), 'utf8');
    for (const h of v.hits) log(`  ${v.file}:${h.line}  ${lineText(src, h.line).slice(0, 140)}`);
  }
  if (improvements.length) {
    log('\nBelow baseline (run `npm run lint:design:update` to lock in the gain):');
    for (const i of improvements) log(`  ${i.file} [${i.rule}] ${i.base} -> ${i.count}`);
  }
  if (violations.length) {
    log('\nDesign check failed. Use tokens from src/index.css and helpers from src/lib/format/; see scripts/README.md.');
    return 1;
  }
  log('Design check passed.');
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  process.exit(main(process.argv.slice(2), root));
}
