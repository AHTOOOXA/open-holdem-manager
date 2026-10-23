/**
 * Tests for the route helpers: old URL redirects and the remembered start screen.
 * Run: cd frontend && npx tsx --test tests/routes.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_ROUTE,
  LEGACY_PATHS,
  RAIL_PATHS,
  legacyRedirect,
  railPathFor,
  resolveLastRoute,
} from '../src/lib/routes';

test('legacyRedirect: every old top-level URL maps to its new home', () => {
  const expected: Record<string, string> = {
    '/graph': '/reports?tab=graph',
    '/range': '/reports?tab=range',
    '/hands': '/reports?tab=hands',
    '/general': '/statistics',
    '/stats': '/extras/stats',
    '/cash-drop': '/extras/cash-drop',
    '/compare': '/extras/compare',
    '/population': '/extras/population',
    '/players': '/extras/players',
    '/settings': '/databases',
    '/settings/workspaces': '/databases',
  };
  for (const [from, to] of Object.entries(expected)) {
    assert.equal(legacyRedirect(from as (typeof LEGACY_PATHS)[number], {}), to, from);
  }
});

test('legacyRedirect: route params carry over', () => {
  assert.equal(legacyRedirect('/stats/:statKey', { statKey: 'vpip' }), '/extras/stats/vpip');
  assert.equal(legacyRedirect('/players/:playerId', { playerId: '42' }), '/extras/players/42');
  assert.equal(
    legacyRedirect('/players/identity/:identityId', { identityId: '7' }),
    '/extras/players/identity/7',
  );
});

test('legacyRedirect: params are re-encoded', () => {
  assert.equal(legacyRedirect('/stats/:statKey', { statKey: 'a b/c' }), '/extras/stats/a%20b%2Fc');
});

test('legacyRedirect: query string is preserved', () => {
  assert.equal(
    legacyRedirect('/stats/:statKey', { statKey: 'pfr' }, '?pos=BTN&stakes=0.25'),
    '/extras/stats/pfr?pos=BTN&stakes=0.25',
  );
  assert.equal(legacyRedirect('/general', {}, '?x=1'), '/statistics?x=1');
  assert.equal(legacyRedirect('/players', {}, ''), '/extras/players');
});

test('legacyRedirect: Reports tabs merge with the existing query, tab first', () => {
  assert.equal(
    legacyRedirect('/hands', {}, '?stat_flag=vpip&stat_flag=pfr'),
    '/reports?tab=hands&stat_flag=vpip&stat_flag=pfr',
  );
  assert.equal(legacyRedirect('/graph', {}, 'stakes=0.5'), '/reports?tab=graph&stakes=0.5');
  // An incoming tab is replaced, not duplicated
  assert.equal(legacyRedirect('/range', {}, '?tab=old&pos=CO'), '/reports?tab=range&pos=CO');
});

test('legacyRedirect: hash is kept', () => {
  assert.equal(legacyRedirect('/compare', {}, '?a=1', '#top'), '/extras/compare?a=1#top');
});

test('legacyRedirect: every legacy path has a target inside the rail', () => {
  for (const from of LEGACY_PATHS) {
    const to = legacyRedirect(from, { statKey: 'k', playerId: '1', identityId: '2' });
    assert.ok(railPathFor(to.split('?')[0]), `${from} -> ${to}`);
  }
});

test('resolveLastRoute: known destinations are kept', () => {
  for (const p of RAIL_PATHS) assert.equal(resolveLastRoute(p), p);
});

test('resolveLastRoute: anything else falls back to Reports', () => {
  assert.equal(DEFAULT_ROUTE, '/reports');
  for (const bad of [null, undefined, '', '/', '/graph', '/design', '/extras', '/reports/x', 'reports', '//evil.example', 'javascript:alert(1)']) {
    assert.equal(resolveLastRoute(bad), '/reports', String(bad));
  }
});

test('railPathFor: sub-pages belong to their rail destination', () => {
  assert.equal(railPathFor('/reports'), '/reports');
  assert.equal(railPathFor('/sessions/3'), '/sessions');
  assert.equal(railPathFor('/extras/stats/vpip'), '/extras/stats');
  assert.equal(railPathFor('/extras/players/identity/2'), '/extras/players');
  assert.equal(railPathFor('/configuration/updates'), '/configuration');
  assert.equal(railPathFor('/statistics/'), '/statistics');
});

test('railPathFor: non-rail paths and look-alikes are not matched', () => {
  assert.equal(railPathFor('/'), null);
  assert.equal(railPathFor('/design'), null);
  assert.equal(railPathFor('/reportsx'), null);
  assert.equal(railPathFor('/extras'), null);
  assert.equal(railPathFor('/stats'), null);
});
