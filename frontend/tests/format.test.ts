import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  bb,
  bb100,
  bbUnits,
  count,
  delta,
  fixed,
  formatCheckpointDateTime,
  formatClockTime,
  formatHHMM,
  formatLocalDate,
  formatMediumDate,
  moneyClass,
  moneyTone,
  pct,
  roundHalfEven,
  signed,
  signedBb,
  signedUsd,
  toneClass,
  trimmed,
  usd,
} from '../src/lib/format/index.ts';

test('banker rounding', () => {
  assert.equal(roundHalfEven(0.125, 2), 0.12);
  assert.equal(roundHalfEven(0.135, 2), 0.14);
  assert.equal(fixed(0.125, 2), '0.12');
  assert.equal(fixed(0.135, 2), '0.14');
  assert.equal(fixed(2.25, 1), '2.2');
  assert.equal(fixed(2.5, 0), '2');
  assert.equal(fixed(3.5, 0), '4');
});

test('fixed never prints negative zero', () => {
  assert.equal(fixed(-0.04, 1), '0.0');
  assert.equal(fixed(-0, 2), '0.00');
  assert.equal(fixed(-1.26, 1), '-1.3');
});

test('pct / bb / bb100', () => {
  assert.equal(pct(12.34), '12.3%');
  assert.equal(pct(7, 0), '7%');
  assert.equal(bb(6), '6');
  assert.equal(bb(3.5), '3.5');
  assert.equal(bb(3.456), '3.46');
  assert.equal(bb(10, 0), '10');
  assert.equal(trimmed(100, 1), '100');
  assert.equal(bb100(1.2), '1.20');
  assert.equal(bb100(-0.004), '0.00');
  assert.equal(bbUnits(12.34), '12.3 BB');
});

test('usd and signed variants', () => {
  assert.equal(usd(3.5), '$3.50');
  assert.equal(usd(-3.5), '-$3.50');
  assert.equal(usd(-0.001), '$0.00');
  assert.equal(signedUsd(3.5), '+$3.50');
  assert.equal(signedUsd(-3.5), '-$3.50');
  assert.equal(signedUsd(0), '$0.00');
  assert.equal(signed(1.25, 1), '+1.2');
  assert.equal(signed(-1.25, 1), '-1.2');
  assert.equal(signed(0.01, 1), '0.0');
  assert.equal(signedBb(3.25), '+3.2');
  assert.equal(signedBb(-12, 0), '-12');
});

test('count shortening and delta', () => {
  assert.equal(count(999), '999');
  assert.equal(count(1250), '1.2k');
  assert.equal(count(44500), '44k');
  assert.equal(count(1_000_000), '1m');
  assert.equal(count(2_500_000), '2.5m');
  assert.equal(delta(10, 11.5), '+1.5');
  assert.equal(delta(10, 9.7), '-0.3');
  assert.equal(delta(10, 10), '0.0');
  assert.equal(delta(1, 1.5, 2), '+0.50');
});

test('moneyTone zero rule', () => {
  assert.equal(moneyTone(1), 'pos');
  assert.equal(moneyTone(-1), 'neg');
  assert.equal(moneyTone(0), 'zero');
  assert.equal(moneyTone(0.004), 'zero');
  assert.equal(moneyTone(-0.004), 'zero');
  assert.equal(moneyTone(0.005), 'pos');
  assert.equal(moneyTone(-0.005), 'neg');
  assert.equal(moneyTone(0.04, 1), 'zero');
  assert.equal(moneyTone(0.05, 1), 'pos');
  assert.equal(moneyTone(NaN), 'zero');
  assert.equal(toneClass('pos'), 'text-money-pos');
  assert.equal(toneClass('neg'), 'text-money-neg');
  assert.equal(toneClass('zero'), 'text-money-zero');
  assert.equal(moneyClass(-3), 'text-money-neg');
});

test('date helpers', () => {
  const d = new Date(2026, 0, 5, 9, 7);
  assert.equal(formatLocalDate(d), '2026-01-05');
  assert.equal(formatHHMM(d), '09:07');
  assert.equal(formatClockTime(''), '');
  assert.equal(formatClockTime(d.toISOString()), '09:07');
  assert.equal(formatMediumDate(null), '—');
  assert.equal(formatMediumDate(d.toISOString()), 'Jan 5, 2026');
  assert.equal(formatCheckpointDateTime(d.toISOString()), 'Jan 5 09:07');
  assert.equal(formatCheckpointDateTime(new Date(2026, 0, 5).toISOString()), 'Jan 5');
});
