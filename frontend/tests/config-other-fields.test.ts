/** Run: cd frontend && npx tsx --test tests/config-other-fields.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DAY_START_RANGE, MAX_BREAK_RANGE, parseIntField } from '../src/components/configuration/other-fields.ts';

test('max break: 1-240 whole minutes', () => {
  assert.deepEqual(parseIntField('10', MAX_BREAK_RANGE), { value: 10 });
  assert.deepEqual(parseIntField(' 240 ', MAX_BREAK_RANGE), { value: 240 });
  for (const bad of ['0', '241', '', '1.5', '-3', 'ten']) assert.ok('error' in parseIntField(bad, MAX_BREAK_RANGE), bad);
});

test('day start: 0-23', () => {
  assert.deepEqual(parseIntField('0', DAY_START_RANGE), { value: 0 });
  assert.deepEqual(parseIntField('23', DAY_START_RANGE), { value: 23 });
  assert.ok('error' in parseIntField('24', DAY_START_RANGE));
});
