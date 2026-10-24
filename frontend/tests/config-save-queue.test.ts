import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createSaveQueue } from '../src/lib/config/saveQueue.ts';
import { listParamsMatchPlayer, patchRow } from '../src/lib/marked/logic.ts';

const tick = () => new Promise((r) => setTimeout(r, 0));

test('save queue: one in flight, latest pending wins', async () => {
  const sent: number[] = [];
  const saved: [number, boolean][] = [];
  const gates: (() => void)[] = [];
  const q = createSaveQueue<number, number>({
    send: (v) => new Promise((res) => { sent.push(v); gates.push(() => res(v)); }),
    onSaved: (r, more) => saved.push([r, more]),
    onFailed: () => assert.fail('no failure expected'),
  });
  q.push(1);
  q.push(2);
  q.push(3);
  assert.deepEqual(sent, [1]);
  assert.equal(q.idle(), false);
  gates[0]();
  await tick();
  assert.deepEqual(sent, [1, 3]);
  gates[1]();
  await tick();
  assert.deepEqual(saved, [[1, true], [3, false]]);
  assert.equal(q.idle(), true);
});

test('save queue: failure drops the queue and reports once', async () => {
  const errors: string[] = [];
  const sent: number[] = [];
  const q = createSaveQueue<number, number>({
    send: async (v) => { sent.push(v); throw new Error('nope'); },
    onSaved: () => assert.fail('no success expected'),
    onFailed: (e) => errors.push(e.message),
  });
  q.push(1);
  q.push(2);
  await tick();
  await tick();
  assert.deepEqual(errors, ['nope']);
  assert.equal(q.idle(), true);
  q.push(4);
  await tick();
  assert.deepEqual(sent.at(-1), 4);
});

test('patchRow only touches the row of that hand and player', () => {
  const rows = [
    { id: 'a', player_id: 1, marked: false, tags: [] },
    { id: 'a', player_id: 2, marked: false, tags: [] },
    { id: 'b', player_id: 1, marked: false, tags: [] },
  ];
  const out = patchRow(rows, { hand_id: 'a', marked: true, tags: [] }, 2);
  assert.deepEqual(out.map((r) => r.marked), [false, true, false]);
  assert.equal(patchRow(rows, { hand_id: 'a', marked: true, tags: [] }).filter((r) => r.marked).length, 2);
});

test('listParamsMatchPlayer', () => {
  assert.equal(listParamsMatchPlayer({ player_id: 3 }, 3), true);
  assert.equal(listParamsMatchPlayer({ player_id: 3 }, 4), false);
  assert.equal(listParamsMatchPlayer({}, 4), true);
  assert.equal(listParamsMatchPlayer({ player_id: 3 }, undefined), true);
});

test('stored appearance parsing', async () => {
  const { parseStoredAppearance } = await import('../src/lib/format/appearance-cache.ts');
  const ok = { one_decimal_below: 10, show_99_for_100: true, leading_zero: false, shorten_amounts: true, show_sample_below: 15, dim_below: 10, vs_user_substitute_above: 50 };
  assert.deepEqual(parseStoredAppearance(JSON.stringify(ok)), ok);
  assert.equal(parseStoredAppearance(null), null);
  assert.equal(parseStoredAppearance('{'), null);
  assert.equal(parseStoredAppearance(JSON.stringify({ ...ok, dim_below: 'x' })), null);
});
