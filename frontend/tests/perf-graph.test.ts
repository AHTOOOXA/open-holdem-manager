/** Run: cd frontend && npx tsx --test tests/perf-graph.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { graphHands, lastHandNumber } from '../src/components/results/graph-hands.ts';
import type { GraphPoint } from '../src/lib/api.ts';

const pt = (hand_number: number): GraphPoint => ({
  hand_number, played_at: '', cumulative_bb: 0, cumulative_ev_bb: 0, cumulative_rake_bb: 0,
  cumulative_jackpot_bb: 0, cumulative_showdown_bb: 0, cumulative_nonshowdown_bb: 0, cumulative_usd: 0,
  cumulative_ev_usd: 0, cumulative_rake_usd: 0, cumulative_jackpot_usd: 0, cumulative_showdown_usd: 0,
  cumulative_nonshowdown_usd: 0,
});

test('hand count comes from `hands`, not from the number of sampled points', () => {
  const points = [pt(1), pt(215), pt(429), pt(214188)];
  assert.equal(graphHands({ points, hands: 214188 }), 214188);
  assert.notEqual(graphHands({ points, hands: 214188 }), points.length);
});

test('without `hands` (old responses, landing mocks) the last point decides', () => {
  assert.equal(graphHands({ points: [pt(1), pt(2), pt(3)] }), 3);
  assert.equal(graphHands({ points: [pt(1), pt(500), pt(34702)] }), 34702);
  assert.equal(graphHands({ points: [] }), 0);
  assert.equal(graphHands(undefined), 0);
  assert.equal(graphHands(null), 0);
});

test('lastHandNumber', () => {
  assert.equal(lastHandNumber([]), 0);
  assert.equal(lastHandNumber([pt(7), pt(9000)]), 9000);
});
