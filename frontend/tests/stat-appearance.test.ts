import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { H2N_APPEARANCE_DEFAULTS, formatHands, formatPercent, setStatAppearance, shouldDim, shouldShowSample, resolveCellDisplay } from '../src/lib/format/h2n.ts';
import { bytes } from '../src/lib/format/number.ts';
import type { StatAppearance } from '../src/lib/config/types.ts';

const DEFAULT_CFG: StatAppearance = {
  one_decimal_below: 10,
  show_99_for_100: true,
  leading_zero: false,
  shorten_amounts: true,
  show_sample_below: 15,
  dim_below: 10,
  vs_user_substitute_above: 50,
};

afterEach(() => {
  setStatAppearance(DEFAULT_CFG);
});

test('defaults map to the built-in appearance', () => {
  assert.equal(setStatAppearance(DEFAULT_CFG), false);
  assert.equal(H2N_APPEARANCE_DEFAULTS.oneDecimalThreshold, 10);
});

test('one_decimal_below moves the decimal window', () => {
  assert.equal(formatPercent(7.46, 100), '7.5');
  setStatAppearance({ ...DEFAULT_CFG, one_decimal_below: 5 });
  assert.equal(formatPercent(7.46, 100), '7');
  assert.equal(formatPercent(4.46, 100), '4.5');
});

test('99 for 100 can be switched off', () => {
  assert.equal(formatPercent(100, 5), '99');
  setStatAppearance({ ...DEFAULT_CFG, show_99_for_100: false });
  assert.equal(formatPercent(100, 5), '100');
});

test('leading zero pads whole percents below 10', () => {
  setStatAppearance({ ...DEFAULT_CFG, leading_zero: true, one_decimal_below: 0 });
  assert.equal(formatPercent(5, 100), '05');
  assert.equal(formatPercent(0, 100), '00');
  assert.equal(formatPercent(12, 100), '12');
  assert.equal(formatPercent(-5, 100), '-5');
});

test('shorten_amounts off prints counts in full', () => {
  assert.equal(formatHands(12500), '12k');
  setStatAppearance({ ...DEFAULT_CFG, shorten_amounts: false });
  assert.equal(formatHands(12500), '12500');
  assert.equal(formatPercent(1250.7), '1250');
});

test('sample thresholds', () => {
  assert.equal(shouldShowSample(12), true);
  setStatAppearance({ ...DEFAULT_CFG, show_sample_below: 5, dim_below: 3 });
  assert.equal(shouldShowSample(12), false);
  assert.equal(shouldDim(4), false);
  assert.equal(shouldDim(2), true);
});

test('vs-user substitution threshold, 0 turns it off', () => {
  const cell = { cases: 1, opps: 10, vs_user: { cases: 5, opps: 60, sample: 60 } };
  assert.equal(resolveCellDisplay(cell).vsUser, true);
  setStatAppearance({ ...DEFAULT_CFG, vs_user_substitute_above: 0 });
  assert.equal(resolveCellDisplay(cell).vsUser, false);
  setStatAppearance({ ...DEFAULT_CFG, vs_user_substitute_above: 100 });
  assert.equal(resolveCellDisplay(cell).vsUser, false);
});

test('bytes', () => {
  assert.equal(bytes(512), '512 B');
  assert.equal(bytes(1536), '1.5 KB');
  assert.equal(bytes(5 * 1024 * 1024), '5.0 MB');
  assert.equal(bytes(-1), '--');
});
