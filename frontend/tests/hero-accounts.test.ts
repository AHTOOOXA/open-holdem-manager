/**
 * Unit tests for src/lib/hero-accounts.ts.
 * Run: cd frontend && npx tsx --test tests/hero-accounts.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeNicknames, firstSiteWithoutManual, groupBySite, heroLabel, heroSummary } from '../src/lib/hero-accounts.ts';
import type { HeroAccount } from '../src/lib/api.ts';

const sites = [
  { code: 'GG', name: 'GGPoker' },
  { code: 'PS', name: 'PokerStars' },
  { code: '888', name: '888poker' },
];
const acc = (site: string, username: string, source: 'manual' | 'auto'): HeroAccount => ({
  site, site_name: site, username, source, hand_count: 5,
});

test('normalizeNicknames trims, drops blanks, dedupes', () => {
  assert.deepEqual(normalizeNicknames([' a ', '', '   ', 'a', 'b', 'A']), ['a', 'b', 'A']);
});

test('firstSiteWithoutManual skips sites with manual nicknames only', () => {
  assert.equal(firstSiteWithoutManual(sites, []), 'GG');
  assert.equal(firstSiteWithoutManual(sites, [acc('GG', 'x', 'manual')]), 'PS');
  assert.equal(firstSiteWithoutManual(sites, [acc('GG', 'x', 'auto')]), 'GG');
  assert.equal(firstSiteWithoutManual(sites, sites.map((s) => acc(s.code, 'x', 'manual'))), 'GG');
  assert.equal(firstSiteWithoutManual([], []), '');
});

test('groupBySite filters by source and groups', () => {
  const g = groupBySite([acc('GG', 'a', 'manual'), acc('PS', 'b', 'auto'), acc('GG', 'c', 'manual')], 'manual');
  assert.equal(g.length, 1);
  assert.deepEqual(g[0].accounts.map((a) => a.username), ['a', 'c']);
});

test('heroLabel and heroSummary handle null', () => {
  assert.equal(heroLabel(null), 'No hero yet');
  assert.equal(heroLabel({ username: 'u', site_name: 'GGPoker' }), 'u · GGPoker');
  assert.match(heroSummary(null), /^No hero yet/);
  assert.equal(
    heroSummary({ site: 'GG', site_name: 'GGPoker', username: 'u', hand_count: 1200 }),
    'Stats show u · GGPoker (1,200 hands), the account with the most hands.',
  );
});
