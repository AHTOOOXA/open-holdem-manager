/**
 * Hand-value category tokens: every key the backend can send has a
 * `--hv-<key>` variable (oklch) and a `--color-hv-<key>` theme entry in
 * src/index.css, and hvColor() falls back to the neutral "other" token.
 *
 * Run: cd frontend && npx tsx --test tests/hv-color.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { HV_KEYS, hvColor } from '../src/lib/hv-color';

const here = path.dirname(fileURLToPath(import.meta.url));
const css = fs.readFileSync(path.join(here, '../src/index.css'), 'utf8');
const backend = fs.readFileSync(path.join(here, '../../backend/app/hand_value.py'), 'utf8');

test('hvColor: token per key, neutral fallback', () => {
  assert.equal(hvColor('tpwk'), 'var(--hv-tpwk)');
  assert.equal(hvColor('kq_kj_qj'), 'var(--hv-kq-kj-qj)');
  assert.equal(hvColor('two_pairs_plus'), 'var(--hv-two-pairs-plus)');
  assert.equal(hvColor('other'), 'var(--hv-other)');
  assert.equal(hvColor('no_such_key'), 'var(--hv-other)');
  assert.equal(hvColor(null), 'var(--hv-other)');
});

test('every HV key has an oklch value and a theme colour in index.css', () => {
  for (const key of HV_KEYS) {
    const name = key.replaceAll('_', '-');
    assert.match(css, new RegExp(`--hv-${name}: oklch\\(`), `--hv-${name}`);
    assert.match(css, new RegExp(`--color-hv-${name}: var\\(--hv-${name}\\)`), `--color-hv-${name}`);
  }
});

test('every category key in backend/app/hand_value.py is known to the frontend', () => {
  const keys = [...backend.matchAll(/_c\("([a-z_]+)"/g)].map((m) => m[1]);
  assert.ok(keys.length > 10);
  for (const k of keys) assert.ok((HV_KEYS as readonly string[]).includes(k), k);
});
