/**
 * Reports screen: pure page-state model on top of lib/page-chain.
 *
 * A page = Page<Step[], ReportPageState>:
 *  - inherited  steps from the pages to its left (previous pages' own + lower + the clicked row/stat filter)
 *  - own        the page's chips (plain steps + `row` quick filters), edited in the filter dialog
 *  - lower      Preflop Range / Hand Strength selections (`cells`, `hv`): not chips; they narrow the
 *               lower tabs and later pages only (Hand2Note rule), never the page's own upper tabs
 *
 * Chains sent to the backend:
 *  - upper tabs (Stats, Graph, Preflop Range, Hand Strength): [...inherited, ...own]
 *  - lower tabs (Hands, split reports) and the next page:     [...inherited, ...own, ...lower]
 */
import {
  closeFrom, createChain, openNext, setPageState, truncateAfter,
  type Page, type PageChain,
} from '@/lib/page-chain';
import { resolvePresets } from './steps';
import type { ReportQuery, SplitType, Step, Street } from './types';

export type UpperTab = 'stats' | 'graph' | 'range' | 'strength';
export type LowerTab = 'hands' | SplitType;
export type HvStreet = Exclude<Street, 'preflop'>;
export interface HvSelection { street: HvStreet; cats: string[] }

/** The selected row of a page: a split row (`tab` = its report) or a clicked stat (`tab` = 'stats'). */
export interface SelectedRow { tab: LowerTab | 'stats'; key: string }

export interface ReportPageState {
  own: Step[];
  lower: Step[];
  upperTab: UpperTab;
  lowerTabs: LowerTab[];
  lowerTab: LowerTab;
  selectedRow: SelectedRow | null;
  /** The report whose row opened this page ('hands' = page 0 or opened from the Stats tab): tab-memory key. */
  openedFrom: LowerTab;
}

export type ReportPage = Page<Step[], ReportPageState>;
export type ReportChain = PageChain<Step[], ReportPageState>;

export const UPPER_TABS: readonly UpperTab[] = ['stats', 'graph', 'range', 'strength'];
export const SPLIT_TYPES: readonly SplitType[] = [
  'results', 'positions', 'next_actions', 'faced_next', 'bet_sizing', 'stack_sizes', 'hour_of_day', 'table_size',
];
export const LOWER_TABS: readonly LowerTab[] = ['hands', ...SPLIT_TYPES];

/** Cash defaults (Hand2Note 03 §2.1). */
export const DEFAULT_LOWER_TABS: readonly LowerTab[] = ['hands', 'results', 'positions', 'next_actions'];
/** Rows of these reports open a page that also gets AUGMENT_TABS (03 §2.4). */
export const AUGMENT_FROM: ReadonlySet<LowerTab> = new Set<LowerTab>(['next_actions', 'faced_next', 'positions']);
export const AUGMENT_TABS: readonly LowerTab[] = ['next_actions', 'faced_next', 'bet_sizing'];

export const PAGE0_TITLE = 'Reports';

export function isUpperTab(v: unknown): v is UpperTab {
  return typeof v === 'string' && (UPPER_TABS as readonly string[]).includes(v);
}

export function isLowerTab(v: unknown): v is LowerTab {
  return typeof v === 'string' && (LOWER_TABS as readonly string[]).includes(v);
}

// ── Chains ──────────────────────────────────────────────────────────────────────────────────

/** Chain of the upper tabs: inherited + own (range selections excluded). */
export function composeUpper(inherited: readonly Step[], own: readonly Step[], now?: Date): Step[] {
  return resolvePresets([...inherited, ...own], now);
}

/** Chain of the lower tabs and of the next page: inherited + own + range / hand-strength selections. */
export function composeFull(inherited: readonly Step[], own: readonly Step[], lower: readonly Step[], now?: Date): Step[] {
  return resolvePresets([...inherited, ...own, ...lower], now);
}

export function upperChain(page: Pick<ReportPage, 'inherited' | 'state'>): Step[] {
  return composeUpper(page.inherited, page.state.own);
}

export function fullChain(page: Pick<ReportPage, 'inherited' | 'state'>): Step[] {
  return composeFull(page.inherited, page.state.own, page.state.lower);
}

export interface Dashboard {
  workspaceId: number;
  /** Omitted = the active hero. */
  playerId?: number;
}

export function reportQuery(d: Dashboard, chain: Step[]): ReportQuery {
  return d.playerId === undefined
    ? { workspace_id: d.workspaceId, chain }
    : { workspace_id: d.workspaceId, player_id: d.playerId, chain };
}

// ── Lower tab lists ─────────────────────────────────────────────────────────────────────────

/** Clean a tab list: known tabs only, no duplicates, "hands" first. */
export function normalizeTabs(tabs: readonly unknown[]): LowerTab[] {
  const out: LowerTab[] = ['hands'];
  for (const t of tabs) if (isLowerTab(t) && !out.includes(t)) out.push(t);
  return out;
}

/** Parse a remembered tab list (localStorage value); null when absent or invalid. */
export function parseTabMemory(raw: string | null | undefined): LowerTab[] | null {
  if (!raw) return null;
  try {
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v) ? normalizeTabs(v) : null;
  } catch {
    return null;
  }
}

export function tabMemoryKey(openedFrom: LowerTab): string {
  return `ohm.reports.tabs.${openedFrom}`;
}

function augment(tabs: LowerTab[], openedFrom: LowerTab): LowerTab[] {
  if (!AUGMENT_FROM.has(openedFrom)) return tabs;
  const out = [...tabs];
  for (const t of AUGMENT_TABS) if (!out.includes(t)) out.push(t);
  return out;
}

/** Tabs of a new page opened from a row of `openedFrom`: remembered (or defaults), then augmented. */
export function lowerTabsFor(openedFrom: LowerTab, remembered: readonly LowerTab[] | null): LowerTab[] {
  return augment(normalizeTabs(remembered ?? DEFAULT_LOWER_TABS), openedFrom);
}

export function initialPageState(
  openedFrom: LowerTab,
  remembered: readonly LowerTab[] | null,
  openTab?: LowerTab,
): ReportPageState {
  const lowerTabs = lowerTabsFor(openedFrom, remembered);
  return {
    own: [],
    lower: [],
    upperTab: 'stats',
    lowerTabs,
    lowerTab: openTab && lowerTabs.includes(openTab) ? openTab : 'hands',
    selectedRow: null,
    openedFrom,
  };
}

export function freshChain(remembered: readonly LowerTab[] | null = null): ReportChain {
  return createChain({ title: PAGE0_TITLE, inherited: [], state: initialPageState('hands', remembered) });
}

// ── Page edits ──────────────────────────────────────────────────────────────────────────────

function patch(chain: ReportChain, index: number, fn: (s: ReportPageState) => ReportPageState): ReportChain {
  const page = chain.pages[index];
  if (!page) return chain;
  const next = fn(page.state);
  return next === page.state ? chain : setPageState(chain, index, next);
}

function sameRow(a: SelectedRow | null, b: SelectedRow | null): boolean {
  return a === b || (!!a && !!b && a.tab === b.tab && a.key === b.key);
}

export interface OpenArgs {
  /** What was clicked on page `index`. */
  selected: SelectedRow;
  /** Step appended to the page's full chain. */
  filter: Step;
  title: string;
  /** Lower tab the new page should select (split rows' `open_tab`). */
  openTab?: LowerTab;
  /** Remembered tab list for `openedFrom` (localStorage), null = defaults. */
  remembered: readonly LowerTab[] | null;
}

/**
 * Select a row (or stat) on page `index` and open the page to its right with
 * inherited = fullChain(page) + filter. The next slot is reused when it exists (it keeps
 * its own filter, range selections and tabs; gets the new inherited chain; pages after it
 * close). Clicking the row that is already selected (and already open) changes nothing.
 */
export function openFrom(chain: ReportChain, index: number, a: OpenArgs): ReportChain {
  const page = chain.pages[index];
  if (!page) return chain;
  if (sameRow(page.state.selectedRow, a.selected) && index + 1 < chain.pages.length) return chain;

  const openedFrom: LowerTab = a.selected.tab === 'stats' ? 'hands' : a.selected.tab;
  const inherited = [...fullChain(page), a.filter];
  const reuse = index + 1 < chain.pages.length;
  let c = patch(chain, index, (s) => ({ ...s, selectedRow: a.selected }));
  c = openNext(c, index, {
    title: a.title,
    inherited,
    state: initialPageState(openedFrom, a.remembered, a.openTab),
  });
  if (reuse) {
    c = patch(c, index + 1, (s) => {
      const lowerTabs = augment(s.lowerTabs, openedFrom);
      const lowerTab = a.openTab && lowerTabs.includes(a.openTab) ? a.openTab : s.lowerTab;
      return { ...s, openedFrom, lowerTabs, lowerTab, selectedRow: null };
    });
  }
  return c;
}

export function clearSelection(chain: ReportChain, index: number): ReportChain {
  return patch(chain, index, (s) => (s.selectedRow ? { ...s, selectedRow: null } : s));
}

/** Close page `index` and everything right of it; the left page loses its selection. */
export function closePagesFrom(chain: ReportChain, index: number): ReportChain {
  if (index < 1) return chain;
  return clearSelection(closeFrom(chain, index), index - 1);
}

/** A page's filtering changed: drop the pages after it and its selection. */
function filterChanged(chain: ReportChain, index: number, fn: (s: ReportPageState) => ReportPageState): ReportChain {
  if (!chain.pages[index]) return chain;
  return truncateAfter(patch(chain, index, (s) => ({ ...fn(s), selectedRow: null })), index);
}

export function setOwnSteps(chain: ReportChain, index: number, own: Step[]): ReportChain {
  return filterChanged(chain, index, (s) => ({ ...s, own }));
}

export function removeOwnStep(chain: ReportChain, index: number, stepIndex: number): ReportChain {
  const page = chain.pages[index];
  if (!page || stepIndex < 0 || stepIndex >= page.state.own.length) return chain;
  return setOwnSteps(chain, index, page.state.own.filter((_, i) => i !== stepIndex));
}

export function selectedCells(lower: readonly Step[]): string[] {
  const step = lower.find((x) => x.k === 'cells');
  return step && step.k === 'cells' ? step.v : [];
}

export function selectedHv(lower: readonly Step[]): HvSelection | null {
  const step = lower.find((x) => x.k === 'hv');
  return step && step.k === 'hv' && step.street !== 'preflop' ? { street: step.street, cats: step.cats } : null;
}

function shortList(items: string[], max = 4): string {
  return items.length <= max ? items.join(', ') : `${items.slice(0, max).join(', ')} +${items.length - max}`;
}

/** Order of lower steps: cells first, then hv (stable regardless of click order). */
function withLower(lower: Step[], kind: 'cells' | 'hv', step: Step | null): Step[] {
  const rest = lower.filter((x) => x.k !== kind);
  const all = step ? [...rest, step] : rest;
  return [...all.filter((x) => x.k === 'cells'), ...all.filter((x) => x.k === 'hv')];
}

export function setCellsSelection(chain: ReportChain, index: number, cells: string[]): ReportChain {
  const step: Step | null = cells.length ? { k: 'cells', v: [...cells], label: shortList(cells) } : null;
  return filterChanged(chain, index, (s) => ({ ...s, lower: withLower(s.lower, 'cells', step) }));
}

const STREET_NAME: Record<HvStreet, string> = { flop: 'Flop', turn: 'Turn', river: 'River' };

export function setHvSelection(chain: ReportChain, index: number, v: HvSelection | null): ReportChain {
  const step: Step | null = v && v.cats.length
    ? { k: 'hv', street: v.street, cats: [...v.cats], label: `${STREET_NAME[v.street]}: ${shortList(v.cats, 3)}` }
    : null;
  return filterChanged(chain, index, (s) => ({ ...s, lower: withLower(s.lower, 'hv', step) }));
}

export function setUpperTab(chain: ReportChain, index: number, upperTab: UpperTab): ReportChain {
  return patch(chain, index, (s) => (s.upperTab === upperTab ? s : { ...s, upperTab }));
}

export function setLowerTab(chain: ReportChain, index: number, tab: LowerTab): ReportChain {
  return patch(chain, index, (s) => (s.lowerTab === tab || !s.lowerTabs.includes(tab) ? s : { ...s, lowerTab: tab }));
}

/** "+" picker: select `tab` if the page has it, else append and select it. */
export function addLowerTab(chain: ReportChain, index: number, tab: LowerTab): ReportChain {
  return patch(chain, index, (s) => ({
    ...s,
    lowerTabs: s.lowerTabs.includes(tab) ? s.lowerTabs : [...s.lowerTabs, tab],
    lowerTab: tab,
  }));
}

/** Remove a lower tab (never Hands). If it held the row selection, the pages to the right close. */
export function removeLowerTab(chain: ReportChain, index: number, tab: LowerTab): ReportChain {
  const page = chain.pages[index];
  if (!page || tab === 'hands' || !page.state.lowerTabs.includes(tab)) return chain;
  const heldSelection = page.state.selectedRow?.tab === tab;
  const c = patch(chain, index, (s) => ({
    ...s,
    lowerTabs: s.lowerTabs.filter((t) => t !== tab),
    lowerTab: s.lowerTab === tab ? 'hands' : s.lowerTab,
    selectedRow: heldSelection ? null : s.selectedRow,
  }));
  return heldSelection ? truncateAfter(c, index) : c;
}

/** Gear > Close Pages (also used when the dashboard player changes). */
export function closeAllPages(chain: ReportChain): ReportChain {
  return clearSelection(truncateAfter(chain, 0), 0);
}

/** Gear > Reset Filter: page 0 loses its chips, range selections and selection; pages 1+ close. */
export function resetPage0(chain: ReportChain): ReportChain {
  return filterChanged(chain, 0, (s) => ({ ...s, own: [], lower: [] }));
}

/** Old `?tab=` links (`/graph`, `/range`, `/hands` redirects): pick the matching tab on page 0. */
export function applyLegacyTab(chain: ReportChain, tab: 'graph' | 'range' | 'hands'): ReportChain {
  if (tab === 'hands') return setLowerTab(chain, 0, 'hands');
  return setUpperTab(chain, 0, tab);
}

// ── Steps: validation and fallback labels ───────────────────────────────────────────────────

const POSITIONS = new Set(['EP', 'MP', 'CO', 'BTN', 'SB', 'BB']);
const STREETS = new Set(['preflop', 'flop', 'turn', 'river']);

const isStrArr = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === 'string');
const isNumArr = (v: unknown): v is number[] => Array.isArray(v) && v.every((x) => typeof x === 'number' && Number.isFinite(x));
const isStr = (v: unknown): v is string => typeof v === 'string';
const optStr = (v: unknown) => v === undefined || typeof v === 'string';

/** Structural check of a stored step (unknown kinds and malformed fields are rejected). */
export function isStep(x: unknown): x is Step {
  if (!x || typeof x !== 'object') return false;
  const s = x as Record<string, unknown>;
  if (!optStr(s.label)) return false;
  switch (s.k) {
    case 'pos': return isStrArr(s.v) && s.v.every((p) => POSITIONS.has(p));
    case 'stakes': return isStrArr(s.v);
    case 'mode': return s.v === 'fast' || s.v === 'regular';
    case 'tsize': return isNumArr(s.v);
    case 'date': return optStr(s.from) && optStr(s.to);
    case 'hour': return isNumArr(s.v);
    case 'stack': return typeof s.lo === 'number' && (s.hi === null || typeof s.hi === 'number');
    case 'game': return isStr(s.stakes) && isStr(s.mode) && typeof s.tsize === 'number';
    case 'cells': return isStrArr(s.v);
    case 'hv': return isStr(s.street) && STREETS.has(s.street) && isStrArr(s.cats);
    case 'row': return isStr(s.key);
    case 'next':
    case 'faced': return isStr(s.street) && STREETS.has(s.street) && isStr(s.a);
    case 'betsize': return isStr(s.bucket);
    default: return false;
  }
}

/** Chip text when the step has no `label` (labels normally come from the dialog or the backend). */
export function stepLabel(step: Step): string {
  if (step.label) return step.label;
  switch (step.k) {
    case 'pos': return step.v.join(', ');
    case 'stakes': return step.v.join(', ');
    case 'mode': return step.v === 'fast' ? 'Fast-fold' : 'Regular';
    case 'tsize': return step.v.map((n) => `${n}-max`).join(', ');
    case 'date': return [step.from ?? '…', step.to ?? '…'].join(' – ');
    case 'hour': return `Hours ${step.v.join(', ')}`;
    case 'stack': return step.hi === null ? `${step.lo}+ bb` : `${step.lo}–${step.hi} bb`;
    case 'game': return `${step.stakes} ${step.tsize}-max`;
    case 'cells': return shortList(step.v);
    case 'hv': return `${step.street}: ${shortList(step.cats, 3)}`;
    case 'row': return step.key;
    case 'next':
    case 'faced': return `${step.a.replace(/_/g, ' ')}, ${step.street}`;
    case 'betsize': return step.bucket;
    case 'session': return `Session ${step.start.slice(0, 16).replace('T', ' ')}`;
    case 'table': return shortList(step.v);
    case 'with': return `With player ${step.player_id}`;
  }
}

export type FilterDialogTab = 'quick' | 'positions' | 'general' | 'session';

/** Filter-dialog tab a chip reopens on (double-click). */
export function filterTabFor(step: Step): FilterDialogTab {
  switch (step.k) {
    case 'row': return 'quick';
    case 'pos': return 'positions';
    case 'date':
    case 'hour': return 'session';
    default: return 'general';
  }
}

// ── Persistence ─────────────────────────────────────────────────────────────────────────────

export const CHAIN_STORAGE_VERSION = 1;

export function chainStorageKey(workspaceId: number): string {
  return `ohm.reports.chain.${workspaceId}`;
}

export interface StoredPlayer { id: number; username: string; site: string }

interface StoredPage {
  title: string;
  inherited: Step[];
  own: Step[];
  lower: Step[];
  upperTab: UpperTab;
  lowerTabs: LowerTab[];
  lowerTab: LowerTab;
  selectedRow: SelectedRow | null;
  openedFrom: LowerTab;
}

interface StoredChain {
  v: number;
  player: StoredPlayer | null;
  pages: StoredPage[];
}

/** JSON for localStorage: pages without widths, ids or revs. */
export function serializeChain(chain: ReportChain, player: StoredPlayer | null): string {
  const out: StoredChain = {
    v: CHAIN_STORAGE_VERSION,
    player,
    pages: chain.pages.map((p) => ({
      title: p.title,
      inherited: p.inherited,
      own: p.state.own,
      lower: p.state.lower,
      upperTab: p.state.upperTab,
      lowerTabs: p.state.lowerTabs,
      lowerTab: p.state.lowerTab,
      selectedRow: p.state.selectedRow,
      openedFrom: p.state.openedFrom,
    })),
  };
  return JSON.stringify(out);
}

function parsePlayer(v: unknown): StoredPlayer | null {
  if (!v || typeof v !== 'object') return null;
  const p = v as Record<string, unknown>;
  return typeof p.id === 'number' && isStr(p.username) && isStr(p.site)
    ? { id: p.id, username: p.username, site: p.site }
    : null;
}

function parseSelected(v: unknown): SelectedRow | null {
  if (!v || typeof v !== 'object') return null;
  const r = v as Record<string, unknown>;
  return (r.tab === 'stats' || isLowerTab(r.tab)) && isStr(r.key) ? { tab: r.tab, key: r.key } : null;
}

const stepsOrNull = (v: unknown): Step[] | null => (Array.isArray(v) && v.every(isStep) ? v : null);
const validSteps = (v: unknown): Step[] => (Array.isArray(v) ? v.filter(isStep) : []);

/**
 * Restore a stored chain. Returns null (caller starts fresh) on a version mismatch or bad JSON.
 * Own/lower steps of unknown kinds are dropped; a page whose inherited chain is not fully valid
 * is dropped together with every page after it (its numbers would no longer match its title).
 */
export function parseStoredChain(raw: string | null | undefined, now: Date = new Date()): { chain: ReportChain; player: StoredPlayer | null } | null {
  if (!raw) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;
  if (d.v !== CHAIN_STORAGE_VERSION || !Array.isArray(d.pages) || d.pages.length === 0) return null;

  const pages: { title: string; inherited: Step[]; state: ReportPageState }[] = [];
  for (const [i, raw] of (d.pages as unknown[]).entries()) {
    if (!raw || typeof raw !== 'object') break;
    const p = raw as Record<string, unknown>;
    const storedInherited = i === 0 ? [] : stepsOrNull(p.inherited);
    if (!storedInherited) break;
    const inherited = resolvePresets(storedInherited, now);
    const lowerTabs = normalizeTabs(Array.isArray(p.lowerTabs) ? p.lowerTabs : DEFAULT_LOWER_TABS);
    const lowerTab = isLowerTab(p.lowerTab) && lowerTabs.includes(p.lowerTab) ? p.lowerTab : 'hands';
    pages.push({
      title: i === 0 ? PAGE0_TITLE : isStr(p.title) ? p.title : 'Page',
      inherited,
      state: {
        own: resolvePresets(validSteps(p.own), now),
        lower: validSteps(p.lower).filter((s) => s.k === 'cells' || s.k === 'hv'),
        upperTab: isUpperTab(p.upperTab) ? p.upperTab : 'stats',
        lowerTabs,
        lowerTab,
        selectedRow: parseSelected(p.selectedRow),
        openedFrom: isLowerTab(p.openedFrom) ? p.openedFrom : 'hands',
      },
    });
  }
  if (pages.length === 0) return null;
  // The last page has nothing open to its right: no selection to show
  pages[pages.length - 1].state.selectedRow = null;

  let chain = createChain(pages[0]);
  for (let i = 1; i < pages.length; i++) chain = openNext(chain, i - 1, pages[i]);
  return { chain, player: parsePlayer(d.player) };
}
