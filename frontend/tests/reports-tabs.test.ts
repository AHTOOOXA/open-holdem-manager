import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classAt, moveFocus, posOfClass, rectClasses, toggleClass, unionClasses } from '../src/lib/reports/range-grid.ts';
import { formatSpotValue, spotTone } from '../src/lib/reports/format.ts';
import { RANGE_LEVEL_ALPHA, rangeLevelShade } from '../src/lib/chart-theme.ts';

test('classAt: pairs on the diagonal, suited upper-right, offsuit lower-left', () => {
  assert.equal(classAt(0, 0), 'AA');
  assert.equal(classAt(12, 12), '22');
  assert.equal(classAt(0, 1), 'AKs');
  assert.equal(classAt(1, 0), 'AKo');
  assert.equal(classAt(5, 6), '98s');
  assert.equal(classAt(6, 5), '98o');
});

test('posOfClass inverts classAt for all 169 classes', () => {
  const seen = new Set<string>();
  for (let r = 0; r < 13; r++)
    for (let c = 0; c < 13; c++) {
      const cls = classAt(r, c);
      seen.add(cls);
      assert.deepEqual(posOfClass(cls), { row: r, col: c });
    }
  assert.equal(seen.size, 169);
  assert.equal(posOfClass('XX'), null);
  assert.equal(posOfClass('AK'), null);
});

test('rectClasses: any corner order, row-major', () => {
  assert.deepEqual(rectClasses({ row: 0, col: 0 }, { row: 1, col: 1 }), ['AA', 'AKs', 'AKo', 'KK']);
  assert.deepEqual(rectClasses({ row: 1, col: 1 }, { row: 0, col: 0 }), ['AA', 'AKs', 'AKo', 'KK']);
  assert.deepEqual(rectClasses({ row: 2, col: 2 }, { row: 2, col: 2 }), ['QQ']);
  assert.equal(rectClasses({ row: 0, col: 0 }, { row: 12, col: 12 }).length, 169);
});

test('toggleClass / unionClasses keep grid order', () => {
  assert.deepEqual(toggleClass(['AA'], 'KK'), ['AA', 'KK']);
  assert.deepEqual(toggleClass(['KK'], 'AA'), ['AA', 'KK']);
  assert.deepEqual(toggleClass(['AA', 'KK'], 'AA'), ['KK']);
  assert.deepEqual(unionClasses(['KK', 'AA'], ['AA', 'AKs']), ['AA', 'AKs', 'KK']);
});

test('moveFocus clamps at the grid edges', () => {
  assert.deepEqual(moveFocus({ row: 0, col: 0 }, 'ArrowUp'), { row: 0, col: 0 });
  assert.deepEqual(moveFocus({ row: 0, col: 0 }, 'ArrowRight'), { row: 0, col: 1 });
  assert.deepEqual(moveFocus({ row: 12, col: 12 }, 'ArrowDown'), { row: 12, col: 12 });
  assert.deepEqual(moveFocus({ row: 3, col: 3 }, 'a'), { row: 3, col: 3 });
});

test('rangeLevelShade maps levels 0-3 to 0/18/36/60 percent of primary', () => {
  assert.deepEqual([...RANGE_LEVEL_ALPHA], [0, 18, 36, 60]);
  assert.equal(rangeLevelShade(0), 'color-mix(in oklch, var(--primary) 0%, transparent)');
  assert.equal(rangeLevelShade(2), 'color-mix(in oklch, var(--primary) 36%, transparent)');
  assert.equal(rangeLevelShade(3), 'color-mix(in oklch, var(--primary) 60%, transparent)');
  assert.equal(rangeLevelShade(9), rangeLevelShade(3));
  assert.equal(rangeLevelShade(-1), rangeLevelShade(0));
});

test('formatSpotValue by ValueFormat', () => {
  assert.equal(formatSpotValue(null, 'pct'), '--');
  assert.equal(formatSpotValue(NaN, 'bb'), '--');
  assert.equal(formatSpotValue(23.4, 'pct', 100), '23');
  assert.equal(formatSpotValue(23.4, 'pct', 0), '--');
  assert.equal(formatSpotValue(1250, 'count'), '1.2k');
  assert.equal(formatSpotValue(999, 'count'), '999');
  assert.equal(formatSpotValue(-3.5, 'money'), '-$3.50');
  assert.equal(formatSpotValue(12.34, 'bb'), '12.3');
  assert.equal(formatSpotValue(0.456, 'bbh'), '0.46');
  assert.equal(formatSpotValue(2, 'ratio'), '2.00');
});

test('spotTone only for winnings', () => {
  assert.equal(spotTone(5, true, 'money'), 'pos');
  assert.equal(spotTone(-5, true, 'bb100'), 'neg');
  assert.equal(spotTone(0, true, 'money'), 'zero');
  assert.equal(spotTone(5, false, 'money'), null);
  assert.equal(spotTone(null, true, 'money'), null);
});
