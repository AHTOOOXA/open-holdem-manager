import assert from 'node:assert/strict';
import { test } from 'node:test';
import { showsRebuildBanner } from '../src/lib/rebuild-banner.ts';

test('banner shows only on the four screens, only when required and idle', () => {
  for (const p of ['/reports', '/statistics', '/sessions/3', '/configuration/game-types']) assert.equal(showsRebuildBanner(p, true, false), true, p);
  for (const p of ['/databases', '/marked', '/extras/stats', '/reportsx']) assert.equal(showsRebuildBanner(p, true, false), false, p);
  assert.equal(showsRebuildBanner('/reports', false, false), false);
  assert.equal(showsRebuildBanner('/reports', true, true), false);
});
