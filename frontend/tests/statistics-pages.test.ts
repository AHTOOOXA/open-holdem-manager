/** Run: cd frontend && npx tsx --test tests/statistics-pages.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createChain, openFresh, openNext } from '../src/lib/page-chain.ts';
import {
  PICKABLE_STATS, STAT_CATEGORIES, categoryCounts, filterStats, statCategories,
} from '../src/lib/statistics/categories.ts';
import {
  cellHandsPage, clearPagesStore, closePages, freshStatChain, labelDetailChain, loadPages, nextActionHandsPage,
  openFromPage, rangeHandsPage, savePages, selectOnly, selectionOf, statPage,
} from '../src/lib/statistics/pages.ts';
import { GENERAL_CELLS } from '../src/lib/h2n-layout.ts';
import type { Step } from '../src/lib/reports/types.ts';

const np = (title: string) => ({ title, inherited: title, state: 0 });

test('openFresh truncates and appends a new page, never reusing', () => {
  let c = createChain(np('root'));
  c = openFresh(c, 0, np('a'));
  c = openFresh(c, 1, np('b'));
  const reused = openNext(c, 0, np('a2'));
  const fresh = openFresh(c, 0, np('a2'));
  assert.deepEqual(fresh.pages.map((p) => p.title), ['root', 'a2']);
  assert.notEqual(fresh.pages[1].id, c.pages[1].id);
  assert.equal(fresh.pages[1].rev, 0);
  assert.equal(reused.pages[1].id, c.pages[1].id); // Reports behaviour unchanged
  assert.equal(openFresh(c, 5, np('x')), c);
});

test('statistics chain: select + open, highlight only, close clears the left selection', () => {
  let c = freshStatChain();
  c = openFromPage(c, 0, { t: 'cell', id: 'preflop.open_raise.CO' }, statPage('preflop.open_raise.CO'));
  assert.equal(c.pages.length, 2);
  assert.equal(c.pages[1].title, 'Open Raise: Cutoff');
  c = openFromPage(c, 1, { t: 'hands', sel: { label: 'Trash', bucket: 'trash' } }, cellHandsPage('preflop.open_raise.CO', { label: 'Trash', bucket: 'trash' }));
  assert.equal(c.pages.length, 3);
  // another cell on page 0: pages 1+ replaced by one new stat page
  const firstStatId = c.pages[1].id;
  c = openFromPage(c, 0, { t: 'cell', id: 'postflop.cbet.Flop' }, statPage('postflop.cbet.Flop'));
  assert.equal(c.pages.length, 2);
  assert.notEqual(c.pages[1].id, firstStatId);
  assert.deepEqual(selectionOf(c, 1), null);
  // an expression cell only highlights and closes the rest
  const h = selectOnly(c, 0, { t: 'cell', id: 'postflop.wtsd.Total' });
  assert.equal(h.pages.length, 1);
  assert.deepEqual(selectionOf(h, 0), { t: 'cell', id: 'postflop.wtsd.Total' });
  // close page 1: page 0's selection is cleared
  const closed = closePages(c, 1);
  assert.equal(closed.pages.length, 1);
  assert.equal(selectionOf(closed, 0), null);
  assert.equal(closePages(closed, 0), closed); // page 0 can't be closed
});

test('hands pages from the 13x13 grid and Next Actions extend the cell chain', () => {
  const detail: Step[] = [{ k: 'pos', v: ['CO'] }, { k: 'row', key: 'P01', label: 'H:R[first_raise]' }];
  const labelled = labelDetailChain(detail, GENERAL_CELLS['preflop.open_raise.CO']);
  assert.equal(labelled[1].label, 'Open Raise: Cutoff');
  const r = rangeHandsPage(labelled, ['AKs', 'QQ']);
  assert.equal(r.title, 'AKs, QQ');
  assert.deepEqual(r.inherited, { kind: 'chain_hands', chain: [...labelled, { k: 'cells', v: ['AKs', 'QQ'], label: 'AKs, QQ' }] });
  const n = nextActionHandsPage(labelled, { caption: 'Fold vs Raise', filter: { k: 'next', street: 'preflop', a: 'fold_vs_raise' } });
  assert.equal(n.title, 'Fold vs Raise');
  assert.deepEqual(n.inherited.kind === 'chain_hands' && n.inherited.chain.at(-1), {
    k: 'next', street: 'preflop', a: 'fold_vs_raise', label: 'Fold vs Raise',
  });
});

test('pages store: restored per dashboard, dropped when the definition changes', () => {
  clearPagesStore();
  const fresh = loadPages('1:5', 'A');
  assert.equal(fresh.chain.pages.length, 1);
  const opened = openFromPage(fresh.chain, 0, { t: 'cell', id: 'preflop.open_raise.CO' }, statPage('preflop.open_raise.CO'));
  savePages('1:5', { defKey: 'A', chain: opened });
  assert.equal(loadPages('1:5', 'A').chain.pages.length, 2);
  assert.equal(loadPages('1:5', 'B').chain.pages.length, 1);
  assert.equal(loadPages('1:6', 'A').chain.pages.length, 1);
});

test('stat picker: action stats only, no repeats, unique labels, categories', () => {
  assert.ok(PICKABLE_STATS.length > 40);
  for (const s of PICKABLE_STATS) {
    const m = GENERAL_CELLS[s.id];
    assert.equal(m.kind, 'action', s.id);
    assert.equal(m.sameAs, undefined, s.id);
    assert.equal(s.categories[0], 'all');
  }
  const labels = PICKABLE_STATS.map((s) => s.label);
  assert.equal(new Set(labels).size, labels.length, 'labels are unique');
  assert.equal(PICKABLE_STATS.some((s) => s.id === 'postflop.wtsd.Total'), false);
  const counts = categoryCounts(PICKABLE_STATS);
  assert.equal(counts.all, PICKABLE_STATS.length);
  for (const c of STAT_CATEGORIES) assert.ok(counts[c.id] > 0, c.label);
  assert.deepEqual(statCategories(GENERAL_CELLS['postflop.cbet.Flop']), ['all', 'raise1st', 'flop_bet']);
  assert.deepEqual(statCategories(GENERAL_CELLS['postflop.vs_cbet_3bet.Call']), ['all', 'call_3bet', 'flop_call']);
  assert.deepEqual(statCategories(GENERAL_CELLS['postflop.fold_to_cbet.Flop']), ['all', 'pf_call']);
  assert.deepEqual(statCategories(GENERAL_CELLS['preflop.squeeze.Total']), ['all', '3bet']);
});

test('stat picker search and category filter', () => {
  const open = filterStats(PICKABLE_STATS, 'open raise');
  assert.ok(open.some((s) => s.id === 'preflop.open_raise.CO'));
  const cutoff = filterStats(PICKABLE_STATS, 'cutoff open');
  assert.ok(cutoff.every((s) => s.label.toLowerCase().includes('cutoff')));
  assert.ok(cutoff.some((s) => s.id === 'preflop.open_raise.CO'));
  assert.deepEqual(filterStats(PICKABLE_STATS, 'open raise', 'call_3bet'), []);
});
