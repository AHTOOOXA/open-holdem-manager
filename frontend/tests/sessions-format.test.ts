/** Run: cd frontend && npx tsx --test tests/sessions-format.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clockHHMM, liveCaption, liveClock, sessionCaption } from '../src/lib/sessions/format.ts';

test('caption: month, day, weekday and 24h clock', () => {
  assert.equal(sessionCaption('2026-10-17T20:10:05', { numeric: false, currentYear: 2026 }), 'October 17, Saturday 20:10');
  assert.equal(sessionCaption('2026-10-16T09:05:00', { numeric: false, currentYear: 2026 }), 'October 16, Friday 09:05');
});

test('caption: year prefix only when not the current year', () => {
  assert.equal(sessionCaption('2025-10-17T20:10:05', { numeric: false, currentYear: 2026 }), '2025 October 17, Friday 20:10');
});

test('caption: numeric format', () => {
  assert.equal(sessionCaption('2026-10-17T20:10:05', { numeric: true, currentYear: 2026 }), '17-10-2026, 20:10');
  assert.equal(sessionCaption('2025-01-05T00:00:00', { numeric: true, currentYear: 2026 }), '05-01-2025, 00:00');
});

test('caption: unparseable input is empty', () => {
  assert.equal(sessionCaption('', { numeric: false, currentYear: 2026 }), '');
  assert.equal(clockHHMM('nope'), '');
});

test('live texts', () => {
  assert.equal(liveCaption('2026-10-24T14:05:09'), 'Live 14:05 - ...');
  assert.equal(liveClock('2026-10-24T14:05:09'), '14:05 - ...');
});
