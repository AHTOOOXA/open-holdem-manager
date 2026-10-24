/** Pure page-type and tab rules of the Sessions dashboard (sessions.md §5). */
import type { SpotRecipe, SplitRow, Step } from '../reports/types';
import type { SessionRow } from './types';

/** What a page is about: the session (page 0), one table, or one opponent. */
export type SessionPageKind = 'session' | 'table' | 'villain';
export type SessionTab = 'hands' | 'tables' | 'players';

/** What a page inherits from the row that opened it. */
export interface PageScope {
  kind: SessionPageKind;
  /** Full chain of the page (session step first). */
  chain: Step[];
  /** Player the page reports on; undefined = the dashboard's player. */
  playerId?: number;
}

export interface SessionPageState {
  tab: SessionTab;
  /** Key of the row selected in this page's Tables / Players tab (it opened the next page). */
  selectedKey: string | null;
}

/** Fixed lower tabs, Hands first. A Players page has no more drill-down. */
export function tabsFor(kind: SessionPageKind): SessionTab[] {
  if (kind === 'session') return ['hands', 'tables', 'players'];
  if (kind === 'table') return ['hands', 'players'];
  return ['hands'];
}

export const TAB_CAPTION: Record<SessionTab, string> = { hands: 'Hands', tables: 'Tables', players: 'Players' };

/** The Stats recipe a page uses (the recipe is named after the kind). */
export function recipeFor(kind: SessionPageKind): SpotRecipe {
  return kind;
}

/** The kind of page a row of this tab opens. */
export function kindOpenedBy(tab: Exclude<SessionTab, 'hands'>): SessionPageKind {
  return tab === 'tables' ? 'table' : 'villain';
}

export function freshPageState(): SessionPageState {
  return { tab: 'hands', selectedKey: null };
}

export function isSessionTab(v: unknown, kind: SessionPageKind): v is SessionTab {
  return typeof v === 'string' && (tabsFor(kind) as string[]).includes(v);
}

/** Page 0: only the session step (the date filter is not part of the chain). */
export function sessionScope(row: SessionRow): PageScope {
  return { kind: 'session', chain: [row.filter] };
}

/**
 * Scope of the page a Tables / Players row opens: parent chain + the row's step. A Players row
 * switches the reported player to the opponent (null when the row carries no player).
 */
export function childScope(parent: PageScope, tab: Exclude<SessionTab, 'hands'>, row: SplitRow): PageScope | null {
  const chain = [...parent.chain, row.filter];
  if (tab === 'tables') return { kind: 'table', chain, playerId: parent.playerId };
  if (!row.player) return null;
  return { kind: 'villain', chain, playerId: row.player.id };
}

/**
 * The session to show: the one with `preferredId`, else the newest (largest start). An id that
 * matches nothing (old numeric-index links, a session outside the date range) falls back to newest.
 */
export function pickSession<T extends { id: number; start: string }>(rows: readonly T[], preferredId: number | null): T | null {
  if (rows.length === 0) return null;
  const preferred = preferredId === null ? undefined : rows.find((r) => r.id === preferredId);
  if (preferred) return preferred;
  return rows.reduce((a, b) => (b.start > a.start ? b : a));
}

/** `/sessions/:param` → session id, or null for anything that is not a positive integer. */
export function parseSessionParam(param: string | undefined): number | null {
  if (!param || !/^\d+$/.test(param)) return null;
  const n = Number(param);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}
