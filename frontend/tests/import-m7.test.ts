import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  IMPORT_FILTER_KEY, filterMode, importPresets, isAllTime, isValidFilter, loadFilter, resolveFilter, sanitizeFilter, saveFilter,
} from '../src/lib/import/date-filter';
import {
  activeConnection, databaseOptionLabel, loadConnection, parsePort, saveConnection, searchMessage, trackerBody,
} from '../src/lib/import/tracker';
import { addFolder, isAbsolutePath, refreshDelay, removeFolder, replaceFolder, statusText } from '../src/lib/import/auto-import';
import { importCompletedMessage, progressLine, progressParts } from '../src/lib/import-ui';

const NOW = new Date(2026, 9, 24, 15, 0, 0); // Saturday 24 Oct 2026
const mem = () => {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k), m };
};

test('import presets: no All Time, no Last Session', () => {
  const ids = importPresets(NOW, 0).map((p) => p.id);
  assert.ok(ids.includes('today') && ids.includes('lastmonth'));
  assert.ok(!ids.includes('all'));
  assert.ok(!ids.some((i) => i.includes('session')));
});

test('relative presets are re-derived at Apply', () => {
  assert.deepEqual(resolveFilter({ preset: 'today' }, NOW, 0), { date_from: '2026-10-24', date_to: '2026-10-24' });
  const tomorrow = new Date(2026, 9, 25, 15, 0, 0);
  assert.deepEqual(resolveFilter({ preset: 'today' }, tomorrow, 0), { date_from: '2026-10-25', date_to: '2026-10-25' });
  // before the day start hour it is still yesterday
  assert.deepEqual(resolveFilter({ preset: 'today' }, new Date(2026, 9, 25, 2, 0, 0), 5), { date_from: '2026-10-24', date_to: '2026-10-24' });
});

test('custom range and all time', () => {
  assert.deepEqual(resolveFilter({ from: '2026-01-01', to: '2026-02-01' }, NOW, 0), { date_from: '2026-01-01', date_to: '2026-02-01' });
  assert.deepEqual(resolveFilter({ from: '2026-01-01' }, NOW, 0), { date_from: '2026-01-01' });
  assert.deepEqual(resolveFilter({}, NOW, 0), {});
  assert.ok(isAllTime({}));
  assert.equal(filterMode({}), 'all');
  assert.equal(filterMode({ from: '2026-01-01' }), 'custom');
  assert.equal(filterMode({ preset: 'week' }), 'week');
  assert.ok(!isValidFilter({ from: '2026-03-01', to: '2026-02-01' }));
  assert.ok(isValidFilter({ from: '2026-02-01', to: '2026-02-01' }));
});

test('filter storage: presets by id, junk ignored', () => {
  const s = mem();
  saveFilter(s, { preset: 'week' });
  assert.equal(s.m.get(IMPORT_FILTER_KEY), '{"preset":"week"}');
  assert.deepEqual(loadFilter(s, NOW, 0), { preset: 'week' });
  saveFilter(s, { from: '2026-01-01', to: '2026-01-31' });
  assert.deepEqual(loadFilter(s, NOW, 0), { from: '2026-01-01', to: '2026-01-31' });
  saveFilter(s, {});
  assert.equal(s.m.has(IMPORT_FILTER_KEY), false);
  s.setItem(IMPORT_FILTER_KEY, '{nope');
  assert.deepEqual(loadFilter(s, NOW, 0), {});
  assert.deepEqual(sanitizeFilter({ preset: 'lastsession' }, NOW, 0), {});
  assert.deepEqual(sanitizeFilter({ from: 'x', to: '2026-01-01' }, NOW, 0), { to: '2026-01-01' });
  assert.deepEqual(loadFilter(null), {});
});

test('tracker request body leaves blanks (an empty password too) to backend defaults', () => {
  assert.deepEqual(trackerBody('pt4', null), { software: 'pt4' });
  assert.deepEqual(
    trackerBody('hm3', { host: ' db ', port: 5433, user: '', password: 'p w' }),
    { software: 'hm3', host: 'db', port: 5433, password: 'p w' },
  );
  assert.deepEqual(trackerBody('pt4', { host: '', user: ' ', password: '' }), { software: 'pt4' });
});

test('tracker connection persistence never stores the password', () => {
  const s = mem();
  saveConnection(s, 'pt4', { custom: true, host: 'h', port: '5432', user: 'u' });
  assert.ok(!JSON.stringify([...s.m.values()]).includes('password'));
  assert.deepEqual(loadConnection(s, 'pt4'), { custom: true, host: 'h', port: '5432', user: 'u' });
  assert.deepEqual(loadConnection(s, 'hm3'), { custom: false, host: '', port: '', user: '' });
  assert.equal(activeConnection({ custom: false, host: 'h', port: '1', user: 'u' }, 'x'), null);
  assert.deepEqual(activeConnection({ custom: true, host: 'h', port: '1', user: 'u' }, 'x'), { host: 'h', port: 1, user: 'u', password: 'x' });
  assert.equal(parsePort('70000'), undefined);
  assert.equal(parsePort(' 5432 '), 5432);
  assert.equal(parsePort('abc'), undefined);
});

test('tracker search messages and labels', () => {
  assert.equal(searchMessage(null), null);
  assert.equal(searchMessage({ software: 'pt4', databases: [], error: null }), 'Databases not found');
  assert.equal(searchMessage({ software: 'pt4', databases: [], error: 'Could not connect to localhost:5432' }), 'Could not connect to localhost:5432');
  assert.equal(searchMessage({ software: 'pt4', databases: [{ name: 'a', hands: 1 }], error: null }), null);
  assert.equal(databaseOptionLabel({ name: 'main', hands: 12345 }, (n) => n.toLocaleString('en-US')), 'main (12,345 hands)');
});

test('auto-import folder list', () => {
  assert.deepEqual(addFolder(['/a/b'], '/A/B/ ').added, false);
  assert.deepEqual(addFolder(['/a/b'], ' /c/d/ '), { folders: ['/a/b', '/c/d'], added: true });
  assert.deepEqual(addFolder([], '/'), { folders: ['/'], added: true });
  assert.deepEqual(addFolder([], 'C:\\'), { folders: ['C:\\'], added: true });
  assert.deepEqual(replaceFolder(['/a', '/b'], 0, '/c'), ['/c', '/b']);
  assert.deepEqual(replaceFolder(['/a', '/b'], 0, '/B'), ['/a', '/b']);
  assert.deepEqual(removeFolder(['/a', '/b'], 0), ['/b']);
  assert.ok(isAbsolutePath('/x') && isAbsolutePath('C:\\x') && isAbsolutePath('\\\\srv\\x'));
  assert.ok(!isAbsolutePath('x/y') && !isAbsolutePath('~/x'));
});

test('auto-import refresh throttle and status text', () => {
  assert.equal(refreshDelay(null, 5, 0, 10_000), null);
  assert.equal(refreshDelay(5, 5, 0, 10_000), null);
  assert.equal(refreshDelay(5, 9, 0, 10_000), 0);
  assert.equal(refreshDelay(5, 9, 8_000, 10_000), 3_000);
  assert.equal(statusText({ session_hands: 1234, hands_per_hour: 56.4 }, (n) => n.toLocaleString('en-US')), 'Auto import: 1,234 hands, 56/h');
  assert.equal(statusText({ session_hands: 1, hands_per_hour: 0 }, String), 'Auto import: 1 hand, 0/h');
});

test('import summary: cancelled and out of range', () => {
  const m = importCompletedMessage({ imported: 10, duplicates: 2, errors: 0, out_of_range: 1500, cancelled: true });
  assert.equal(m.title, 'Import cancelled');
  assert.equal(m.description, '10 hands imported · 2 duplicates · 0 errors · 1,500 outside the date range');
  assert.equal(importCompletedMessage({ imported: 0, duplicates: 0, errors: 0, cancelled: true }).title, 'Import cancelled');
  assert.equal(importCompletedMessage({ imported: 5, duplicates: 0, errors: 0, out_of_range: 0 }).description, '5 hands imported · 0 duplicates · 0 errors');
  assert.deepEqual(progressParts({ type: 'progress', processed: 1, total: 2, out_of_range: 3 }), ['1 / 2 hands', '3 outside the date range']);
  assert.equal(progressLine(null), '');
});
