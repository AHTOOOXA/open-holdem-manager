/** Run: cd frontend && npx tsx --test tests/reports-fixf.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { presetDateStep, presetOf, resolvePresets, sessionPresets, stripUiFields } from '../src/lib/reports/steps.ts';
import { chainParam } from '../src/lib/reports/api.ts';
import { composeFull, composeUpper, parseStoredChain, serializeChain, freshChain, setOwnSteps, type ReportChain } from '../src/lib/reports/pages.ts';
import { activeLegacyFilters, legacyFilterLabels } from '../src/lib/reports/legacy-filters.ts';
import type { Step } from '../src/lib/reports/types.ts';

const at = (y: number, m: number, d: number) => new Date(y, m - 1, d, 15, 30);
const p = (now: Date, id: string) => {
  const x = sessionPresets(now).find((q) => q.id === id)!;
  return [x.from, x.to];
};

test('Last Week across a month boundary', () => {
  assert.deepEqual(p(at(2026, 10, 1), 'lastweek'), ['2026-09-21', '2026-09-27']);
  assert.deepEqual(p(at(2026, 10, 1), 'week'), ['2026-09-28', '2026-10-01']);
  assert.deepEqual(p(at(2027, 1, 1), 'lastweek'), ['2026-12-21', '2026-12-27']);
  assert.deepEqual(p(at(2026, 10, 19), 'lastweek'), ['2026-10-12', '2026-10-18']);
  assert.deepEqual(p(at(2026, 10, 25), 'lastweek'), ['2026-10-12', '2026-10-18']);
});

test('other presets at boundaries', () => {
  assert.deepEqual(p(at(2026, 3, 1), 'yesterday'), ['2026-02-28', '2026-02-28']);
  assert.deepEqual(p(at(2026, 1, 1), 'yesterday'), ['2025-12-31', '2025-12-31']);
  assert.deepEqual(p(at(2026, 1, 15), 'lastmonth'), ['2025-12-01', '2025-12-31']);
  assert.deepEqual(p(at(2026, 3, 31), 'lastmonth'), ['2026-02-01', '2026-02-28']);
  assert.deepEqual(p(at(2026, 5, 31), 'last3'), ['2026-02-28', '2026-05-31']);
  assert.deepEqual(p(at(2026, 1, 10), 'last3'), ['2025-10-10', '2026-01-10']);
  assert.deepEqual(p(at(2026, 12, 31), 'year'), ['2026-01-01', '2026-12-31']);
  assert.deepEqual(p(at(2026, 2, 5), 'month'), ['2026-02-01', '2026-02-05']);
  assert.deepEqual(p(at(2026, 2, 5), 'today'), ['2026-02-05', '2026-02-05']);
});

test('preset date steps re-derive; custom ones stay fixed', () => {
  const monday = sessionPresets(at(2026, 10, 19)).find((x) => x.id === 'week')!;
  const step = presetDateStep(monday, at(2026, 10, 19));
  assert.equal(presetOf(step), 'week');
  const custom: Step = { k: 'date', from: '2026-01-01', to: '2026-01-31', label: 'x' };
  const pos: Step = { k: 'pos', v: ['BTN'] };
  const out = resolvePresets([pos, step, custom], at(2026, 10, 22));
  assert.deepEqual(out[1], { ...step, from: '2026-10-19', to: '2026-10-22' });
  assert.equal(out[2], custom);
  const plain = [pos, custom];
  assert.equal(resolvePresets(plain), plain);
});

test('compose functions re-derive presets', () => {
  const today = presetDateStep(sessionPresets(at(2026, 10, 1)).find((x) => x.id === 'today')!, at(2026, 10, 1));
  const now = at(2026, 10, 2);
  assert.deepEqual(composeUpper([], [today], now)[0], { ...today, from: '2026-10-02', to: '2026-10-02' });
  assert.deepEqual(composeFull([today], [], [], now)[0], { ...today, from: '2026-10-02', to: '2026-10-02' });
});

test('persisted chains re-derive presets on load', () => {
  const today = presetDateStep(sessionPresets(at(2026, 10, 1)).find((x) => x.id === 'today')!, at(2026, 10, 1));
  const c: ReportChain = setOwnSteps(freshChain(), 0, [today]);
  const loaded = parseStoredChain(serializeChain(c, null), at(2026, 10, 5))!;
  const own = loaded.chain.pages[0].state.own[0] as Step & { preset?: string; from?: string };
  assert.equal(own.preset, 'today');
  assert.equal(own.from, '2026-10-05');
});

test('chainParam strips label and preset, [] stays []', () => {
  assert.equal(chainParam([]), '[]');
  const s = { k: 'date', from: 'a', to: 'b', label: 'Today', preset: 'today' } as unknown as Step;
  assert.equal(chainParam([s]), JSON.stringify([{ k: 'date', from: 'a', to: 'b' }]));
  assert.deepEqual(stripUiFields([s])[0], { k: 'date', from: 'a', to: 'b', label: 'Today' });
});

test('legacy filters notice data', () => {
  const link = { tab: 'hands', statFlags: ['vpip', 'pfr'], position: ['BTN'], statKey: 'k' };
  assert.deepEqual(legacyFilterLabels(link), ['vpip', 'pfr', 'k', 'BTN']);
  assert.equal(activeLegacyFilters(link, 2, 0), link);
  assert.equal(activeLegacyFilters(link, 2, 2), undefined, 'dismissed');
  assert.equal(activeLegacyFilters({ ...link, tab: 'graph' }, 2, 0), undefined);
  assert.equal(activeLegacyFilters({ tab: 'hands', statFlags: [], position: [] }, 1, 0), undefined);
  assert.equal(activeLegacyFilters(null, 1, 0), undefined);
});
