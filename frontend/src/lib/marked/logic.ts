/** Pure helpers for the marked-hands UI (no React, unit-tested). */
import type { MarkState, TagDef, TagRef } from './types';

/** Tag checkbox grid: ten tags per column. */
export const TAGS_PER_COLUMN = 10;

export function gridColumnCount(n: number): number {
  return Math.max(1, Math.ceil(n / TAGS_PER_COLUMN));
}

/** Marked-hands filter used by the hand-list filter popover: any-of semantics. */
export type MarkedMode = '' | 'marked' | 'unmarked';

export interface MarkedFilter {
  mode: MarkedMode;
  tagIds: number[];
}

export const EMPTY_MARKED_FILTER: MarkedFilter = { mode: '', tagIds: [] };

/** Hand-list query params for a filter. Selected tags imply "marked" (and win over the mode). */
export function markedListParams(f: MarkedFilter): { marked?: boolean; tag_ids?: number[] } {
  if (f.tagIds.length > 0) return { tag_ids: [...f.tagIds] };
  if (f.mode === 'marked') return { marked: true };
  if (f.mode === 'unmarked') return { marked: false };
  return {};
}

export function isMarkedFilterActive(f: MarkedFilter): boolean {
  return f.mode !== '' || f.tagIds.length > 0;
}

export function toggleId(ids: readonly number[], id: number, on: boolean): number[] {
  const has = ids.includes(id);
  if (on) return has ? [...ids] : [...ids, id];
  return ids.filter((x) => x !== id);
}

/** Parse the `?tag=` URL param (single id or comma list); invalid parts are dropped. */
export function parseTagParam(raw: string | null | undefined): number[] {
  if (!raw) return [];
  const out: number[] = [];
  for (const part of raw.split(',')) {
    const n = Number(part.trim());
    if (Number.isInteger(n) && n > 0 && !out.includes(n)) out.push(n);
  }
  return out;
}

/** Drop ids that are no longer in the catalogue. */
export function pruneTagIds(ids: readonly number[], defs: readonly TagDef[]): number[] {
  const known = new Set(defs.map((d) => d.id));
  return ids.filter((i) => known.has(i));
}

/** Resolve ids to catalogue-ordered refs. */
export function tagRefsFor(ids: readonly number[], defs: readonly TagDef[]): TagRef[] {
  return defs
    .filter((d) => ids.includes(d.id))
    .sort((a, b) => a.position - b.position)
    .map(({ id, name, color }) => ({ id, name, color }));
}

/** Menu entries available for a hand (see MarkMenuItems). */
export function markMenuState(marked: boolean, tagCount: number): { mark: boolean; markWithTags: boolean; unmark: boolean } {
  return { mark: !marked, markWithTags: tagCount > 0, unmark: marked };
}

/** Row patch after a mark change (optimistic update). */
export function patchRow<T extends { id: string; marked: boolean; tags: TagRef[] }>(rows: readonly T[], state: Pick<MarkState, 'hand_id' | 'marked' | 'tags'>): T[] {
  return rows.map((r) => (r.id === state.hand_id ? { ...r, marked: state.marked, tags: state.tags } : r));
}

// Marked Hands page: tag filter kept in memory per workspace (not persisted).
const pageFilters = new Map<number, number[]>();
export const getPageTagFilter = (ws: number): number[] => pageFilters.get(ws) ?? [];
export const setPageTagFilter = (ws: number, ids: number[]): void => {
  pageFilters.set(ws, ids);
};
export function clearPageTagFilters(): void {
  pageFilters.clear();
}

/** "1 hand", "3 hands". */
export function countLabel(n: number, noun: string): string {
  return `${n.toLocaleString('en-US')} ${noun}${n === 1 ? '' : 's'}`;
}
