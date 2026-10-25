/** Run: cd frontend && npx tsx --test tests/perf-frontend-query-policy.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { QueryClient, QueryObserver, type QueryKey } from '@tanstack/query-core';
import {
  HEAVY_META, isHeavyQuery, isOutdatedOnScreen, isSessionChainQuery, isStaticQuery, refetchOutdatedOnScreen,
  refreshAfterDataChange, sessionQueriesToRefetch, sessionStepsOf, type SessionRowLike,
} from '../src/lib/query-policy.ts';

// The app's chain key part (lib/reports/api.ts queryKeyOf): [ws, player, chainParam(chain)]
const keyOf = (chain: unknown[]) => JSON.stringify([1, null, JSON.stringify(chain)]);

const flush = () => new Promise((r) => setTimeout(r, 0));

function client() {
  return new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, gcTime: Infinity, retry: 0, refetchOnWindowFocus: false } } });
}

/** A query with a fetch counter; `mount` adds an observer (a visible screen). */
function harness(qc: QueryClient) {
  const fetches = new Map<string, number>();
  const fn = (key: QueryKey) => async () => {
    const h = JSON.stringify(key);
    fetches.set(h, (fetches.get(h) ?? 0) + 1);
    return { at: fetches.get(h) };
  };
  const observers: QueryObserver[] = [];
  const mount = (queryKey: QueryKey, meta?: Record<string, unknown>) => {
    const o = new QueryObserver(qc, { queryKey, queryFn: fn(queryKey), meta });
    const unsub = o.subscribe(() => {});
    observers.push(o);
    return { o, unsub, move: (k: QueryKey) => o.setOptions({ queryKey: k, queryFn: fn(k), meta }) };
  };
  const count = (k: QueryKey) => fetches.get(JSON.stringify(k)) ?? 0;
  const total = () => [...fetches.values()].reduce((a, b) => a + b, 0);
  return { mount, count, total, fetches };
}

const q = (queryKey: QueryKey, meta?: Record<string, unknown>) => ({ queryKey, meta });

test('classification: heavy report / statistics / extras keys, cheap lists, static settings', () => {
  for (const k of [
    ['reports', 'spot', keyOf([])], ['reports', 'split', 'positions', keyOf([])], ['reports', 'graph', keyOf([])],
    ['reports', 'preflop-range', keyOf([])], ['reports', 'hand-strength', keyOf([]), 'flop'],
    ['general', 'grid', {}], ['general', 'detail', 'vpip', {}], ['general', 'hands', 'vpip', {}, 'all', 'date', 'desc'],
    ['population', 'overview', {}], ['stats', 'hero', {}], ['compare', 1, {}], ['players', 'list', {}],
    ['hands', 'list', { page: 1, chain: [] }],
  ]) assert.equal(isHeavyQuery(q(k)), true, JSON.stringify(k));
  for (const k of [
    ['workspaces'], ['heroes', 1], ['sessions', { workspace_id: 1 }], ['sessions', 'live', 1], ['checkpoints', 1],
    ['hands', 'list', { page: 1, marked: true }], ['hands', 'detail', 'x'], ['filter-options'], ['players', 'detail', 3],
    ['reports', 'quick-filters'],
  ]) assert.equal(isHeavyQuery(q(k)), false, JSON.stringify(k));
  assert.equal(isHeavyQuery(q(['anything'], HEAVY_META)), true);
  assert.equal(isStaticQuery(q(['auto-import', 'status'])), true);
  assert.equal(isStaticQuery(q(['config', 'auto_import'])), true);
  assert.equal(isStaticQuery(q(['reports', 'quick-filters'])), true);
  assert.equal(isStaticQuery(q(['workspaces'])), false);
  // Databases screen: db_size_bytes grows with every import
  assert.equal(isStaticQuery(q(['system', 'info'])), false);
});

test('session steps are found in string-encoded and object chains', () => {
  const step = { k: 'session', start: '2026-10-25T10:00:00', end: '2026-10-25T11:00:00' };
  assert.deepEqual(sessionStepsOf(['reports', 'spot', 'session', keyOf([step])]), [{ start: step.start, end: step.end }]);
  assert.deepEqual(sessionStepsOf(['hands', 'list', { page: 1, chain: [step, { k: 'table', v: ['T'] }] }]), [{ start: step.start, end: step.end }]);
  assert.deepEqual(sessionStepsOf(['reports', 'spot', keyOf([{ k: 'pos', v: ['BTN'] }])]), []);
  assert.equal(isSessionChainQuery(q(['reports', 'graph', keyOf([step])])), true);
  assert.equal(isSessionChainQuery(q(['reports', 'graph', keyOf([])])), false);
});

test('auto-import tick: before = every visible query refetches; after = only the cheap ones', async () => {
  const keys = {
    spot: ['reports', 'spot', keyOf([])], split: ['reports', 'split', 'positions', keyOf([])],
    graph: ['reports', 'graph', keyOf([])], hands: ['hands', 'list', { page: 1, chain: [] }],
    workspaces: ['workspaces'], heroes: ['heroes', 1], config: ['config', 'auto_import'],
  };
  const run = async (policy: 'before' | 'after') => {
    const qc = client();
    const h = harness(qc);
    for (const k of Object.values(keys)) h.mount(k);
    await flush();
    const base = h.total();
    if (policy === 'before') {
      // The old AutoImportIndicator: everything except the status poll, plus refetchWorkspaces()
      void qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== 'auto-import' });
      void qc.invalidateQueries({ queryKey: ['workspaces'] });
    } else {
      await refreshAfterDataChange(qc, 'auto-import');
    }
    await flush();
    return { qc, h, refetched: h.total() - base };
  };
  const before = await run('before');
  const after = await run('after');
  // before: 7 visible queries, the workspace list twice (second call cancels and restarts the first)
  assert.equal(before.refetched, 8);
  // after: workspaces + heroes; config untouched; the 4 heavy report queries keep their data
  assert.equal(after.refetched, 2);
  assert.equal(after.h.count(keys.spot), 1);
  const outdated = after.qc.getQueryCache().getAll().filter(isOutdatedOnScreen).map((x) => x.queryKey[1]);
  assert.deepEqual(outdated.sort(), ['graph', 'list', 'split', 'spot']);
  // The chip's Refresh: each heavy query once
  await refetchOutdatedOnScreen(after.qc);
  assert.equal(after.h.count(keys.spot), 2);
  assert.equal(after.h.count(keys.graph), 2);
  assert.equal(after.qc.getQueryCache().getAll().filter(isOutdatedOnScreen).length, 0);
});

test('auto-import: a heavy screen that is not showing refetches once when it mounts again', async () => {
  const qc = client();
  const h = harness(qc);
  const graph = ['reports', 'graph', keyOf([])];
  const m = h.mount(graph);
  await flush();
  m.unsub(); // left the screen
  for (let tick = 0; tick < 5; tick++) await refreshAfterDataChange(qc, 'auto-import');
  await flush();
  assert.equal(h.count(graph), 1, 'no refetch while hidden, whatever the number of ticks');
  h.mount(graph);
  await flush();
  assert.equal(h.count(graph), 2, 'one refetch on return');
});

test('auto-import tick during an in-flight heavy fetch: the chip shows once that fetch lands', async () => {
  const qc = client();
  let n = 0;
  let release: (() => void) | null = null;
  const key = ['reports', 'spot', keyOf([])];
  const o = new QueryObserver(qc, {
    queryKey: key,
    queryFn: () => new Promise((r) => { n++; release = () => r({ n }); }),
  });
  const unsub = o.subscribe(() => {});
  await flush();
  release!();
  await flush();
  void o.refetch(); // chip click / filter refetch: its data predates the tick below
  await flush();
  await refreshAfterDataChange(qc, 'auto-import');
  release!();
  await flush();
  const query = qc.getQueryCache().find({ queryKey: key })!;
  assert.equal(n, 2, 'the running fetch is not cancelled and not repeated');
  assert.equal(query.state.isInvalidated, true);
  assert.equal(isOutdatedOnScreen(query), true, 'New hands chip');
  void refetchOutdatedOnScreen(qc);
  await flush();
  release!();
  await flush();
  assert.equal(n, 3);
  assert.equal(isOutdatedOnScreen(query), false);
  // hidden after the race: the remount refetches
  void o.refetch();
  await flush();
  await refreshAfterDataChange(qc, 'auto-import');
  unsub();
  release!();
  await flush();
  assert.equal(query.state.isInvalidated, true);
  const o2 = new QueryObserver(qc, { queryKey: key, queryFn: () => new Promise((r) => { n++; release = () => r({ n }); }) });
  o2.subscribe(() => {});
  await flush();
  assert.equal(n, 5, 'one refetch on return');
});

test('manual import: the visible heavy screen refetches right away', async () => {
  const qc = client();
  const h = harness(qc);
  const spot = ['reports', 'spot', keyOf([])];
  h.mount(spot);
  await flush();
  await refreshAfterDataChange(qc, 'import');
  await flush();
  assert.equal(h.count(spot), 2);
  assert.equal(qc.getQueryCache().getAll().filter(isOutdatedOnScreen).length, 0);
});

// ── Sessions pages (05/S1) ──────────────────────────────────────────────────────────────────────

const START = '2026-10-25T10:00:00';
const row = (end: string, hands: number): SessionRowLike => ({
  filter: { k: 'session', start: START, end }, hands, last_hand_at: end, won: hands, won_bb: hands, won_ev: hands,
});
const pageKeys = (end: string) => {
  const chain = [{ k: 'session', start: START, end }];
  return [
    ['reports', 'spot', 'session', keyOf(chain)],
    ['reports', 'graph', keyOf(chain)],
    ['hands', 'list', { page: 1, per_page: 100, chain }],
    ['reports', 'split', 'tables', keyOf(chain)],
  ];
};

/** One tick on the Sessions page: data change, list refetch, pages follow the new row, reconcile. */
async function sessionTick(policy: 'before' | 'after', next: SessionRowLike, prev: SessionRowLike) {
  const qc = client();
  const h = harness(qc);
  const old = pageKeys(String(prev.filter.end));
  const pages = old.map((k) => h.mount(k));
  await flush();
  const base = h.total();
  if (policy === 'before') void qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== 'auto-import' });
  else void refreshAfterDataChange(qc, 'auto-import');
  await flush();
  // The list came back with `next`: page 0 renders with its filter (same key if the end did not move)
  const now = pageKeys(String(next.filter.end));
  pages.forEach((p, i) => p.move(now[i]));
  await flush();
  if (policy === 'after') {
    const plan = sessionQueriesToRefetch(qc.getQueryCache().findAll({ predicate: isSessionChainQuery }), [prev], [next]);
    for (const x of plan.remove) qc.getQueryCache().remove(x);
    const due = new Set(plan.refetch);
    await qc.refetchQueries({ predicate: (x) => due.has(x), type: 'active' });
  }
  await flush();
  return { fetched: h.total() - base, cached: qc.getQueryCache().findAll({ predicate: isSessionChainQuery }).length };
}

test('live session tick, window moved: before = 2 fetches per page query, after = 1', async () => {
  const prev = row('2026-10-25T10:30:00', 100);
  const next = row('2026-10-25T10:31:00', 103);
  const before = await sessionTick('before', next, prev);
  const after = await sessionTick('after', next, prev);
  assert.equal(before.fetched, 8); // 4 queries x (old chain + new chain)
  assert.equal(after.fetched, 4);
  assert.equal(after.cached, 4, 'the old-window entries are dropped');
});

test('session tick, same window but more hands (a hand inside the window): refetched once', async () => {
  const prev = row('2026-10-25T10:30:00', 100);
  const next = row('2026-10-25T10:30:00', 101);
  const after = await sessionTick('after', next, prev);
  assert.equal(after.fetched, 4);
});

test('session tick, row unchanged (hands went to another session): nothing refetched', async () => {
  const prev = row('2026-10-25T10:30:00', 100);
  const after = await sessionTick('after', prev, prev);
  assert.equal(after.fetched, 0);
});

test('Refresh button (force): visible session queries refetch once even if the row is unchanged', async () => {
  const qc = client();
  const h = harness(qc);
  const r = row('2026-10-25T10:30:00', 100);
  for (const k of pageKeys(String(r.filter.end))) h.mount(k);
  await flush();
  void qc.invalidateQueries({ predicate: isSessionChainQuery, refetchType: 'none' });
  const plan = sessionQueriesToRefetch(qc.getQueryCache().findAll({ predicate: isSessionChainQuery }), [r], [r], true);
  assert.equal(plan.refetch.length, 4);
  const due = new Set(plan.refetch);
  await qc.refetchQueries({ predicate: (x) => due.has(x), type: 'active' });
  assert.equal(h.total(), 8);
});

test('date-filter change (new list, not invalidated): session pages are not refetched', () => {
  const qc = client();
  const r = row('2026-10-25T10:30:00', 100);
  for (const k of pageKeys(String(r.filter.end))) {
    const o = new QueryObserver(qc, { queryKey: k, queryFn: async () => 1, enabled: true });
    o.subscribe(() => {});
  }
  const fewer = { ...r, hands: 40 }; // in-range hands only
  const plan = sessionQueriesToRefetch(qc.getQueryCache().findAll({ predicate: isSessionChainQuery }), [r], [fewer]);
  assert.equal(plan.refetch.length, 0);
});
