/**
 * Unit tests for src/lib/general-notation.ts (stat popup + hands list notation).
 * Vectors from docs/specs/H2N-COMPATIBLE-STATS.md sections 3.1, 6.1, 6.4, 6.7.
 *
 * Run: cd frontend && npx tsx --test tests/general-notation.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  barWidthPct,
  cardParts,
  denoise,
  formatBbAmount,
  formatFrequency,
  formatHandDate,
  formatRangeCount,
  formatRatio,
  formatSignedBb,
  formatWeak,
  popupTitle,
  positionClass,
  splitTokens,
  tokenText,
} from '../src/lib/general-notation';

test('bb amounts: one decimal below 5, whole numbers from 5, half to even', () => {
  assert.equal(formatBbAmount(2.6), '2.6');
  assert.equal(formatBbAmount(4), '4');
  assert.equal(formatBbAmount(3.0), '3');
  assert.equal(formatBbAmount(16), '16');
  assert.equal(formatBbAmount(4.5), '4.5');
  // GG examples: 5.5bb flop pot -> "6" (half to even), 2bb -> "2", 4.5 -> "4.5"
  assert.equal(formatBbAmount(5.5), '6');
  assert.equal(formatBbAmount(6.5), '6');
  assert.equal(formatBbAmount(2), '2');
  // float noise from the backend
  assert.equal(formatBbAmount(4.199999999999999), '4.2');
  assert.equal(formatBbAmount(6.000000000000001), '6');
  assert.equal(formatBbAmount(1.4999999999999998), '1.5');
  assert.equal(formatBbAmount(8.499999999999998), '8'); // 8.5 -> 8 (even)
  assert.equal(formatBbAmount(9.499999999999998), '10'); // 9.5 -> 10 (even), not 9
  assert.equal(formatBbAmount(4.96), '5');
  assert.equal(denoise(0.1 + 0.2), 0.3);
});

test('signed bb amounts for the won / EV columns', () => {
  assert.equal(formatSignedBb(3.2), '+3.2');
  assert.equal(formatSignedBb(-12.4), '-12');
  assert.equal(formatSignedBb(0), '0');
  assert.equal(formatSignedBb(-0.01), '0');
  assert.equal(formatSignedBb(null), '');
});

test('action tokens', () => {
  assert.equal(tokenText({ t: 'R', amt_bb: 3 }), 'R3');
  assert.equal(tokenText({ t: 'C', amt_bb: 2.6 }), 'C2.6');
  assert.equal(tokenText({ t: 'X', amt_bb: null }), 'X');
  assert.equal(tokenText({ t: 'F' }), 'F');
  assert.equal(tokenText({ t: 'B', amt_bb: 16.2 }), 'B16');
  assert.equal(tokenText({ t: 'R', amt_bb: 25, allin: true }), "R25'");
});

test('at most three tokens per street, the rest behind +N', () => {
  const four = ['X', 'B4', 'R12', 'C8'];
  assert.deepEqual(splitTokens(four, false), { shown: ['X', 'B4', 'R12'], hidden: 1 });
  assert.deepEqual(splitTokens(four, true), { shown: four, hidden: 0 });
  assert.deepEqual(splitTokens(['X', 'B4', 'R8', 'R20', 'C12'], false).hidden, 2);
  assert.deepEqual(splitTokens(['X', 'X'], false), { shown: ['X', 'X'], hidden: 0 });
});

test('position colours: the General column tokens', () => {
  assert.equal(positionClass('BTN'), 'text-pos-btn');
  assert.equal(positionClass('CO'), 'text-pos-co');
  assert.equal(positionClass('MP'), 'text-pos-mp');
  assert.equal(positionClass('EP'), 'text-pos-ep');
  assert.equal(positionClass('SB'), 'text-pos-sb');
  assert.equal(positionClass('bb'), 'text-pos-bb');
  assert.equal(positionClass(''), 'text-foreground');
  assert.equal(positionClass('XX'), 'text-foreground');
});

test('Range tab frequency, weak label and counts (screenshot numbers)', () => {
  assert.equal(formatFrequency(142, 1299), '11%');
  assert.equal(formatFrequency(174, 1299), '13%');
  assert.equal(formatFrequency(22, 1299), '2%');
  assert.equal(formatFrequency(0, 1299), '0%');
  assert.equal(formatFrequency(0, 0), '0%');
  assert.equal(formatWeak(626, 1299), '48% weak');
  assert.equal(formatWeak(0, 0), '');
  assert.equal(formatRangeCount(142), '142');
  assert.equal(formatRangeCount(1000), '1k');
  assert.equal(formatRangeCount(1250), '1.2k');
  assert.equal(formatRangeCount(1299), '1.3k');
  assert.equal(formatRangeCount(9960), '10k');
  assert.equal(formatRangeCount(12000), '12k');
  assert.equal(barWidthPct(87, 174), 50);
  assert.equal(barWidthPct(0, 174), 0);
});

test('ratios use the stat-value rules', () => {
  assert.deepEqual(formatRatio({ cases: 0, opps: 0 }), { text: '--', sampleText: null, opacity: 0.5 });
  assert.equal(formatRatio({ cases: 3, opps: 3 }).text, '99');
  assert.equal(formatRatio({ cases: 3, opps: 3 }).sampleText, '3');
  assert.equal(formatRatio({ cases: 1156, opps: 1616 }).text, '72');
  assert.equal(formatRatio({ cases: 6, opps: 100 }).text, '6');
  assert.equal(formatRatio({ cases: 23, opps: 40 }).text, '57');
  assert.equal(formatRatio({ cases: 12, opps: 12 }).opacity, 1);
  assert.equal(formatRatio({ cases: 9, opps: 9 }).opacity, 0.5);
});

test('cards, dates, titles', () => {
  assert.deepEqual(cardParts('Ah'), { rank: 'A', suit: 'h' });
  assert.deepEqual(cardParts('10d'), { rank: 'T', suit: 'd' });
  assert.equal(cardParts('?'), null);
  assert.equal(formatHandDate('2026-01-23 14:02:31'), '2026-01-23 14:02');
  assert.equal(formatHandDate('2026-01-23T14:02:31Z'), '2026-01-23 14:02');
  assert.equal(popupTitle('Open Raise -> Continuation Bet'), 'Open Raise → Continuation Bet');
});
