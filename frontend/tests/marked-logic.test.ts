import test from 'node:test';
import assert from 'node:assert/strict';
import {
  clearPageTagFilters,
  countLabel,
  getPageTagFilter,
  gridColumnCount,
  isMarkedFilterActive,
  markMenuState,
  markedListParams,
  parseTagParam,
  patchRow,
  pruneTagIds,
  setPageTagFilter,
  tagRefsFor,
  toggleId,
} from '../src/lib/marked/logic.ts';
import { mockHandListResponse, mockTagDefs } from '../landing/mock/hands-data.ts';

test('grid columns: ten per column', () => {
  assert.equal(gridColumnCount(0), 1);
  assert.equal(gridColumnCount(10), 1);
  assert.equal(gridColumnCount(11), 2);
  assert.equal(gridColumnCount(25), 3);
});

test('filter params: tags imply marked and win over the mode', () => {
  assert.deepEqual(markedListParams({ mode: '', tagIds: [] }), {});
  assert.deepEqual(markedListParams({ mode: 'marked', tagIds: [] }), { marked: true });
  assert.deepEqual(markedListParams({ mode: 'unmarked', tagIds: [] }), { marked: false });
  assert.deepEqual(markedListParams({ mode: 'unmarked', tagIds: [2, 3] }), { tag_ids: [2, 3] });
  assert.equal(isMarkedFilterActive({ mode: '', tagIds: [] }), false);
  assert.equal(isMarkedFilterActive({ mode: '', tagIds: [1] }), true);
});

test('toggleId, parseTagParam, pruneTagIds', () => {
  assert.deepEqual(toggleId([1], 2, true), [1, 2]);
  assert.deepEqual(toggleId([1, 2], 2, true), [1, 2]);
  assert.deepEqual(toggleId([1, 2], 1, false), [2]);
  assert.deepEqual(parseTagParam('3'), [3]);
  assert.deepEqual(parseTagParam('3,x,-1,3,4'), [3, 4]);
  assert.deepEqual(parseTagParam(null), []);
  assert.deepEqual(pruneTagIds([1, 9], mockTagDefs), [1]);
});

test('tagRefsFor keeps catalogue order; menu state', () => {
  assert.deepEqual(tagRefsFor([3, 1], mockTagDefs).map((t) => t.id), [1, 3]);
  assert.deepEqual(markMenuState(false, 2), { mark: true, markWithTags: true, unmark: false });
  assert.deepEqual(markMenuState(true, 0), { mark: false, markWithTags: false, unmark: true });
});

test('patchRow updates only the matching row', () => {
  const rows = [{ id: 'a', marked: false, tags: [] }, { id: 'b', marked: false, tags: [] }];
  const out = patchRow(rows, { hand_id: 'b', marked: true, tags: [{ id: 1, name: 'x', color: 'tag-1' }] });
  assert.equal(out[0], rows[0]);
  assert.equal(out[1].marked, true);
  assert.equal(out[1].tags.length, 1);
});

test('page filter memory is per workspace', () => {
  clearPageTagFilters();
  setPageTagFilter(1, [4]);
  assert.deepEqual(getPageTagFilter(1), [4]);
  assert.deepEqual(getPageTagFilter(2), []);
  assert.equal(countLabel(1, 'hand'), '1 hand');
  assert.equal(countLabel(1200, 'hand'), '1,200 hands');
});

test('landing mock rows carry the contract shape', () => {
  const ids = new Set(mockTagDefs.map((d) => d.id));
  for (const h of mockHandListResponse.hands) {
    assert.equal(typeof h.marked, 'boolean');
    assert.ok(Array.isArray(h.tags));
    if (h.tags.length > 0) assert.equal(h.marked, true);
    for (const t of h.tags) assert.ok(ids.has(t.id));
  }
});
