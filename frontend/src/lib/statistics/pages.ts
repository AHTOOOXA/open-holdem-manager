/**
 * Pages of a Statistics dashboard: page 0 (the profile grid or, for a single-stat dashboard, the
 * stat detail) and the drill-down pages to its right. Rule (unlike Reports): a click on page k
 * closes everything after k and appends a new page, never reusing one; closing page k clears the
 * selection on page k-1. Pages and selections live in memory per dashboard (`pagesStore`), so
 * switching dashboards in the tree restores the drill-down. Pure, no React.
 */
import type { HandsSelection } from '../api-general';
import { GENERAL_CELLS } from '../h2n-layout';
import type { GeneralCellMeta } from '../h2n-layout';
import { closeFrom, createChain, openFresh, setPageState, truncateAfter } from '../page-chain';
import type { NewPage, PageChain } from '../page-chain';
import type { SplitRow, Step } from '../reports/types';
import { statLabel } from './definition';

export type StatPage =
  /** Page 0; what it shows follows the dashboard's profile id. */
  | { kind: 'root' }
  /** Stat detail of an action cell. */
  | { kind: 'stat'; cellId: string }
  /** The stat's hands for a Range / Boards / Bet Sizes selection (General hands list). */
  | { kind: 'cell_hands'; cellId: string; selection: HandsSelection }
  /** Hands of a Reports chain (13x13 grid cell, Next Actions row). */
  | { kind: 'chain_hands'; chain: Step[] };

export type PageSelection =
  | { t: 'cell'; id: string } // a General grid cell
  | { t: 'hands'; sel: HandsSelection } // Range category / board / bet size
  | { t: 'range'; cells: string[] } // 13x13 grid classes
  | { t: 'next'; key: string }; // Next Actions row

export interface PageState {
  selection: PageSelection | null;
}

export type StatChain = PageChain<StatPage, PageState>;

export const ROOT_PAGE_WIDTH = 700;
export const STAT_PAGE_WIDTH = 560;
export const HANDS_PAGE_WIDTH = 820;

const EMPTY: PageState = { selection: null };

/** A chain with page 0 only; `rootWidth` = its width while pages are open to its right. */
export function freshStatChain(rootWidth = ROOT_PAGE_WIDTH): StatChain {
  return createChain<StatPage, PageState>({ title: 'Dashboard', inherited: { kind: 'root' }, state: EMPTY, width: rootWidth });
}

/** Select something on page `index` and open `page` right of it (everything after `index` closes). */
export function openFromPage(chain: StatChain, index: number, selection: PageSelection, page: NewPage<StatPage, PageState>): StatChain {
  if (!chain.pages[index]) return chain;
  return openFresh(setPageState(chain, index, { selection }), index, page);
}

/** Select without opening anything (expression cells only highlight); pages after `index` close. */
export function selectOnly(chain: StatChain, index: number, selection: PageSelection | null): StatChain {
  if (!chain.pages[index]) return chain;
  return truncateAfter(setPageState(chain, index, { selection }), index);
}

/** Close page `index` and everything right of it; the new last page loses its selection. */
export function closePages(chain: StatChain, index: number): StatChain {
  const closed = closeFrom(chain, index);
  if (closed === chain) return chain;
  return setPageState(closed, index - 1, EMPTY);
}

export function selectionOf(chain: StatChain, index: number): PageSelection | null {
  return chain.pages[index]?.state.selection ?? null;
}

// ── New pages ───────────────────────────────────────────────────────────────────────────────

export function statPage(cellId: string): NewPage<StatPage, PageState> {
  const meta = GENERAL_CELLS[cellId];
  return { title: meta ? statLabel(meta) : cellId, inherited: { kind: 'stat', cellId }, state: EMPTY, width: STAT_PAGE_WIDTH };
}

export function cellHandsPage(cellId: string, selection: HandsSelection): NewPage<StatPage, PageState> {
  return { title: selection.label, inherited: { kind: 'cell_hands', cellId, selection }, state: EMPTY, width: HANDS_PAGE_WIDTH };
}

/** The cell's chain with its spot step named after the stat (the backend labels it with the matcher notation). */
export function labelDetailChain(chain: readonly Step[], meta: GeneralCellMeta | undefined): Step[] {
  if (!meta) return [...chain];
  return chain.map((s) => (s.k === 'row' ? { ...s, label: statLabel(meta) } : s));
}

/** Hands of 13x13 grid classes: the cell's chain + a `cells` step. */
export function rangeHandsPage(detailChain: readonly Step[], cells: string[]): NewPage<StatPage, PageState> {
  const label = cells.join(', ');
  return {
    title: label,
    inherited: { kind: 'chain_hands', chain: [...detailChain, { k: 'cells', v: [...cells], label }] },
    state: EMPTY,
    width: HANDS_PAGE_WIDTH,
  };
}

/** Hands of a Next Actions row: the cell's chain + the row's filter; titled with the row caption. */
export function nextActionHandsPage(detailChain: readonly Step[], row: Pick<SplitRow, 'caption' | 'filter'>): NewPage<StatPage, PageState> {
  return {
    title: row.caption,
    inherited: { kind: 'chain_hands', chain: [...detailChain, { ...row.filter, label: row.filter.label ?? row.caption } as Step] },
    state: EMPTY,
    width: HANDS_PAGE_WIDTH,
  };
}

// ── In-memory store per dashboard ───────────────────────────────────────────────────────────

export interface StoredPages {
  /** definitionKey the pages were built for; a different definition starts over. */
  defKey: string;
  chain: StatChain;
}

const store = new Map<string, StoredPages>();

export const pagesStoreKey = (workspaceId: number, dashboardId: number) => `${workspaceId}:${dashboardId}`;

export function loadPages(key: string, defKey: string, rootWidth = ROOT_PAGE_WIDTH): StoredPages {
  const s = store.get(key);
  return s && s.defKey === defKey ? s : { defKey, chain: freshStatChain(rootWidth) };
}

export function savePages(key: string, pages: StoredPages): void {
  store.set(key, pages);
}

/** Test hook. */
export function clearPagesStore(): void {
  store.clear();
}
