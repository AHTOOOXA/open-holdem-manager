/**
 * Unit tests for the Configuration section registry helpers.
 * Run: cd frontend && npx tsx --test tests/config-sections.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { findSection, groupSections } from '../src/components/configuration/section-registry.ts';

const sections = [
  { id: 'hero', title: 'Hero Nicknames', group: 'Players' },
  { id: 'updates', title: 'Updates', group: 'Application' },
  { id: 'extra', title: 'Extra', group: 'Players' },
  { id: 'about', title: 'About', group: 'Application' },
];

test('findSection returns the matching section', () => {
  assert.equal(findSection(sections, 'about').id, 'about');
});

test('unknown or missing id falls back to the first section', () => {
  assert.equal(findSection(sections, 'nope').id, 'hero');
  assert.equal(findSection(sections, undefined).id, 'hero');
});

test('groupSections keeps first-appearance group order and array order inside groups', () => {
  const g = groupSections(sections);
  assert.deepEqual(g.map((x) => x.group), ['Players', 'Application']);
  assert.deepEqual(g[0].sections.map((s) => s.id), ['hero', 'extra']);
  assert.deepEqual(g[1].sections.map((s) => s.id), ['updates', 'about']);
});
