/** Run: cd frontend && npx tsx --test tests/statistics-definition.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  dashboardType, dateButtonLabel, dateChoiceId, exportFileName, generalParams, modeOf, profileLabel,
  resolvedDateRange, sameDefinition, stakesOf, withDate, withMode, withPlayer, withProfile, withStakes,
} from '../src/lib/statistics/definition.ts';
import { sessionPresets } from '../src/lib/reports/steps.ts';
import type { DashboardDefinition } from '../src/lib/statistics/types.ts';

const base: DashboardDefinition = { player_id: null, filters: [], profile_id: 'default' };
const now = new Date(2026, 9, 24, 15, 0); // Sat 2026-10-24
const week = sessionPresets(now).find((p) => p.id === 'week')!;

test('empty definition: no chain, no player', () => {
  assert.deepEqual(generalParams(base, 3, now), { workspace_id: 3 });
  assert.equal(dateButtonLabel(base), 'All Time');
  assert.equal(dateChoiceId(base), 'all');
});

test('filters are kept in date, stakes, mode order with labels', () => {
  const d = withDate(withMode(withStakes(base, '$0.05/$0.10'), 'fast'), { kind: 'custom', from: '2026-01-01', to: '2026-02-01' }, now);
  assert.deepEqual(d.filters.map((s) => s.k), ['date', 'stakes', 'mode']);
  assert.equal(stakesOf(d), '$0.05/$0.10');
  assert.equal(modeOf(d), 'fast');
  assert.equal(dateChoiceId(d), 'custom');
  assert.equal(dateButtonLabel(d), '2026-01-01 – 2026-02-01');
  assert.deepEqual(generalParams(d, 1, now).chain, [
    { k: 'date', from: '2026-01-01', to: '2026-02-01' },
    { k: 'stakes', v: ['$0.05/$0.10'] },
    { k: 'mode', v: 'fast' },
  ]);
  assert.deepEqual(withMode(withStakes(d, null), null).filters.map((s) => s.k), ['date']);
});

test('a relative preset is stored with its id, re-derived, never sent', () => {
  const d = withDate(base, { kind: 'preset', preset: week }, now);
  assert.equal(dateChoiceId(d), 'week');
  assert.equal(dateButtonLabel(d), 'This Week');
  assert.equal((d.filters[0] as { preset?: string }).preset, 'week');
  const later = new Date(2026, 10, 3, 9, 0); // Tue 2026-11-03
  const p = generalParams(d, 1, later);
  assert.deepEqual(p.chain, [{ k: 'date', from: '2026-11-02', to: '2026-11-03' }]);
  assert.deepEqual(resolvedDateRange(d, later), { from: '2026-11-02', to: '2026-11-03' });
  assert.equal(JSON.stringify(p).includes('preset'), false);
  // All Time preset = no date step
  const all = sessionPresets(now).find((x) => x.id === 'all')!;
  assert.deepEqual(withDate(d, { kind: 'preset', preset: all }, now).filters, []);
  assert.deepEqual(withDate(d, { kind: 'custom' }, now).filters, []);
});

test('player id is sent only when set', () => {
  assert.equal(generalParams(withPlayer(base, 42), 1, now).player_id, 42);
  assert.equal('player_id' in generalParams(withPlayer(base, null), 1, now), false);
});

test('same definition ignores labels and re-derived preset dates', () => {
  const a = withDate(base, { kind: 'preset', preset: week }, now);
  const b = withDate(base, { kind: 'preset', preset: week }, new Date(2026, 10, 3));
  assert.equal(sameDefinition(a, b), true);
  assert.equal(sameDefinition(a, base), false);
  const s1 = withStakes(base, '$1/$2');
  const s2 = { ...s1, filters: s1.filters.map((s) => ({ ...s, label: 'other' })) };
  assert.equal(sameDefinition(s1, s2), true);
  assert.equal(sameDefinition(base, withProfile(base, 'preflop.open_raise.CO')), false);
});

test('profile label and dashboard type', () => {
  assert.equal(profileLabel('default'), 'default');
  assert.equal(dashboardType('default'), 'profile');
  assert.equal(profileLabel('preflop.open_raise.CO'), 'Open Raise: Cutoff');
  assert.equal(dashboardType('preflop.open_raise.CO'), 'single');
  assert.equal(profileLabel('postflop.cbet.Turn'), 'Raise 1st → Continuation Bet → Turn Continuation Bet');
  // expression cells and unknown ids are not stats
  assert.equal(profileLabel('postflop.wtsd.Total'), '--');
  assert.equal(dashboardType('postflop.wtsd.Total'), 'profile');
  assert.equal(profileLabel('nope'), '--');
});

test('export file name', () => {
  assert.equal(exportFileName('Cash: all/time', 'Hero'), 'Cash alltime, Hero.json');
  assert.equal(exportFileName('Me', null), 'Me.json');
  assert.equal(exportFileName('???', ''), 'dashboard.json');
});
