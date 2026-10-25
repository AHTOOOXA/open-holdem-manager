/**
 * Auto-import refresh of the visible heavy screen (perf/incremental, INCREMENTAL-CACHES.md step 2).
 * Run: cd frontend && npx tsx --test tests/perf-incremental-query-policy.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { QueryClient, QueryObserver, type QueryKey } from '@tanstack/query-core';
import {
  AUTO_REFRESH_DEBOUNCE_MS, SLOW_REFRESH_MS, isOutdatedOnScreen, refetchOutdatedOnScreen, refreshAfterDataChange,
} from '../src/lib/query-policy.ts';

const keyOf = (chain: unknown[]) => JSON.stringify([1, null, JSON.stringify(chain)]);
const flush = () => new Promise((r) => setTimeout(r, 0));
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const settle = () => sleep(AUTO_REFRESH_DEBOUNCE_MS + 30);

function client() {
  return new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, gcTime: Infinity, retry: 0, refetchOnWindowFocus: false } } });
}

/** A visible query whose fetches resolve when `release()` is called (or at once when `auto`). */
function manual(qc: QueryClient, queryKey: QueryKey, auto = false) {
  const st = { started: 0, done: 0, aborted: 0, pending: [] as (() => void)[] };
  const o = new QueryObserver(qc, {
    queryKey,
    queryFn: ({ signal }) =>
      new Promise((resolve) => {
        st.started++;
        const n = st.started;
        signal.addEventListener('abort', () => st.aborted++);
        const fin = () => {
          st.done++;
          resolve({ n });
        };
        if (auto) fin();
        else st.pending.push(fin);
      }),
  });
  const unsub = o.subscribe(() => {});
  const release = () => {
    const fns = st.pending.splice(0);
    for (const f of fns) f();
  };
  return { st, o, unsub, release, query: () => qc.getQueryCache().find({ queryKey })! };
}

test('ticks within the debounce window: one refresh of the visible heavy screen', async () => {
  const qc = client();
  const spot = manual(qc, ['reports', 'spot', keyOf([])], true);
  const general = manual(qc, ['general', 'grid', {}], true);
  await flush();
  for (let i = 0; i < 4; i++) {
    void refreshAfterDataChange(qc, 'auto-import');
    await sleep(AUTO_REFRESH_DEBOUNCE_MS / 4);
  }
  assert.equal(spot.st.started, 1, 'nothing yet: the ticks keep pushing the refresh back');
  await settle();
  assert.equal(spot.st.started, 2);
  assert.equal(general.st.started, 2);
  assert.equal(qc.getQueryCache().getAll().filter(isOutdatedOnScreen).length, 0);
});

test('a slow refresh is never cancelled by the next ticks and is followed by exactly one more', async () => {
  const qc = client();
  const spot = manual(qc, ['reports', 'spot', keyOf([{ k: 'row', key: 'P01' }])]);
  await flush();
  spot.release();
  await flush();
  await refreshAfterDataChange(qc, 'auto-import');
  await settle();
  assert.equal(spot.st.started, 2, 'the tick refresh is running');
  for (let i = 0; i < 5; i++) {
    // more ticks while it runs (auto-import every few seconds, a cold server compute)
    await refreshAfterDataChange(qc, 'auto-import');
    await settle();
  }
  assert.equal(spot.st.started, 2, 'not cancelled, not doubled');
  assert.equal(spot.st.aborted, 0);
  spot.release();
  await flush();
  assert.equal(spot.query().state.isInvalidated, true, 'its data predates the later ticks');
  await settle();
  assert.equal(spot.st.started, 3, 'one refresh for all the ticks that landed meanwhile');
  spot.release();
  await flush();
  assert.equal(spot.st.done, 3);
  assert.equal(spot.query().state.isInvalidated, false);
  await settle();
  assert.equal(spot.st.started, 3, 'and nothing after it');
});

test('hidden heavy screens stay stale through ticks and refetch once when shown', async () => {
  const qc = client();
  const graph = manual(qc, ['reports', 'graph', keyOf([])], true);
  await flush();
  graph.unsub();
  for (let i = 0; i < 3; i++) await refreshAfterDataChange(qc, 'auto-import');
  await settle();
  assert.equal(graph.st.started, 1);
  assert.equal(graph.query().state.isInvalidated, true);
  const again = new QueryObserver(qc, { queryKey: ['reports', 'graph', keyOf([])], queryFn: async () => ({ n: 99 }) });
  again.subscribe(() => {});
  await flush();
  assert.equal(graph.query().state.data && (graph.query().state.data as { n: number }).n, 99);
});

test('session pages are left to SessionsPage; cheap and system queries refetch at once', async () => {
  const qc = client();
  const step = { k: 'session', start: '2026-10-25T10:00:00', end: '2026-10-25T11:00:00' };
  const session = manual(qc, ['reports', 'spot', 'session', keyOf([step])], true);
  const system = manual(qc, ['system', 'info'], true);
  const status = manual(qc, ['auto-import', 'status'], true);
  await flush();
  await refreshAfterDataChange(qc, 'auto-import');
  await flush();
  assert.equal(system.st.started, 2, 'Databases screen: db size grows with every import');
  assert.equal(status.st.started, 1);
  await settle();
  assert.equal(session.st.started, 1);
});

test('a refresh slower than SLOW_REFRESH_MS falls back to the New hands chip until a refresh is fast', async () => {
  const realNow = Date.now;
  let clock = 1_000_000;
  Date.now = () => clock;
  try {
    const qc = client();
    const spot = manual(qc, ['reports', 'spot', keyOf([{ k: 'row', key: 'C01' }])]);
    await flush();
    spot.release();
    await flush();
    // tick 1: the refresh takes longer than SLOW_REFRESH_MS (a cold server compute)
    await refreshAfterDataChange(qc, 'auto-import');
    await settle();
    assert.equal(spot.st.started, 2);
    clock += SLOW_REFRESH_MS + 1;
    spot.release();
    await flush();
    // tick 2: no automatic refresh, the chip instead
    await refreshAfterDataChange(qc, 'auto-import');
    await settle();
    assert.equal(spot.st.started, 2);
    assert.equal(isOutdatedOnScreen(spot.query()), true, 'New hands chip');
    // the chip's Refresh, fast this time: automatic refreshes resume
    const done = refetchOutdatedOnScreen(qc);
    await flush();
    assert.equal(spot.st.started, 3);
    spot.release();
    await done;
    assert.equal(isOutdatedOnScreen(spot.query()), false);
    await refreshAfterDataChange(qc, 'auto-import');
    assert.equal(isOutdatedOnScreen(spot.query()), false, 'no chip: a refresh is due');
    await settle();
    assert.equal(spot.st.started, 4);
    spot.release();
    await flush();
  } finally {
    Date.now = realNow;
  }
});

test('manual import and rebuild still refetch the visible heavy screen right away', async () => {
  const qc = client();
  const spot = manual(qc, ['reports', 'spot', keyOf([])], true);
  await flush();
  await refreshAfterDataChange(qc, 'import');
  await flush();
  assert.equal(spot.st.started, 2);
  await refreshAfterDataChange(qc, 'all');
  await flush();
  assert.equal(spot.st.started, 3);
  await settle();
  assert.equal(spot.st.started, 3);
});
