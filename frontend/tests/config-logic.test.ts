import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  diffMembers, filterAliases, newColorMarker, parseNumberField, parseRangePair, patchMarker, sortAliases, uniqueName, validName,
} from '../src/lib/config/logic.ts';

test('parseNumberField integer and decimal', () => {
  assert.deepEqual(parseNumberField('12', { min: 0, max: 100 }), { value: 12 });
  assert.ok('error' in parseNumberField('12.5', { min: 0, max: 100 }));
  assert.deepEqual(parseNumberField('12.5', { min: 0, max: 100, integer: false }), { value: 12.5 });
  assert.ok('error' in parseNumberField('101', { min: 0, max: 100 }));
  assert.ok('error' in parseNumberField('', { min: 0, max: 100 }));
});

test('parseRangePair', () => {
  assert.deepEqual(parseRangePair('0', '35', { min: 0, max: 100 }), { value: [0, 35] });
  assert.ok('error' in parseRangePair('40', '35', { min: 0, max: 100 }));
  assert.ok('error' in parseRangePair('a', '35', { min: 0, max: 100 }));
});

test('uniqueName', () => {
  assert.equal(uniqueName('New Workspace', ['Main']), 'New Workspace');
  assert.equal(uniqueName('New Workspace', ['New Workspace']), 'New Workspace (2)');
  assert.equal(uniqueName('New Workspace', ['new workspace', 'New Workspace (2)']), 'New Workspace (3)');
});

test('validName', () => {
  assert.equal(validName('  raise '), 'raise');
  assert.equal(validName('   '), null);
  assert.equal(validName('x'.repeat(61)), null);
});

test('colour markers', () => {
  const m = [{ id: 1, name: 'Fish', color: 'tag-3' as const, is_regular: false }, { id: 5, name: 'Reg', color: 'tag-7' as const, is_regular: true }];
  assert.deepEqual(newColorMarker(6), { id: 6, name: 'new marker', color: 'tag-3', is_regular: false });
  assert.equal(patchMarker(m, 5, { name: 'X' })[1].name, 'X');
  assert.equal(patchMarker(m, 5, { name: 'X' })[0].name, 'Fish');
});

test('aliases sort pinned first then A-Z, filter by member names', () => {
  const l = [
    { id: 1, display_name: 'zed', aliases: [{ username: 'abc' }] },
    { id: 2, display_name: 'Bob', aliases: [] },
    { id: 3, display_name: 'amy', pinned: true, aliases: [{ username: 'Foo' }] },
  ];
  assert.deepEqual(sortAliases(l).map((a) => a.id), [3, 2, 1]);
  assert.deepEqual(filterAliases(l, 'ABC').map((a) => a.id), [1]);
  assert.deepEqual(filterAliases(l, 'foo').map((a) => a.id), [3]);
  assert.equal(filterAliases(l, ' ').length, 3);
});

test('diffMembers', () => {
  const m = (p: number, aliasId?: number) => ({ playerId: p, workspaceId: 1, username: `p${p}`, aliasId });
  const d = diffMembers([m(1, 10), m(2, 11)], [m(2), m(3)]);
  assert.deepEqual(d.add.map((x) => x.playerId), [3]);
  assert.deepEqual(d.remove.map((x) => x.aliasId), [10]);
});
