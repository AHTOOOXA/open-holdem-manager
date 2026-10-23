/** Run: cd frontend && npx tsx --test tests/reports-steps.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normaliseOwnSteps, sessionPresets, splitOwnSteps, stepKindTab, stepLabel } from '../src/lib/reports/steps.ts';
import type { Step } from '../src/lib/reports/types.ts';

test('stepLabel prefers label, else falls back', () => {
  assert.equal(stepLabel({ k: 'pos', v: ['BTN', 'CO'], label: 'x' }), 'x');
  assert.equal(stepLabel({ k: 'pos', v: ['BTN', 'CO'] }), 'BTN, CO');
  assert.equal(stepLabel({ k: 'mode', v: 'fast' }), 'Fast Fold');
  assert.equal(stepLabel({ k: 'tsize', v: [6] }), '6-max');
  assert.equal(stepLabel({ k: 'tsize', v: [2] }), 'Heads-up');
  assert.equal(stepLabel({ k: 'stack', lo: 40, hi: 80 }), '40-80 bb');
  assert.equal(stepLabel({ k: 'stack', lo: 100, hi: null }), '100+ bb');
  assert.equal(stepLabel({ k: 'stack', lo: 0, hi: 20 }), '< 20 bb');
  assert.equal(stepLabel({ k: 'date', from: '2026-01-01', to: '2026-02-08' }), '2026-01-01 – 2026-02-08');
});

test('stepKindTab', () => {
  assert.equal(stepKindTab({ k: 'row', key: 'P01' }), 'quick');
  assert.equal(stepKindTab({ k: 'pos', v: ['BB'] }), 'positions');
  assert.equal(stepKindTab({ k: 'stack', lo: 1, hi: null }), 'general');
  assert.equal(stepKindTab({ k: 'date', from: 'a' }), 'session');
  assert.equal(stepKindTab({ k: 'hv', street: 'flop', cats: [] }), null);
});

test('normalise orders, drops empties, labels, keeps others', () => {
  const next: Step = { k: 'next', street: 'flop', a: 'bet' };
  const out = normaliseOwnSteps([
    { k: 'date', from: '2026-01-01' },
    next,
    { k: 'pos', v: [] },
    { k: 'stakes', v: ['NL10', 'NL25'] },
    { k: 'row', key: 'P01', label: 'Raise 1st In' },
    { k: 'stack', lo: 0, hi: null },
  ]);
  assert.deepEqual(out.map((s) => s.k), ['row', 'stakes', 'date', 'next']);
  assert.equal(out[1].label, 'NL10, NL25');
  assert.equal(out[0].label, 'Raise 1st In');
  assert.equal(out[3], next);
});

test('split sends duplicates to other', () => {
  const p = splitOwnSteps([{ k: 'row', key: 'a' }, { k: 'row', key: 'b' }, { k: 'hour', v: [1] }]);
  assert.equal(p.row?.key, 'a');
  assert.equal(p.other.length, 2);
});

test('session presets', () => {
  const p = Object.fromEntries(sessionPresets(new Date(2026, 1, 11)).map((x) => [x.id, x]));
  assert.deepEqual([p.today.from, p.today.to], ['2026-02-11', '2026-02-11']);
  assert.equal(p.week.from, '2026-02-09');
  assert.deepEqual([p.lastweek.from, p.lastweek.to], ['2026-02-02', '2026-02-08']);
  assert.deepEqual([p.lastmonth.from, p.lastmonth.to], ['2026-01-01', '2026-01-31']);
  assert.equal(p.last3.from, '2025-11-11');
  assert.equal(p.all.from, undefined);
});
