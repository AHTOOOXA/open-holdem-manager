/** Run: cd frontend && npx tsx --test tests/sessions-pages.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  childScope, freshPageState, isSessionTab, kindOpenedBy, parseSessionParam, pickSession, recipeFor, sessionScope, tabsFor,
} from '../src/lib/sessions/pages.ts';
import { liveFlipped, liveSignature } from '../src/lib/sessions/live.ts';
import {
  dateFilterLabel, datePresets, parseDateFilter, resolveDateFilter, serializeDateFilter, shiftForDayStart,
} from '../src/lib/sessions/date-filter.ts';
import type { SessionRow } from '../src/lib/sessions/types.ts';
import type { SplitRow } from '../src/lib/reports/types.ts';

const row = (id: number, start: string): SessionRow => ({
  id, number: id, start, last_hand_at: start, end: start, duration_s: 600, is_live: false, hands: 10,
  won: 1, won_ev: 1, won_bb: 1, won_ev_bb: 1, filter: { k: 'session', start, end: start },
});

test('tabs per page kind, Hands first', () => {
  assert.deepEqual(tabsFor('session'), ['hands', 'tables', 'players']);
  assert.deepEqual(tabsFor('table'), ['hands', 'players']);
  assert.deepEqual(tabsFor('villain'), ['hands']);
  assert.equal(freshPageState().tab, 'hands');
  assert.equal(isSessionTab('tables', 'table'), false);
  assert.equal(isSessionTab('players', 'table'), true);
});

test('recipe follows the page kind; rows open the right kind', () => {
  assert.equal(recipeFor('session'), 'session');
  assert.equal(recipeFor('villain'), 'villain');
  assert.equal(kindOpenedBy('tables'), 'table');
  assert.equal(kindOpenedBy('players'), 'villain');
});

test('page 0 chain is only the session step', () => {
  const s = sessionScope(row(5, '2026-10-17T20:00:00'));
  assert.deepEqual(s.chain, [{ k: 'session', start: '2026-10-17T20:00:00', end: '2026-10-17T20:00:00' }]);
  assert.equal(s.playerId, undefined);
});

test('Tables row appends its step and keeps the player; Players row switches the player', () => {
  const p0 = { ...sessionScope(row(5, '2026-10-17T20:00:00')), playerId: 7 };
  const tableRow: SplitRow = { key: 't', caption: 'T1', filter: { k: 'table', v: ['T1'] }, values: {} };
  const t = childScope(p0, 'tables', tableRow)!;
  assert.equal(t.kind, 'table');
  assert.equal(t.playerId, 7);
  assert.deepEqual(t.chain.map((s) => s.k), ['session', 'table']);

  const pr: SplitRow = { key: 'p', caption: 'Villain', filter: { k: 'with', player_id: 7 }, values: {}, player: { id: 99, username: 'Villain' } };
  const v = childScope(t, 'players', pr)!;
  assert.equal(v.kind, 'villain');
  assert.equal(v.playerId, 99);
  assert.deepEqual(v.chain.map((s) => s.k), ['session', 'table', 'with']);
  assert.equal(childScope(t, 'players', { ...pr, player: undefined }), null);
});

test('pickSession: preferred id, else newest, never throws on stale ids', () => {
  const rows = [row(3, '2026-10-17T20:00:00'), row(2, '2026-10-16T20:00:00'), row(1, '2026-10-15T20:00:00')];
  assert.equal(pickSession(rows, 2)?.id, 2);
  assert.equal(pickSession(rows, 42)?.id, 3);
  assert.equal(pickSession(rows, null)?.id, 3);
  assert.equal(pickSession([], 1), null);
  // unsorted input still resolves to the newest start
  assert.equal(pickSession([rows[2], rows[0], rows[1]], null)?.id, 3);
});

test('route param parsing', () => {
  assert.equal(parseSessionParam('123'), 123);
  assert.equal(parseSessionParam('0'), null);
  assert.equal(parseSessionParam('abc'), null);
  assert.equal(parseSessionParam(undefined), null);
});

test('live flip: first answer is not a flip, a changed state is', () => {
  const a = liveSignature({ live: true, session_id: 1, start: 'x' });
  const b = liveSignature({ live: false, session_id: 1, start: 'x' });
  assert.equal(liveFlipped(null, a), false);
  assert.equal(liveFlipped(a, a), false);
  assert.equal(liveFlipped(a, b), true);
  assert.equal(liveSignature(undefined), null);
});

const NOW = new Date(2026, 9, 24, 15, 0); // Sat 24 Oct 2026

test('date filter: no Last Session, no All Time in the preset list', () => {
  const ids = datePresets(NOW).map((p) => p.id);
  assert.ok(ids.includes('today') && ids.includes('month'));
  assert.ok(!ids.includes('all') && !ids.includes('lastsession'));
});

test('date filter: presets are re-derived, custom kept, junk falls back to All Time', () => {
  assert.deepEqual(resolveDateFilter(null, NOW), {});
  assert.deepEqual(resolveDateFilter({ kind: 'preset', id: 'today' }, NOW), { date_from: '2026-10-24', date_to: '2026-10-24' });
  assert.deepEqual(resolveDateFilter({ kind: 'preset', id: 'today' }, new Date(2026, 9, 25, 9, 0)), { date_from: '2026-10-25', date_to: '2026-10-25' });
  assert.deepEqual(resolveDateFilter({ kind: 'custom', from: '2026-10-01' }, NOW), { date_from: '2026-10-01' });
  assert.equal(parseDateFilter('not json'), null);
  assert.equal(parseDateFilter('{"kind":"preset","id":"nope"}', NOW), null);
  const f = parseDateFilter(serializeDateFilter({ kind: 'custom', from: '2026-10-01', to: '2026-10-17' }), NOW);
  assert.deepEqual(f, { kind: 'custom', from: '2026-10-01', to: '2026-10-17' });
});

test('date filter labels', () => {
  assert.equal(dateFilterLabel(null, NOW), 'All Time');
  assert.equal(dateFilterLabel({ kind: 'preset', id: 'month' }, NOW), 'This Month');
  assert.equal(dateFilterLabel({ kind: 'custom', from: '2026-10-01', to: '2026-10-17' }, NOW), 'From 01-10-2026 to 17-10-2026');
});

test('day start hour shifts "today" back before that hour', () => {
  const early = new Date(2026, 9, 24, 2, 0);
  assert.deepEqual(resolveDateFilter({ kind: 'preset', id: 'today' }, early, 4), { date_from: '2026-10-23', date_to: '2026-10-23' });
  assert.equal(shiftForDayStart(early, 0), early);
});
