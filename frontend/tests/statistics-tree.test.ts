/** Run: cd frontend && npx tsx --test tests/statistics-tree.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY_HISTORY, ancestorIds, canDelete, canMove, clampTreeWidth, cloneDashboard, createDashboard, createFolder,
  dashboardCount, deleteNode, displayName, firstDashboardId, matchesSearch, moveNode, pushHistory, redo, renameNode,
  setDefinition, stripCopySuffix, targetFolder, undo, uniqueName, visibleRows,
} from '../src/lib/statistics/tree.ts';
import type { DashboardNode, DashboardsDoc } from '../src/lib/statistics/types.ts';

const def = { player_id: null, filters: [], profile_id: 'default' };
const dash = (id: number, name: string, parent_id: number | null = null): DashboardNode =>
  ({ id, kind: 'dashboard', name, parent_id, definition: { ...def } });
const folder = (id: number, name: string, parent_id: number | null = null): DashboardNode =>
  ({ id, kind: 'folder', name, parent_id });
const doc = (nodes: DashboardNode[], selected_id: number | null = 1): DashboardsDoc =>
  ({ nodes, config: { selected_id, collapsed: false, tree_width: 300 } });

// 1 "new dashboard" (root), 2 folder "Me" with 3 "Cash" and 4 folder "Old" (empty), 5 folder "B" (root)
const sample = () => doc([dash(1, 'new dashboard'), folder(2, 'Me'), dash(3, 'Cash', 2), folder(4, 'Old', 2), folder(5, 'B')]);

test('rows: folders first, ordinal name order, 14px levels, expansion', () => {
  const d = doc([dash(1, 'b'), dash(2, 'B'), folder(3, 'z'), folder(4, 'A'), dash(5, 'x', 3)]);
  assert.deepEqual(visibleRows(d.nodes, new Set()).map((r) => r.node.name), ['A', 'z', 'B', 'b']);
  const open = visibleRows(d.nodes, new Set([3]));
  assert.deepEqual(open.map((r) => [r.node.name, r.level]), [['A', 0], ['z', 0], ['x', 1], ['B', 0], ['b', 0]]);
  assert.equal(open[1].expanded, true);
  assert.equal(open[1].hasChildren, true);
  assert.equal(open[0].hasChildren, false);
});

test('search: substring, all words, parents kept open', () => {
  assert.equal(matchesSearch('Cash all time', 'ALL'), true);
  assert.equal(matchesSearch('Cash all time', 'time cash'), true);
  assert.equal(matchesSearch('Cash all time', 'time poker'), false);
  assert.equal(matchesSearch('Cash all time', 'x cash'), false); // one-letter words don't count as words
  assert.equal(matchesSearch('anything', '   '), true);
  const rows = visibleRows(sample().nodes, new Set(), 'cash');
  assert.deepEqual(rows.map((r) => r.node.name), ['Me', 'Cash']);
  assert.equal(rows[0].expanded, true);
});

test('unique names and clone suffix', () => {
  assert.equal(uniqueName('new dashboard', []), 'new dashboard');
  assert.equal(uniqueName('new dashboard', ['new dashboard', 'new dashboard (1)']), 'new dashboard (2)');
  assert.equal(stripCopySuffix('Me (3)'), 'Me');
  assert.equal(stripCopySuffix('Me'), 'Me');
  assert.equal(stripCopySuffix('(2)'), '(2)');
});

test('create dashboard goes into the selected folder, selected, unique among siblings', () => {
  const d = sample();
  assert.equal(targetFolder(d, 3), 2);
  assert.equal(targetFolder(d, 2), 2);
  assert.equal(targetFolder(d, null), null);
  const a = createDashboard(d, null);
  assert.equal(a.id, 6);
  assert.equal(a.doc.config.selected_id, 6);
  const made = a.doc.nodes.find((n) => n.id === 6)!;
  assert.equal(made.name, 'new dashboard (1)');
  const b = createDashboard(d, 2);
  assert.equal(b.doc.nodes.find((n) => n.id === 6)!.name, 'new dashboard');
});

test('create folder does not change the shown dashboard', () => {
  const r = createFolder(sample(), null);
  assert.equal(r.doc.config.selected_id, 1);
  assert.equal(r.doc.nodes.find((n) => n.id === r.id)!.name, 'New Folder');
});

test('clone copies the definition only and strips the suffix', () => {
  let d = doc([dash(1, 'Me (2)'), dash(2, 'Me')]);
  d = setDefinition(d, 1, { player_id: 7, filters: [{ k: 'mode', v: 'fast' }], profile_id: 'x' });
  const c = cloneDashboard(d, 1)!;
  const n = c.doc.nodes.find((x) => x.id === c.id)!;
  assert.equal(n.name, 'Me (1)');
  assert.equal(n.kind === 'dashboard' && n.definition.player_id, 7);
  assert.equal(c.doc.config.selected_id, c.id);
  // deep copy
  const src = c.doc.nodes.find((x) => x.id === 1)!;
  assert.notEqual(n.kind === 'dashboard' && n.definition.filters, src.kind === 'dashboard' && src.definition.filters);
  assert.equal(cloneDashboard(d, 99), null);
});

test('rename trims, refuses empty, caps 200', () => {
  const d = sample();
  assert.equal(renameNode(d, 1, '   '), d);
  assert.equal(renameNode(d, 1, 'new dashboard'), d);
  assert.equal(renameNode(d, 1, '  Me  ').nodes[0].name, 'Me');
  assert.equal(renameNode(d, 1, 'x'.repeat(300)).nodes[0].name.length, 200);
  assert.equal(displayName('A->B'), 'A→B');
});

test('delete: never the last dashboard, only empty folders, selection handed over', () => {
  const one = doc([dash(1, 'only')]);
  assert.equal(canDelete(one, 1), false);
  assert.equal(deleteNode(one, 1), one);
  const d = sample();
  assert.equal(canDelete(d, 2), false); // has children
  assert.equal(canDelete(d, 4), true);
  assert.equal(deleteNode(d, 2), d);
  const gone = deleteNode(d, 1);
  assert.equal(dashboardCount(gone), 1);
  assert.equal(gone.config.selected_id, 3);
  assert.equal(firstDashboardId(gone), 3);
});

test('move (cut + paste): no cycles, only into folders, name made unique', () => {
  const d = sample();
  assert.equal(canMove(d, 2, 4), false); // into its own child
  assert.equal(canMove(d, 2, 2), false);
  assert.equal(canMove(d, 1, 3), false); // a dashboard is not a folder
  assert.equal(canMove(d, 3, 2), false); // already there
  const m = moveNode(d, 2, 5);
  assert.equal(m.nodes.find((n) => n.id === 2)!.parent_id, 5);
  assert.deepEqual(ancestorIds(m.nodes, 3), [2, 5]);
  const clash = moveNode(doc([dash(1, 'a'), folder(2, 'f'), dash(3, 'a', 2)]), 3, null);
  assert.equal(clash.nodes.find((n) => n.id === 3)!.name, 'a (1)');
});

test('undo / redo restore the structure but keep current definitions', () => {
  const d0 = sample();
  let h = EMPTY_HISTORY;
  h = pushHistory(h, d0.nodes);
  const d1 = renameNode(d0, 1, 'renamed');
  const changed = setDefinition(d1, 1, { player_id: 3, filters: [], profile_id: 'default' });
  const u = undo(h, changed)!;
  const n = u.doc.nodes.find((x) => x.id === 1)!;
  assert.equal(n.name, 'new dashboard');
  assert.equal(n.kind === 'dashboard' && n.definition.player_id, 3);
  assert.equal(undo(u.history, u.doc), null);
  const r = redo(u.history, u.doc)!;
  assert.equal(r.doc.nodes.find((x) => x.id === 1)!.name, 'renamed');
  assert.equal(redo(r.history, r.doc), null);
});

test('undo of a create repairs the selection', () => {
  const d0 = sample();
  const c = createDashboard(d0, null);
  const u = undo(pushHistory(EMPTY_HISTORY, d0.nodes), c.doc)!;
  // the restored tree has no node 6: the first dashboard in tree order is shown (folders first)
  assert.equal(u.doc.config.selected_id, 3);
});

test('tree width clamp', () => {
  assert.equal(clampTreeWidth(100), 280);
  assert.equal(clampTreeWidth(5000), 1000);
  assert.equal(clampTreeWidth(301.6), 302);
  assert.equal(clampTreeWidth(Number.NaN), 300);
});
