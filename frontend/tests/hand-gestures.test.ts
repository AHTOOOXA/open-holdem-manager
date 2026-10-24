/**
 * Hand-list gestures (M8): panel docking, arrow navigation, hover intent timing, export URL, hand-plot formatting.
 * Run: cd frontend && npx tsx --test tests/hand-gestures.test.ts
 */
import { test, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  HAND_PANEL_MIN_CONTAINER_WIDTH,
  canDockPanel,
  createHoverIntent,
  isGridKeyTarget,
  neighbourId,
} from '../src/lib/hands/gestures';
import { handHistoryText, plotAmount, plotPlayers, exportCapNotice, plotResult, rowPlayer } from '../src/lib/hands/hand-plot';
import { handsExportUrl } from '../src/lib/api';

test('canDockPanel: unmeasured and narrow containers fall back to the drawer', () => {
  assert.equal(canDockPanel(null), false);
  assert.equal(canDockPanel(HAND_PANEL_MIN_CONTAINER_WIDTH - 1), false);
  assert.equal(canDockPanel(HAND_PANEL_MIN_CONTAINER_WIDTH), true);
});

test('neighbourId: clamps at both ends, starts from an end when nothing is selected', () => {
  const ids = ['a', 'b', 'c'];
  assert.equal(neighbourId(ids, 'a', 1), 'b');
  assert.equal(neighbourId(ids, 'c', 1), 'c');
  assert.equal(neighbourId(ids, 'a', -1), 'a');
  assert.equal(neighbourId(ids, null, 1), 'a');
  assert.equal(neighbourId(ids, 'gone', -1), 'c');
  assert.equal(neighbourId([], 'a', 1), null);
});

test('hover intent: opens after the delay, not before; leaving first cancels', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const log: string[] = [];
    const h = createHoverIntent({ openDelay: 300, closeDelay: 100, onOpen: () => log.push('open'), onClose: () => log.push('close') });
    h.enter();
    mock.timers.tick(299);
    assert.deepEqual(log, []);
    mock.timers.tick(1);
    assert.deepEqual(log, ['open']);
    h.leave();
    mock.timers.tick(99);
    assert.deepEqual(log, ['open']);
    mock.timers.tick(1);
    assert.deepEqual(log, ['open', 'close']);

    h.enter();
    mock.timers.tick(100);
    h.leave(); // left before 300 ms: never opens
    mock.timers.tick(1000);
    assert.deepEqual(log, ['open', 'close']);
  } finally {
    mock.timers.reset();
  }
});

test('hover intent: crossing from button to popover keeps it open; pinned ignores leave; openNow is immediate', () => {
  mock.timers.enable({ apis: ['setTimeout'] });
  try {
    const log: string[] = [];
    const h = createHoverIntent({ openDelay: 300, closeDelay: 100, onOpen: () => log.push('open'), onClose: () => log.push('close') });
    h.openNow();
    h.openNow();
    assert.deepEqual(log, ['open']);
    h.leave(); // button -> popover
    mock.timers.tick(50);
    h.enter();
    mock.timers.tick(500);
    assert.deepEqual(log, ['open']);
    h.setPinned(true);
    h.leave();
    mock.timers.tick(500);
    assert.deepEqual(log, ['open']);
    h.setPinned(false);
    h.notifyClosed(); // Esc / outside click closed it
    h.enter();
    mock.timers.tick(300);
    assert.deepEqual(log, ['open', 'open']);
    h.dispose();
  } finally {
    mock.timers.reset();
  }
});

test('handsExportUrl: whole filtered list with sort, chain, marked, tags and player; never paging', () => {
  const url = handsExportUrl(
    {
      page: 3,
      per_page: 50,
      sort: 'won_usd',
      order: 'asc',
      position: 'btn',
      marked: true,
      tag_ids: [2, 5],
      player_id: 9,
      search: 'AK',
      stat_flag: ['vpip', 'pfr'],
      chain: [],
    },
    7,
  );
  const [path, qs] = url.split('?');
  assert.equal(path, '/api/hands/export');
  const sp = new URLSearchParams(qs);
  assert.equal(sp.get('workspace_id'), '7');
  assert.equal(sp.get('format'), 'txt');
  assert.equal(sp.get('sort'), 'won_usd');
  assert.equal(sp.get('order'), 'asc');
  assert.equal(sp.get('position'), 'BTN');
  assert.equal(sp.get('marked'), 'true');
  assert.equal(sp.get('tag_ids'), '2,5');
  assert.equal(sp.get('player_id'), '9');
  assert.equal(sp.get('search'), 'AK');
  assert.deepEqual(sp.getAll('stat_flag'), ['vpip', 'pfr']);
  assert.equal(sp.has('page'), false);
  assert.equal(sp.has('per_page'), false);
  assert.equal(sp.has('chain'), true);
});

test('hand plot: amounts, result line and all-in EV', () => {
  assert.equal(plotAmount(6.5), '6.5 bb');
  assert.equal(plotAmount(3), '3 bb');
  assert.equal(plotAmount(null), '');
  assert.deepEqual(plotResult(12.54), { label: 'Won 12.5 bb', tone: 'pos', ev: null });
  assert.deepEqual(plotResult(-3), { label: 'Lost 3 bb', tone: 'neg', ev: null });
  assert.equal(plotResult(0.02).tone, 'zero');
  assert.equal(plotResult(0.02).label, 'Broke even');
  assert.equal(plotResult(-20, -12.4).ev, 'All-in EV -12.4 bb');
  assert.equal(plotResult(5, 5.01).ev, null);
});

test('hand plot: hero listed first, then seat order; empty history is null', () => {
  const p = (seat: number, is_hero = false) => ({ seat, is_hero }) as never;
  const sorted = plotPlayers({ players: [p(1), p(4, true), p(2)] });
  assert.deepEqual(sorted.map((x) => x.seat), [4, 1, 2]);
  // a mixed list: the row's player leads, matched by player_id; no match falls back to the hero
  const q = (seat: number, player_id: number, is_hero = false) => ({ seat, player_id, is_hero }) as never;
  const mixed = { players: [q(1, 10), q(2, 20, true), q(3, 30)] };
  assert.deepEqual(plotPlayers(mixed, 30).map((x) => x.seat), [3, 1, 2]);
  assert.equal(rowPlayer(mixed.players, 10)?.seat, 1);
  assert.equal(rowPlayer(mixed.players, 99)?.seat, 2);
  assert.equal(rowPlayer(mixed.players)?.seat, 2);
  assert.equal(rowPlayer([] as never[], 1), undefined);
  assert.equal(handHistoryText({ raw_text: '  ' }), null);
  assert.equal(handHistoryText({ raw_text: null }), null);
  assert.equal(handHistoryText({ raw_text: 'Poker Hand #1' }), 'Poker Hand #1');
});

test('isGridKeyTarget: only rows and the grid scroll box; never menus, listboxes, dialogs, popovers or the panel', () => {
  const el = (tagName: string, opts: { scroll?: boolean; inside?: boolean } = {}) => ({
    tagName,
    closest: () => (opts.inside ? {} : null),
    hasAttribute: (n: string) => !!opts.scroll && n === 'data-grid-scroll',
  });
  assert.equal(isGridKeyTarget(el('TR')), true);
  assert.equal(isGridKeyTarget(el('DIV', { scroll: true })), true);
  assert.equal(isGridKeyTarget(el('DIV')), false);
  assert.equal(isGridKeyTarget(el('BUTTON')), false);
  // a row-like target inside a menu / dialog / aside is not the grid's
  assert.equal(isGridKeyTarget(el('TR', { inside: true })), false);
  assert.equal(isGridKeyTarget(el('DIV', { scroll: true, inside: true })), false);
});

test('exportCapNotice: warns before an export the server will cap', () => {
  assert.equal(exportCapNotice(100_000), null);
  assert.equal(exportCapNotice(5), null);
  assert.equal(exportCapNotice(undefined), null);
  assert.match(exportCapNotice(250_000) ?? '', /first 100k of 250k/);
});
