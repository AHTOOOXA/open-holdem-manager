// Hand list performance changes (performance/03-hands-lists.md): cancellable list / detail requests (F4),
// mark / unmark refetches only the lists a mark can change (F6), one shared hand-detail cache entry (F10).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getHandDetail, getHands, setWorkspaceIdGetter } from '../src/lib/api';
import { listDependsOnMarks } from '../src/components/marked/markInvalidation';
import { handDetailKey, handDetailQuery } from '../src/components/hands/handDetailQuery';
import { queryKeys } from '../src/lib/query-keys';

function captureFetch(): { calls: { url: string; init?: RequestInit }[]; restore: () => void } {
  const calls: { url: string; init?: RequestInit }[] = [];
  const orig = globalThis.fetch;
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify({ hands: [], total: 0, page: 1, per_page: 50, total_pages: 0 }), { status: 200 });
  }) as typeof fetch;
  return { calls, restore: () => { globalThis.fetch = orig; } };
}

test('getHands and getHandDetail pass the AbortSignal to fetch', async () => {
  setWorkspaceIdGetter(() => 3);
  const f = captureFetch();
  try {
    const ac = new AbortController();
    await getHands({ page: 2, chain: [] }, ac.signal);
    await getHandDetail('RC1', 7, ac.signal);
    assert.equal(f.calls.length, 2);
    assert.equal(f.calls[0].init?.signal, ac.signal);
    assert.equal(f.calls[1].init?.signal, ac.signal);
    assert.match(f.calls[0].url, /\/hands\?page=2&chain=.*workspace_id=3/);
    assert.match(f.calls[1].url, /\/hands\/RC1\?.*player_id=7/);
    await getHands({ page: 1 });
    assert.equal(f.calls[2].init?.signal, undefined);
  } finally {
    f.restore();
  }
});

test('a mark only refetches lists filtered on marks / tags or sorted by tags', () => {
  assert.equal(listDependsOnMarks(undefined), false);
  assert.equal(listDependsOnMarks({}), false);
  assert.equal(listDependsOnMarks({ page: 3, sort: 'won_bb', chain: [], player_id: 4 }), false);
  assert.equal(listDependsOnMarks({ marked: undefined, tag_ids: [] }), false);
  assert.equal(listDependsOnMarks({ marked: true }), true);
  assert.equal(listDependsOnMarks({ marked: false }), true);
  assert.equal(listDependsOnMarks({ tag_ids: [2] }), true);
  assert.equal(listDependsOnMarks({ sort: 'tags', order: 'asc' }), true);
});

test('hand detail: one cache key per (hand, row player) under the hands.detail prefix', () => {
  assert.deepEqual(handDetailKey('RC1'), ['hands', 'detail', 'RC1', null]);
  assert.deepEqual(handDetailKey('RC1', 5), ['hands', 'detail', 'RC1', 5]);
  assert.deepEqual(handDetailKey('RC1', 5).slice(0, 3), [...queryKeys.hands.detail('RC1')]);
  assert.deepEqual(handDetailQuery('RC1', 5).queryKey, handDetailKey('RC1', 5));
});
