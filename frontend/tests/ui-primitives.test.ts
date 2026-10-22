/**
 * Tests for the pure helpers behind StatValue, Chip and Tabs overflow.
 * Run: cd frontend && npx tsx --test tests/ui-primitives.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statValueParts } from '../src/components/ui/stat-value';
import { computeVisibleTabs } from '../src/components/ui/tabs';
import { chipToneClasses, chipDotClasses } from '../src/components/ui/chip';

test('statValueParts: null and empty sample show a dimmed --', () => {
  assert.deepEqual(statValueParts(null, null), { text: '--', sampleText: null, dim: true });
  assert.deepEqual(statValueParts(undefined, 50), { text: '--', sampleText: null, dim: true });
  assert.deepEqual(statValueParts(30, 0), { text: '--', sampleText: null, dim: true });
});

test('statValueParts: plenty of data has no sample and no dim', () => {
  assert.deepEqual(statValueParts(23.4, 140), { text: '23', sampleText: null, dim: false });
  assert.deepEqual(statValueParts(23.4, null), { text: '23', sampleText: null, dim: false });
});

test('statValueParts: sample shown below 15, dim below 10', () => {
  assert.deepEqual(statValueParts(40, 12), { text: '40', sampleText: '12', dim: false });
  assert.deepEqual(statValueParts(40, 14), { text: '40', sampleText: '14', dim: false });
  assert.deepEqual(statValueParts(40, 15).sampleText, null);
  assert.deepEqual(statValueParts(40, 9), { text: '40', sampleText: '9', dim: true });
  assert.equal(statValueParts(40, 10).dim, false);
});

test('statValueParts: bb100 keeps sign and decimals', () => {
  assert.equal(statValueParts(-5.43, 500, 'bb100').text, '-5.4');
  assert.equal(statValueParts(12.6, 500, 'bb100').text, '13');
  assert.equal(statValueParts(0.456, 500, 'bb100').text, '0.46');
  assert.equal(statValueParts(null, 500, 'bb100').text, '--');
});

test('statValueParts: number format shortens counts', () => {
  assert.equal(statValueParts(1250, null, 'number').text, '1.2k');
});

test('computeVisibleTabs: everything fits', () => {
  assert.deepEqual(computeVisibleTabs([50, 50, 50], 150, 30, 0), { visible: [0, 1, 2], hidden: [] });
});

test('computeVisibleTabs: overflow reserves room for the more button', () => {
  // budget = 200 - 30 = 170 -> 3 tabs of 50
  assert.deepEqual(computeVisibleTabs([50, 50, 50, 50, 50], 200, 30, 0), {
    visible: [0, 1, 2],
    hidden: [3, 4],
  });
});

test('computeVisibleTabs: hidden active tab is swapped in for the last visible', () => {
  assert.deepEqual(computeVisibleTabs([50, 50, 50, 50, 50], 200, 30, 4), {
    visible: [0, 1, 4],
    hidden: [2, 3],
  });
});

test('computeVisibleTabs: wide active tab evicts as many as needed', () => {
  assert.deepEqual(computeVisibleTabs([50, 50, 50, 120], 200, 30, 3), {
    visible: [0, 3],
    hidden: [1, 2],
  });
});

test('computeVisibleTabs: zero width keeps only the active tab', () => {
  assert.deepEqual(computeVisibleTabs([50, 50, 50], 0, 30, 1), { visible: [1], hidden: [0, 2] });
  assert.deepEqual(computeVisibleTabs([50, 50], 0, 30, -1), { visible: [], hidden: [0, 1] });
  assert.deepEqual(computeVisibleTabs([], 0, 30, -1), { visible: [], hidden: [] });
});

test('chip tone maps: every tone has surface and dot classes', () => {
  const tones = Object.keys(chipToneClasses);
  assert.equal(tones.length, 13);
  assert.deepEqual(tones, Object.keys(chipDotClasses));
  assert.match(chipToneClasses.accent, /bg-primary\/15/);
  assert.match(chipToneClasses.tag7, /bg-tag-7\/20/);
  assert.equal(chipDotClasses.tag3, 'bg-tag-3');
});
