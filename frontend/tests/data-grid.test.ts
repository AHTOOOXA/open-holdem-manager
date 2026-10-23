/**
 * Tests for the pure helpers behind DataGrid.
 * Run: cd frontend && npx tsx --test tests/data-grid.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  ariaSortValue,
  clampWidth,
  computeSelection,
  endReachedIndex,
  hiddenFromVisibility,
  nextRowIndex,
  nextSorting,
  parseGridPrefs,
  pinSummaryLast,
  resizeByKey,
  revealScrollTop,
  rowsPerPage,
  selectAllState,
  serializeGridPrefs,
  shouldFireEndReached,
  shouldVirtualize,
  sortDirection,
  splitSummary,
  visibilityFromHidden,
  type ColumnPrefSpec,
} from '../src/components/ui/data-grid/logic.ts';

test('nextSorting: a new column starts desc when descFirst, asc otherwise', () => {
  assert.deepEqual(nextSorting([], 'won', true), [{ id: 'won', desc: true }]);
  assert.deepEqual(nextSorting([], 'name', false), [{ id: 'name', desc: false }]);
  assert.deepEqual(nextSorting([{ id: 'name', desc: false }], 'won', true), [{ id: 'won', desc: true }]);
});

test('nextSorting: same column toggles and never clears', () => {
  assert.deepEqual(nextSorting([{ id: 'won', desc: true }], 'won', true), [{ id: 'won', desc: false }]);
  assert.deepEqual(nextSorting([{ id: 'won', desc: false }], 'won', true), [{ id: 'won', desc: true }]);
  // descFirst only matters for the first click
  assert.deepEqual(nextSorting([{ id: 'name', desc: false }], 'name', false), [{ id: 'name', desc: true }]);
});

test('sortDirection / ariaSortValue', () => {
  assert.equal(sortDirection([{ id: 'a', desc: true }], 'a'), 'desc');
  assert.equal(sortDirection([{ id: 'a', desc: false }], 'a'), 'asc');
  assert.equal(sortDirection([{ id: 'a', desc: false }], 'b'), false);
  assert.equal(ariaSortValue('desc'), 'descending');
  assert.equal(ariaSortValue('asc'), 'ascending');
  assert.equal(ariaSortValue(false), 'none');
});

test('nextRowIndex: arrows clamp at the ends', () => {
  assert.equal(nextRowIndex('ArrowDown', 0, 5, 10), 1);
  assert.equal(nextRowIndex('ArrowDown', 4, 5, 10), 4);
  assert.equal(nextRowIndex('ArrowUp', 0, 5, 10), 0);
  assert.equal(nextRowIndex('ArrowUp', 3, 5, 10), 2);
});

test('nextRowIndex: Home/End and pages', () => {
  assert.equal(nextRowIndex('Home', 3, 50, 10), 0);
  assert.equal(nextRowIndex('End', 3, 50, 10), 49);
  assert.equal(nextRowIndex('PageDown', 3, 50, 10), 13);
  assert.equal(nextRowIndex('PageDown', 45, 50, 10), 49);
  assert.equal(nextRowIndex('PageUp', 13, 50, 10), 3);
  assert.equal(nextRowIndex('PageUp', 5, 50, 10), 0);
  assert.equal(nextRowIndex('PageDown', 0, 50, 0), 1, 'page size is at least 1');
});

test('nextRowIndex: no active row lands on a row; other keys and empty grids return null', () => {
  assert.equal(nextRowIndex('ArrowDown', -1, 5, 10), 0);
  assert.equal(nextRowIndex('ArrowUp', -1, 5, 10), 0);
  assert.equal(nextRowIndex('End', -1, 5, 10), 4);
  assert.equal(nextRowIndex('ArrowDown', 99, 5, 10), 0, 'stale index restarts');
  assert.equal(nextRowIndex('Enter', 1, 5, 10), null);
  assert.equal(nextRowIndex('a', 1, 5, 10), null);
  assert.equal(nextRowIndex('ArrowDown', 0, 0, 10), null);
});

test('rowsPerPage keeps one row of overlap and is at least 1', () => {
  assert.equal(rowsPerPage(28 + 340, 28, 34), 9);
  assert.equal(rowsPerPage(40, 28, 34), 1);
  assert.equal(rowsPerPage(400, 28, 0), 1);
});

test('pinSummaryLast: the summary leaves the body wherever sorting put it', () => {
  const rows = [{ id: 'b' }, { id: '__s' }, { id: 'a' }];
  const r = pinSummaryLast(rows, '__s');
  assert.deepEqual(r.body.map((x) => x.id), ['b', 'a']);
  assert.equal(r.summary?.id, '__s');
  const none = pinSummaryLast(rows, null);
  assert.equal(none.body.length, 3);
  assert.equal(none.summary, null);
  assert.notEqual(none.body, rows, 'returns a copy');
  assert.equal(pinSummaryLast([{ id: 'x' }], '__s').summary, null);
});

test('splitSummary: flagged row in data or explicit summary', () => {
  type R = { id: string; total?: boolean };
  const data: R[] = [{ id: 'a' }, { id: 't', total: true }, { id: 'b' }];
  const flagged = splitSummary(data, undefined, (r) => !!r.total);
  assert.deepEqual(flagged.rows.map((r) => r.id), ['a', 'b']);
  assert.equal(flagged.summary?.id, 't');
  const explicit = splitSummary(data, { id: 'x' }, (r) => !!r.total);
  assert.equal(explicit.summary?.id, 'x', 'explicit summary wins');
  assert.equal(explicit.rows.length, 2);
  const plain = splitSummary(data, null);
  assert.equal(plain.rows.length, 3);
  assert.equal(plain.summary, null);
});

const ORDER = ['a', 'b', 'c', 'd', 'e'];

test('computeSelection: single replaces, none clears', () => {
  assert.deepEqual(computeSelection({ mode: 'single', current: ['a'], anchor: 'a', target: 'c', order: ORDER, toggle: true }), {
    ids: ['c'],
    anchor: 'c',
  });
  assert.deepEqual(computeSelection({ mode: 'none', current: ['a'], anchor: null, target: 'c', order: ORDER }), {
    ids: [],
    anchor: null,
  });
});

test('computeSelection: multi click, toggle and ranges', () => {
  const click = computeSelection({ mode: 'multi', current: ['a', 'b'], anchor: 'a', target: 'd', order: ORDER });
  assert.deepEqual(click, { ids: ['d'], anchor: 'd' });
  const add = computeSelection({ mode: 'multi', current: ['a'], anchor: 'a', target: 'c', order: ORDER, toggle: true });
  assert.deepEqual(add, { ids: ['a', 'c'], anchor: 'c' });
  const remove = computeSelection({ mode: 'multi', current: ['a', 'c'], anchor: 'a', target: 'a', order: ORDER, toggle: true });
  assert.deepEqual(remove, { ids: ['c'], anchor: 'a' });
  const range = computeSelection({ mode: 'multi', current: ['b'], anchor: 'b', target: 'd', order: ORDER, range: true });
  assert.deepEqual(range, { ids: ['b', 'c', 'd'], anchor: 'b' });
  const back = computeSelection({ mode: 'multi', current: [], anchor: 'd', target: 'b', order: ORDER, range: true });
  assert.deepEqual(back.ids, ['b', 'c', 'd']);
  const addRange = computeSelection({
    mode: 'multi', current: ['a', 'c'], anchor: 'c', target: 'e', order: ORDER, range: true, toggle: true,
  });
  assert.deepEqual(addRange.ids, ['a', 'c', 'd', 'e']);
  const noAnchor = computeSelection({ mode: 'multi', current: [], anchor: null, target: 'c', order: ORDER, range: true });
  assert.deepEqual(noAnchor, { ids: ['c'], anchor: 'c' });
});

test('selectAllState', () => {
  assert.equal(selectAllState([], ORDER), false);
  assert.equal(selectAllState(['a'], ORDER), 'indeterminate');
  assert.equal(selectAllState(ORDER, ORDER), true);
  assert.equal(selectAllState(['zz'], ORDER), false);
  assert.equal(selectAllState([], []), false);
});

const SPEC: ColumnPrefSpec[] = [
  { id: 'cards', hideable: false, minSize: 60, maxSize: 200 },
  { id: 'won', hideable: true, minSize: 40, maxSize: 300 },
  { id: 'date', hideable: true, minSize: 40, maxSize: 300 },
];

test('parseGridPrefs: round trip', () => {
  const raw = serializeGridPrefs({ hidden: ['date'], widths: { won: 90 } });
  assert.deepEqual(parseGridPrefs(raw, SPEC), { hidden: ['date'], widths: { won: 90 } });
});

test('parseGridPrefs: validates and drops what no longer applies', () => {
  const raw = JSON.stringify({
    v: 1,
    hidden: ['cards', 'gone', 'won', 'won', 7],
    widths: { won: 5000, date: 'wide', cards: 10, gone: 100, x: NaN },
  });
  assert.deepEqual(parseGridPrefs(raw, SPEC), { hidden: ['won'], widths: { won: 300, cards: 60 } });
});

test('parseGridPrefs: malformed input yields empty prefs', () => {
  const empty = { hidden: [], widths: {} };
  assert.deepEqual(parseGridPrefs(null, SPEC), empty);
  assert.deepEqual(parseGridPrefs('', SPEC), empty);
  assert.deepEqual(parseGridPrefs('{not json', SPEC), empty);
  assert.deepEqual(parseGridPrefs('[1,2]', SPEC), empty);
  assert.deepEqual(parseGridPrefs('"str"', SPEC), empty);
  assert.deepEqual(parseGridPrefs(JSON.stringify({ v: 99, hidden: ['won'] }), SPEC), empty, 'unknown version');
  assert.deepEqual(parseGridPrefs(JSON.stringify({ v: 1, hidden: 'won', widths: [1] }), SPEC), empty);
});

test('parseGridPrefs: never hides every column', () => {
  const spec: ColumnPrefSpec[] = [{ id: 'a', hideable: true, minSize: 10, maxSize: 100 }];
  assert.deepEqual(parseGridPrefs(JSON.stringify({ v: 1, hidden: ['a'], widths: {} }), spec).hidden, []);
});

test('visibility <-> hidden ids', () => {
  assert.deepEqual(visibilityFromHidden(['a', 'b']), { a: false, b: false });
  assert.deepEqual(hiddenFromVisibility({ a: false, b: true, c: false }), ['a', 'c']);
  assert.deepEqual(hiddenFromVisibility({}), []);
});

test('clampWidth / resizeByKey', () => {
  assert.equal(clampWidth(12.6, 10, 100), 13);
  assert.equal(clampWidth(5, 10, 100), 10);
  assert.equal(clampWidth(500, 10, 100), 100);
  const lim = { min: 40, max: 200 };
  assert.equal(resizeByKey('ArrowRight', 100, lim), 108);
  assert.equal(resizeByKey('ArrowLeft', 100, lim), 92);
  assert.equal(resizeByKey('ArrowRight', 100, lim, true), 132);
  assert.equal(resizeByKey('ArrowLeft', 50, lim, true), 40);
  assert.equal(resizeByKey('ArrowRight', 199, lim), 200);
  assert.equal(resizeByKey('Home', 150, lim), 40);
  assert.equal(resizeByKey('ArrowUp', 100, lim), null);
});

test('revealScrollTop: below the sticky header and above the sticky footer', () => {
  const base = { viewHeight: 300, itemHeight: 30, headerHeight: 28, footerHeight: 30 };
  assert.equal(revealScrollTop({ ...base, scrollTop: 0, itemTop: 100 }), null, 'already visible');
  assert.equal(revealScrollTop({ ...base, scrollTop: 100, itemTop: 110 }), 82, 'hidden under the header');
  assert.equal(revealScrollTop({ ...base, scrollTop: 0, itemTop: 260 }), 20, 'hidden under the footer');
  assert.equal(revealScrollTop({ ...base, scrollTop: 50, itemTop: 20 }), 0, 'never negative');
  assert.equal(revealScrollTop({ scrollTop: 0, viewHeight: 100, itemTop: 120, itemHeight: 20 }), 40);
});

test('endReached: once per row count, within the last rows, not while loading', () => {
  assert.equal(endReachedIndex(100), 90);
  assert.equal(endReachedIndex(5), 0);
  assert.equal(endReachedIndex(100, 20), 80);
  const base = { count: 100, firedForCount: null as number | null };
  assert.equal(shouldFireEndReached({ ...base, lastRenderedIndex: 40 }), false);
  assert.equal(shouldFireEndReached({ ...base, lastRenderedIndex: 90 }), true);
  assert.equal(shouldFireEndReached({ ...base, lastRenderedIndex: 99, firedForCount: 100 }), false);
  assert.equal(shouldFireEndReached({ ...base, lastRenderedIndex: 99, loading: true }), false);
  assert.equal(shouldFireEndReached({ ...base, lastRenderedIndex: 99, firedForCount: 50 }), true);
  assert.equal(shouldFireEndReached({ count: 0, lastRenderedIndex: -1, firedForCount: null }), false);
});

test('shouldVirtualize: explicit flag or auto above 200 rows', () => {
  assert.equal(shouldVirtualize(true, 3), true);
  assert.equal(shouldVirtualize(false, 5000), false);
  assert.equal(shouldVirtualize('auto', 200), false);
  assert.equal(shouldVirtualize('auto', 201), true);
  assert.equal(shouldVirtualize(undefined, 201), true);
});
