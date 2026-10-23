/** Run: cd frontend && npx tsx --test tests/reports-pages.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  addLowerTab, applyLegacyTab, closeAllPages, closePagesFrom, CHAIN_STORAGE_VERSION, DEFAULT_LOWER_TABS,
  filterTabFor, freshChain, fullChain, initialPageState, isStep, lowerTabsFor, normalizeTabs, openFrom,
  parseStoredChain, parseTabMemory, removeLowerTab, removeOwnStep, reportQuery, resetPage0, selectedCells,
  selectedHv, serializeChain, setCellsSelection, setHvSelection, setLowerTab, setOwnSteps, stepLabel,
  upperChain, type OpenArgs, type ReportChain,
} from '../src/lib/reports/pages.ts';
import { formatReportValue } from '../src/lib/reports/format-value.ts';
import type { Step } from '../src/lib/reports/types.ts';

const BTN: Step = { k: 'pos', v: ['BTN'], label: 'BTN' };
const RFI: Step = { k: 'row', key: 'P01', label: 'Raise 1st In' };
const CBET: Step = { k: 'next', street: 'flop', a: 'bet', label: 'Continuation Bet' };
const FOLD: Step = { k: 'next', street: 'flop', a: 'fold' };

const row = (tab: OpenArgs['selected']['tab'], key: string, filter: Step, extra: Partial<OpenArgs> = {}): OpenArgs => ({
  selected: { tab, key },
  filter,
  title: key,
  remembered: null,
  ...extra,
});

/** page 0 (own BTN) -> page 1 (from a Next Actions row) -> page 2. */
function threePages(): ReportChain {
  let c = setOwnSteps(freshChain(), 0, [BTN]);
  c = openFrom(c, 0, row('next_actions', 'cbet', CBET));
  c = openFrom(c, 1, row('results', 'nl10', { k: 'game', stakes: 'NL10', mode: 'fast', tsize: 6 }));
  return c;
}

// ── Tab defaults and augmentation ───────────────────────────────────────────────────────────

test('fresh chain: one page with the cash default tabs, Stats + Hands selected', () => {
  const c = freshChain();
  assert.equal(c.pages.length, 1);
  assert.deepEqual(c.pages[0].state.lowerTabs, DEFAULT_LOWER_TABS);
  assert.equal(c.pages[0].state.upperTab, 'stats');
  assert.equal(c.pages[0].state.lowerTab, 'hands');
  assert.deepEqual(c.pages[0].inherited, []);
});

test('lowerTabsFor: remembered list wins; action/position rows append Next Actions, Faced Next, Bet Sizing', () => {
  assert.deepEqual(lowerTabsFor('results', null), DEFAULT_LOWER_TABS);
  assert.deepEqual(lowerTabsFor('next_actions', null), ['hands', 'results', 'positions', 'next_actions', 'faced_next', 'bet_sizing']);
  assert.deepEqual(lowerTabsFor('positions', ['hands', 'hour_of_day']), ['hands', 'hour_of_day', 'next_actions', 'faced_next', 'bet_sizing']);
  assert.deepEqual(lowerTabsFor('results', ['hour_of_day']), ['hands', 'hour_of_day']);
});

test('normalizeTabs / parseTabMemory: Hands first, unknown and duplicate tabs dropped', () => {
  assert.deepEqual(normalizeTabs(['results', 'hands', 'nope', 'results', 3]), ['hands', 'results']);
  assert.deepEqual(parseTabMemory('["positions"]'), ['hands', 'positions']);
  assert.equal(parseTabMemory('{'), null);
  assert.equal(parseTabMemory('{"a":1}'), null);
  assert.equal(parseTabMemory(null), null);
});

test('initialPageState selects open_tab when the page has it, else Hands', () => {
  assert.equal(initialPageState('next_actions', null, 'faced_next').lowerTab, 'faced_next');
  assert.equal(initialPageState('results', null, 'faced_next').lowerTab, 'hands');
});

// ── Opening pages ───────────────────────────────────────────────────────────────────────────

test('row click: selects the row, appends a page inheriting fullChain + row filter', () => {
  let c = setOwnSteps(freshChain(), 0, [BTN]);
  c = setCellsSelection(c, 0, ['AKs']);
  c = openFrom(c, 0, row('next_actions', 'cbet', CBET, { title: 'Continuation Bet', openTab: 'faced_next' }));
  assert.equal(c.pages.length, 2);
  assert.deepEqual(c.pages[0].state.selectedRow, { tab: 'next_actions', key: 'cbet' });
  const p1 = c.pages[1];
  assert.equal(p1.title, 'Continuation Bet');
  assert.deepEqual(p1.inherited.map((s) => s.k), ['pos', 'cells', 'next']);
  assert.deepEqual(p1.state.own, []);
  assert.equal(p1.state.lowerTab, 'faced_next');
  assert.equal(p1.state.openedFrom, 'next_actions');
  assert.ok(p1.state.lowerTabs.includes('bet_sizing'));
});

test('stat click opens a page remembered as "hands" (no augmentation)', () => {
  const c = openFrom(freshChain(), 0, row('stats', 'k', RFI, { title: 'Raise 1st In' }));
  assert.equal(c.pages[1].state.openedFrom, 'hands');
  assert.deepEqual(c.pages[1].state.lowerTabs, DEFAULT_LOWER_TABS);
  assert.deepEqual(c.pages[0].state.selectedRow, { tab: 'stats', key: 'k' });
});

test('clicking the already selected row keeps the chain unchanged', () => {
  const c = threePages();
  assert.equal(openFrom(c, 0, row('next_actions', 'cbet', CBET)), c);
});

test('another row on a middle page reuses the next slot (keeps own filter + tabs) and drops the rest', () => {
  let c = threePages();
  c = setOwnSteps(c, 1, [RFI]); // drops page 2
  c = openFrom(c, 1, row('results', 'nl10', { k: 'game', stakes: 'NL10', mode: 'fast', tsize: 6 }));
  c = addLowerTab(c, 1, 'hour_of_day');
  const slotId = c.pages[1].id;
  const r = openFrom(c, 0, row('positions', 'BTN', BTN, { title: 'BTN' }));
  assert.equal(r.pages.length, 2);
  assert.equal(r.pages[1].id, slotId);
  assert.equal(r.pages[1].title, 'BTN');
  assert.deepEqual(r.pages[1].state.own, [RFI]);
  assert.ok(r.pages[1].state.lowerTabs.includes('hour_of_day'));
  assert.equal(r.pages[1].state.selectedRow, null);
  assert.equal(r.pages[1].state.openedFrom, 'positions');
  assert.deepEqual(r.pages[0].state.selectedRow, { tab: 'positions', key: 'BTN' });
  assert.deepEqual(r.pages[1].inherited, [BTN, BTN]);
});

test('selecting a row in one tab replaces the selection of the other tabs', () => {
  let c = openFrom(freshChain(), 0, row('results', 'a', BTN));
  c = openFrom(c, 0, row('positions', 'b', BTN));
  assert.deepEqual(c.pages[0].state.selectedRow, { tab: 'positions', key: 'b' });
});

// ── Truncation ──────────────────────────────────────────────────────────────────────────────

test('changing or removing an own step truncates the pages after it and clears its selection', () => {
  const c = threePages();
  const a = setOwnSteps(c, 1, [RFI]);
  assert.equal(a.pages.length, 2);
  assert.equal(a.pages[1].state.selectedRow, null);
  const b = removeOwnStep(c, 0, 0);
  assert.equal(b.pages.length, 1);
  assert.deepEqual(b.pages[0].state.own, []);
  assert.equal(removeOwnStep(c, 0, 5), c);
});

test('range / hand-strength selections narrow lower tabs only and truncate later pages', () => {
  let c = threePages();
  c = setCellsSelection(c, 0, ['AA', 'KK']);
  assert.equal(c.pages.length, 1);
  assert.deepEqual(selectedCells(c.pages[0].state.lower), ['AA', 'KK']);
  c = setHvSelection(c, 0, { street: 'flop', cats: ['top_pair'] });
  assert.deepEqual(selectedHv(c.pages[0].state.lower), { street: 'flop', cats: ['top_pair'] });
  assert.deepEqual(upperChain(c.pages[0]), [BTN]);
  assert.deepEqual(fullChain(c.pages[0]).map((s) => s.k), ['pos', 'cells', 'hv']);
  // cells keep their place before hv whatever the click order
  c = setCellsSelection(c, 0, ['QQ']);
  assert.deepEqual(fullChain(c.pages[0]).map((s) => s.k), ['pos', 'cells', 'hv']);
  c = setCellsSelection(c, 0, []);
  c = setHvSelection(c, 0, null);
  assert.deepEqual(c.pages[0].state.lower, []);
});

test('closePagesFrom clears the left page selection; page 0 cannot close', () => {
  const c = threePages();
  const r = closePagesFrom(c, 1);
  assert.equal(r.pages.length, 1);
  assert.equal(r.pages[0].state.selectedRow, null);
  assert.equal(closePagesFrom(c, 0), c);
});

test('gear: Close Pages and Reset Filter', () => {
  let c = setCellsSelection(threePages(), 1, ['AA']);
  c = closeAllPages(c);
  assert.equal(c.pages.length, 1);
  assert.equal(c.pages[0].state.selectedRow, null);
  assert.deepEqual(c.pages[0].state.own, [BTN]);
  const r = resetPage0(setCellsSelection(threePages(), 0, ['AA']));
  assert.equal(r.pages.length, 1);
  assert.deepEqual(r.pages[0].state.own, []);
  assert.deepEqual(r.pages[0].state.lower, []);
});

// ── Lower tabs ──────────────────────────────────────────────────────────────────────────────

test('addLowerTab selects an existing tab or appends + selects a new one', () => {
  let c = addLowerTab(freshChain(), 0, 'results');
  assert.deepEqual(c.pages[0].state.lowerTabs, DEFAULT_LOWER_TABS);
  assert.equal(c.pages[0].state.lowerTab, 'results');
  c = addLowerTab(c, 0, 'stack_sizes');
  assert.equal(c.pages[0].state.lowerTabs.at(-1), 'stack_sizes');
  assert.equal(c.pages[0].state.lowerTab, 'stack_sizes');
});

test('removeLowerTab: never Hands; selected tab falls back to Hands; a tab holding the selection closes pages', () => {
  let c = setLowerTab(freshChain(), 0, 'results');
  assert.equal(removeLowerTab(c, 0, 'hands'), c);
  c = removeLowerTab(c, 0, 'results');
  assert.equal(c.pages[0].state.lowerTab, 'hands');
  assert.ok(!c.pages[0].state.lowerTabs.includes('results'));

  const t = threePages();
  const kept = removeLowerTab(t, 0, 'results');
  assert.equal(kept.pages.length, 3);
  const cut = removeLowerTab(t, 0, 'next_actions');
  assert.equal(cut.pages.length, 1);
  assert.equal(cut.pages[0].state.selectedRow, null);
});

test('applyLegacyTab maps old ?tab= links to page 0 tabs', () => {
  assert.equal(applyLegacyTab(freshChain(), 'graph').pages[0].state.upperTab, 'graph');
  assert.equal(applyLegacyTab(freshChain(), 'range').pages[0].state.upperTab, 'range');
  const h = applyLegacyTab(setLowerTab(freshChain(), 0, 'results'), 'hands');
  assert.equal(h.pages[0].state.lowerTab, 'hands');
});

// ── Queries ─────────────────────────────────────────────────────────────────────────────────

test('reportQuery omits player_id for the hero', () => {
  assert.deepEqual(reportQuery({ workspaceId: 2 }, [BTN]), { workspace_id: 2, chain: [BTN] });
  assert.deepEqual(reportQuery({ workspaceId: 2, playerId: 9 }, []), { workspace_id: 2, player_id: 9, chain: [] });
});

// ── Persistence ─────────────────────────────────────────────────────────────────────────────

test('serialize/parse round trip keeps pages, filters, tabs and selection but not widths', () => {
  let c = threePages();
  c = setCellsSelection(c, 2, ['AKs']);
  c = { ...c, pages: c.pages.map((p) => ({ ...p, width: 400 })) };
  const raw = serializeChain(c, { id: 5, username: 'v', site: 'GG' });
  assert.ok(!raw.includes('"width"'));
  const back = parseStoredChain(raw);
  assert.ok(back);
  assert.deepEqual(back.player, { id: 5, username: 'v', site: 'GG' });
  assert.equal(back.chain.pages.length, 3);
  for (let i = 0; i < 3; i++) {
    assert.deepEqual(back.chain.pages[i].inherited, c.pages[i].inherited);
    assert.deepEqual(back.chain.pages[i].state, c.pages[i].state);
    assert.equal(back.chain.pages[i].title, c.pages[i].title);
    assert.notEqual(back.chain.pages[i].width, 400);
  }
});

test('parseStoredChain rejects bad JSON, wrong versions and empty chains', () => {
  assert.equal(parseStoredChain(null), null);
  assert.equal(parseStoredChain('nope'), null);
  assert.equal(parseStoredChain(JSON.stringify({ v: CHAIN_STORAGE_VERSION + 1, pages: [{}] })), null);
  assert.equal(parseStoredChain(JSON.stringify({ v: CHAIN_STORAGE_VERSION, pages: [] })), null);
});

test('parseStoredChain drops unknown own steps and pages whose inherited chain is invalid', () => {
  const c = threePages();
  const data = JSON.parse(serializeChain(c, null));
  data.pages[0].own.push({ k: 'martian', v: 1 });
  data.pages[0].lowerTabs = ['results', 'bogus'];
  data.pages[0].lowerTab = 'bogus';
  data.pages[2].inherited.push({ k: 'pos', v: ['XX'] });
  const back = parseStoredChain(JSON.stringify(data));
  assert.ok(back);
  assert.equal(back.chain.pages.length, 2);
  assert.deepEqual(back.chain.pages[0].state.own, [BTN]);
  assert.deepEqual(back.chain.pages[0].state.lowerTabs, ['hands', 'results']);
  assert.equal(back.chain.pages[0].state.lowerTab, 'hands');
  // The new last page has nothing to its right: its stale selection is gone
  assert.equal(back.chain.pages[1].state.selectedRow, null);
  assert.equal(back.player, null);
});

test('isStep validates shapes of every kind', () => {
  const ok: Step[] = [
    BTN, RFI, CBET, FOLD,
    { k: 'stakes', v: ['NL10'] }, { k: 'mode', v: 'fast' }, { k: 'tsize', v: [6] },
    { k: 'date', from: '2026-01-01' }, { k: 'hour', v: [1, 2] }, { k: 'stack', lo: 0, hi: null },
    { k: 'game', stakes: 'NL10', mode: 'fast', tsize: 6 }, { k: 'cells', v: ['AA'] },
    { k: 'hv', street: 'flop', cats: ['x'] }, { k: 'faced', street: 'turn', a: 'villain_bet' },
    { k: 'betsize', bucket: '33' },
  ];
  for (const s of ok) assert.ok(isStep(s), JSON.stringify(s));
  for (const s of [null, 1, {}, { k: 'pos', v: ['ZZ'] }, { k: 'mode', v: 'x' }, { k: 'stack', lo: 'a', hi: 1 }, { k: 'row' }, { k: 'pos', v: [], label: 3 }]) {
    assert.ok(!isStep(s), JSON.stringify(s));
  }
});

test('stepLabel prefers the label; filterTabFor picks the dialog tab', () => {
  assert.equal(stepLabel(RFI), 'Raise 1st In');
  assert.equal(stepLabel({ k: 'pos', v: ['CO', 'BTN'] }), 'CO, BTN');
  assert.equal(stepLabel({ k: 'stack', lo: 40, hi: 100 }), '40–100 bb');
  assert.equal(filterTabFor(RFI), 'quick');
  assert.equal(filterTabFor(BTN), 'positions');
  assert.equal(filterTabFor({ k: 'date', from: '2026-01-01' }), 'session');
  assert.equal(filterTabFor({ k: 'stakes', v: ['NL10'] }), 'general');
});

test('formatReportValue by ValueFormat', () => {
  assert.equal(formatReportValue(null, 'pct'), '--');
  assert.equal(formatReportValue(1250, 'count'), '1.2k');
  assert.equal(formatReportValue(-3.5, 'money'), '-$3.50');
  assert.equal(formatReportValue(3.5, 'bb'), '3.5');
  assert.equal(formatReportValue(1.2, 'bb100'), '1.20');
  assert.equal(formatReportValue(42.4, 'pct'), '42');
  assert.equal(formatReportValue(10, 'pct', 0), '--');
});
