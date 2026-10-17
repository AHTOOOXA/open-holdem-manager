/**
 * Unit tests for src/lib/h2n-format.ts (General screen value formatting and
 * sample-size display). Vectors from docs/specs/H2N-COMPATIBLE-STATS.md
 * sections 3.1-3.5.
 *
 * Run: cd frontend && npx tsx --test tests/h2n-format.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  actionPercent,
  formatBb100,
  formatHands,
  formatPercent,
  formatStatValue,
  resolveCellDisplay,
  roundHalfEven,
  roundHalfEvenInt,
  sampleOpacity,
  shortenAmount,
  shortenCount,
  shouldDim,
  shouldShowSample,
} from '../src/lib/h2n-format';

/** Format an action stat the way a cell does: divide, then multiply by 100. */
function pct(cases: number, opps: number): string {
  return formatPercent(actionPercent(cases, opps), opps);
}

test('round half to even on the exact double', () => {
  assert.equal(roundHalfEvenInt(0.5), 0);
  assert.equal(roundHalfEvenInt(1.5), 2);
  assert.equal(roundHalfEvenInt(2.5), 2);
  assert.equal(roundHalfEvenInt(3.5), 4);
  assert.equal(roundHalfEvenInt(12.5), 12);
  assert.equal(roundHalfEvenInt(37.5), 38);
  assert.equal(roundHalfEvenInt(-2.5), -2);
  assert.equal(roundHalfEvenInt(2.5000001), 3);
  assert.ok(Object.is(roundHalfEvenInt(-0.4), -0));
  // Scaled rounding: 0.25 * 10 = 2.5 -> 2, 0.75 * 10 = 7.5 -> 8.
  assert.equal(roundHalfEven(0.25, 1), 0.2);
  assert.equal(roundHalfEven(0.75, 1), 0.8);
  assert.equal(roundHalfEven(0.456, 2), 0.46);
  assert.equal(roundHalfEven(9.96, 1), 10);
});

test('percent: basic vectors (cases/opps)', () => {
  assert.equal(formatPercent(NaN, 0), '--');
  assert.equal(formatPercent(actionPercent(0, 0), 0), '--');
  assert.equal(pct(26, 100), '26');
  assert.equal(pct(19, 200), '9.5');
  assert.equal(pct(2, 21), '9.5');
  assert.equal(pct(1, 8), '12'); // 12.5 half-even
  assert.equal(pct(3, 8), '38'); // 37.5 half-even
  assert.equal(pct(1, 400), '0.2'); // 0.25 half-even
  assert.equal(pct(3, 400), '0.8');
  assert.equal(pct(1, 250), '0.4');
  assert.equal(pct(0, 7), '0');
});

test('percent: exactly 100 shows 99, but 99.6 rounds to 100', () => {
  assert.equal(pct(5, 5), '99');
  assert.equal(pct(3, 3), '99');
  assert.equal(pct(249, 250), '100'); // 99.6
  assert.equal(pct(199, 200), '100'); // 99.5 half-even -> 100
});

test('percent: evaluation order c/o*100, not c*100/o', () => {
  // c/o*100 lands just below / above the midpoint; c*100/o lands exactly on it.
  assert.equal(actionPercent(23, 40), 57.49999999999999);
  assert.equal(pct(23, 40), '57');
  assert.equal(formatPercent((23 * 100) / 40, 40), '58'); // the wrong order, for contrast
  assert.equal(pct(46, 80), '57');
  assert.equal(pct(1150, 2000), '57');
  assert.equal(pct(109, 200), '55');
  assert.equal(formatPercent((109 * 100) / 200, 200), '54');
  assert.equal(pct(545, 1000), '55');
  // One-decimal pairs.
  assert.equal(pct(11, 2000), '0.5');
  assert.equal(pct(29, 2000), '1.5');
  assert.equal(pct(41, 2000), '2.1');
  assert.equal(pct(59, 2000), '2.9');
  assert.equal(pct(97, 2000), '4.9');
  assert.equal(pct(101, 2000), '5.1');
  assert.equal(pct(103, 2000), '5.1');
  assert.equal(pct(117, 2000), '5.9');
  assert.equal(pct(119, 2000), '5.9');
  assert.equal(pct(169, 2000), '8.5');
});

test('percent: aggression-style values and infinities', () => {
  assert.equal(formatPercent(3.14), '3.1');
  assert.equal(formatPercent(2.0), '2');
  assert.equal(formatPercent(12.6), '13');
  assert.equal(formatPercent(7 / 0), '∞');
  assert.equal(formatPercent(-7 / 0), '-∞');
  assert.equal(formatPercent(0 / 0), '--');
  // |v| > 100: truncated then shortened.
  assert.equal(formatPercent(150.9), '150');
  assert.equal(formatPercent(1250.7), '1.2k');
  assert.equal(formatPercent(-150.9), '-150');
});

test('bb/100 formatting and shortening', () => {
  assert.equal(formatBb100(null), '--');
  assert.equal(formatBb100(NaN), '--');
  assert.equal(formatBb100(Infinity), '∞');
  assert.equal(formatBb100(9.83), '9.8');
  assert.equal(formatBb100(0.456), '0.46');
  assert.equal(formatBb100(-0.456), '-0.46');
  assert.equal(formatBb100(15.5), '16');
  assert.equal(formatBb100(-12.3), '-12');
  assert.equal(formatBb100(999.4), '999');
  assert.equal(formatBb100(1234), '1234'); // not a multiple of 100
  assert.equal(formatBb100(1200.2), '1.2k'); // rounds to 1200
  assert.equal(formatBb100(-3000), '-3k');
  assert.equal(shortenAmount(12345), '12.3k');
  assert.equal(shortenAmount(15000), '15k');
  assert.equal(shortenAmount(250000), '250k');
  // bb/100 with no hands is "--" through the generic formatter too.
  assert.equal(formatStatValue(5, 'bb100', 0), '--');
});

test('hand count shortening', () => {
  assert.equal(formatHands(999), '999');
  assert.equal(formatHands(1250), '1.2k');
  assert.equal(formatHands(44_499), '44k');
  assert.equal(formatHands(44_500), '44k'); // 44.5 half-even
  assert.equal(formatHands(45_500), '46k'); // 45.5 half-even
  assert.equal(formatHands(null), '--');
  assert.equal(shortenCount(0), '0');
  assert.equal(shortenCount(2_500_000), '2.5m');
  assert.equal(shortenCount(25_000_000), '25m');
});

test('sample subscript shows for 0 < sample < 15', () => {
  assert.equal(shouldShowSample(0), false);
  assert.equal(shouldShowSample(1), true);
  assert.equal(shouldShowSample(14), true);
  assert.equal(shouldShowSample(15), false);
  assert.equal(shouldShowSample(null), false);
});

test('dimming applies for sample < 10, including 0', () => {
  assert.equal(shouldDim(0), true);
  assert.equal(shouldDim(9), true);
  assert.equal(shouldDim(10), false);
  assert.equal(shouldDim(null), false);
  assert.equal(sampleOpacity(9), 0.5);
  assert.equal(sampleOpacity(10), 1);
});

test('resolved cell display combines value, sample and opacity', () => {
  assert.deepEqual(resolveCellDisplay({ cases: 3, opps: 11 }), {
    text: '27',
    sampleText: '11',
    opacity: 1,
    vsUser: false,
  });
  assert.deepEqual(resolveCellDisplay({ cases: 3, opps: 9 }), {
    text: '33',
    sampleText: '9',
    opacity: 0.5,
    vsUser: false,
  });
  assert.deepEqual(resolveCellDisplay({ cases: 0, opps: 0 }), {
    text: '--',
    sampleText: null,
    opacity: 0.5,
    vsUser: false,
  });
  assert.equal(resolveCellDisplay({ cases: 7, opps: 20 }).sampleText, null);
  // Hands: no sample text, dimmed below 10 hands.
  assert.deepEqual(resolveCellDisplay({ value: 9 }, 'count'), {
    text: '9',
    sampleText: null,
    opacity: 0.5,
    vsUser: false,
  });
  assert.equal(resolveCellDisplay({ value: 44_500 }, 'count').text, '44k');
  // Expression with no sample is never dimmed.
  assert.equal(resolveCellDisplay({ value: 3.14, sample: null }).opacity, 1);
  // Vs-user substitution only above 50.
  const base = { cases: 100, opps: 400 };
  assert.equal(resolveCellDisplay({ ...base, vs_user: { cases: 30, opps: 60, sample: 60 } }).text, '50');
  assert.equal(resolveCellDisplay({ ...base, vs_user: { cases: 30, opps: 60, sample: 60 } }).vsUser, true);
  assert.equal(resolveCellDisplay({ ...base, vs_user: { cases: 25, opps: 50, sample: 50 } }).text, '25');
});
