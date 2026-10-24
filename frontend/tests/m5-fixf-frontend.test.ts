/** Run: cd frontend && npx tsx --test tests/m5-fixf-frontend.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getAppDayStartHour, sessionPresets, setAppDayStartHour } from '../src/lib/reports/steps.ts';
import { datePresets } from '../src/lib/sessions/date-filter.ts';
import { dayKey } from '../src/hooks/useDayStart.ts';
import { expandedStore, forgetNodes, loadPages, pagesStoreKey, savePages, freshStatChain } from '../src/lib/statistics/pages.ts';
import { removedNodeIds } from '../src/lib/statistics/tree.ts';
import { grouped } from '../src/lib/format/number.ts';

const at3am = new Date(2026, 9, 24, 3, 0); // Saturday 03:00

test('presets: day start shifts "today" back before that hour', () => {
  const today = (h?: number) => sessionPresets(at3am, h).find((p) => p.id === 'today')!;
  assert.equal(today(0).from, '2026-10-24');
  assert.equal(today(5).from, '2026-10-23');
  assert.equal(datePresets(at3am, 5).find((p) => p.id === 'today')!.from, '2026-10-23');
});

test('presets: default hour is the app setting', () => {
  setAppDayStartHour(5);
  assert.equal(getAppDayStartHour(), 5);
  assert.equal(sessionPresets(at3am).find((p) => p.id === 'today')!.from, '2026-10-23');
  setAppDayStartHour(99);
  assert.equal(getAppDayStartHour(), 0);
});

test('dayKey follows the day-start rule', () => {
  assert.equal(dayKey(at3am, 0), '2026-10-24');
  assert.equal(dayKey(at3am, 4), '2026-10-23');
});

test('forgetNodes clears pages and expansion of removed nodes', () => {
  const key = pagesStoreKey(1, 7);
  savePages(key, { defKey: 'x', chain: freshStatChain() });
  expandedStore.set(1, new Set([7, 8]));
  forgetNodes(1, [7]);
  assert.notEqual(loadPages(key, 'x').chain, undefined);
  assert.equal(loadPages(key, 'x').defKey, 'x');
  assert.deepEqual([...expandedStore.get(1)!], [8]);
  // pages gone: a fresh chain with a new object is returned
  const a = loadPages(key, 'x');
  const b = loadPages(key, 'x');
  assert.notEqual(a.chain, b.chain);
});

test('removedNodeIds', () => {
  const n = (id: number) => ({ id, kind: 'dashboard', name: String(id), parent_id: null }) as never;
  assert.deepEqual(removedNodeIds([n(1), n(2), n(3)], [n(1), n(3)]), [2]);
});

test('grouped thousands', () => {
  assert.equal(grouped(1234567), '1,234,567');
  assert.equal(grouped(12), '12');
});
