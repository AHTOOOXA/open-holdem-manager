/**
 * Pure helpers behind DataGrid: sort cycling, keyboard index math, summary pinning,
 * selection, persisted column preferences, scroll-into-view math and infinite loading.
 * No React, no DOM: unit-tested in tests/data-grid.test.ts.
 */

export interface SortEntry {
  id: string;
  desc: boolean;
}
export type GridSorting = SortEntry[];

/**
 * Header click. A new column starts descending when `descFirst` (numeric columns by default),
 * ascending otherwise; clicking the sorted column again flips it. Single-column sort, never
 * cleared by clicking.
 */
export function nextSorting(current: GridSorting, columnId: string, descFirst: boolean): GridSorting {
  const head = current[0];
  if (head && head.id === columnId) return [{ id: columnId, desc: !head.desc }];
  return [{ id: columnId, desc: descFirst }];
}

export function sortDirection(sorting: GridSorting, columnId: string): 'asc' | 'desc' | false {
  const entry = sorting.find((s) => s.id === columnId);
  if (!entry) return false;
  return entry.desc ? 'desc' : 'asc';
}

export function ariaSortValue(dir: 'asc' | 'desc' | false): 'ascending' | 'descending' | 'none' {
  return dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none';
}

/**
 * Keyboard row navigation. Returns the next active index, or null when the key does not move
 * the active row. `current` -1 means no active row yet: any movement key lands on a row
 * (Up/PageUp/Home go to the first, Down/PageDown to the first, End to the last).
 */
export function nextRowIndex(key: string, current: number, count: number, pageSize: number): number | null {
  if (count <= 0) return null;
  const last = count - 1;
  const page = Math.max(1, Math.floor(pageSize));
  const from = current < 0 || current > last ? -1 : current;
  switch (key) {
    case 'ArrowDown':
      return from < 0 ? 0 : Math.min(last, from + 1);
    case 'ArrowUp':
      return from < 0 ? 0 : Math.max(0, from - 1);
    case 'PageDown':
      return from < 0 ? 0 : Math.min(last, from + page);
    case 'PageUp':
      return from < 0 ? 0 : Math.max(0, from - page);
    case 'Home':
      return 0;
    case 'End':
      return last;
    default:
      return null;
  }
}

/** Rows that fit in the visible body (one row of overlap kept, at least 1). */
export function rowsPerPage(viewportHeight: number, headerHeight: number, rowHeight: number): number {
  if (!(rowHeight > 0)) return 1;
  const body = viewportHeight - headerHeight;
  return Math.max(1, Math.floor(body / rowHeight) - 1);
}

/**
 * Summary pinning: the summary row (by id) is taken out of the body rows wherever sorting put it
 * and returned separately, so it always renders last.
 */
export function pinSummaryLast<R extends { id: string }>(
  rows: readonly R[],
  summaryId: string | null,
): { body: R[]; summary: R | null } {
  if (summaryId == null) return { body: rows.slice(), summary: null };
  let summary: R | null = null;
  const body: R[] = [];
  for (const r of rows) {
    if (r.id === summaryId && summary === null) summary = r;
    else body.push(r);
  }
  return { body, summary };
}

/**
 * Separate a summary row that callers keep inside `data` (flagged by `isSummary`) from the body
 * data. An explicit `summary` wins over a flagged row.
 */
export function splitSummary<T>(
  data: readonly T[],
  summary: T | null | undefined,
  isSummary?: (row: T) => boolean,
): { rows: T[]; summary: T | null } {
  if (!isSummary) return { rows: data.slice(), summary: summary ?? null };
  const rows: T[] = [];
  let found: T | null = null;
  for (const r of data) {
    if (isSummary(r)) {
      if (found === null) found = r;
    } else rows.push(r);
  }
  return { rows, summary: summary ?? found };
}

export type SelectionMode = 'none' | 'single' | 'multi';

export interface SelectionChange {
  mode: SelectionMode;
  /** Currently selected ids. */
  current: readonly string[];
  /** Anchor for shift ranges (last plainly clicked / toggled row). */
  anchor: string | null;
  /** Row being clicked / toggled. */
  target: string;
  /** Active (keyboard) row: the range anchor when no anchor exists yet. */
  activeId?: string | null;
  /** Row ids in display order (for ranges). */
  order: readonly string[];
  /** Shift held: select the range anchor..target. */
  range?: boolean;
  /** Ctrl/Cmd held, Space, or checkbox: toggle target only. */
  toggle?: boolean;
}

/** Next selection after a click / Space / checkbox on `target`. */
export function computeSelection(c: SelectionChange): { ids: string[]; anchor: string | null } {
  if (c.mode === 'none') return { ids: [], anchor: null };
  if (c.mode === 'single') return { ids: [c.target], anchor: c.target };
  const anchor = c.anchor ?? c.activeId ?? null;
  if (c.range && anchor != null) {
    const a = c.order.indexOf(anchor);
    const b = c.order.indexOf(c.target);
    if (a >= 0 && b >= 0) {
      const [lo, hi] = a <= b ? [a, b] : [b, a];
      const range = c.order.slice(lo, hi + 1);
      // Range replaces the selection unless toggling (Ctrl+Shift adds the range)
      const base = c.toggle ? c.current.filter((id) => !range.includes(id)) : [];
      return { ids: [...base, ...range], anchor };
    }
  }
  if (c.toggle) {
    const has = c.current.includes(c.target);
    return {
      ids: has ? c.current.filter((id) => id !== c.target) : [...c.current, c.target],
      anchor: c.target,
    };
  }
  return { ids: [c.target], anchor: c.target };
}

/**
 * Selection restricted to ids still present in `order` (same order as `selected`), or null when
 * nothing needs pruning.
 */
export function pruneSelection(selected: readonly string[], order: readonly string[]): string[] | null {
  if (selected.length === 0) return null;
  const present = new Set(order);
  const kept = selected.filter((id) => present.has(id));
  return kept.length === selected.length ? null : kept;
}

/** Header "select all" checkbox state. */
export function selectAllState(selected: readonly string[], order: readonly string[]): boolean | 'indeterminate' {
  if (order.length === 0) return false;
  const set = new Set(selected);
  let n = 0;
  for (const id of order) if (set.has(id)) n++;
  if (n === 0) return false;
  return n === order.length ? true : 'indeterminate';
}

// ── Persisted column preferences ────────────────────────────────────────────

export interface ColumnPrefSpec {
  id: string;
  /** May the user hide it (the first column never can). */
  hideable: boolean;
  minSize: number;
  maxSize: number;
}

export interface GridPrefs {
  /** Hidden column ids. */
  hidden: string[];
  /** User-set widths in px. */
  widths: Record<string, number>;
}

export const GRID_PREFS_VERSION = 1;
export const EMPTY_PREFS: GridPrefs = { hidden: [], widths: {} };

export function clampWidth(width: number, min: number, max: number): number {
  return Math.round(Math.min(Math.max(width, min), max));
}

/**
 * Parse stored prefs, keeping only what still applies: known columns, hideable ones in
 * `hidden`, finite widths clamped to the column's limits. Anything malformed yields empty prefs.
 */
/** Default-hidden ids that exist and may be hidden; never all columns. */
export function defaultHiddenFor(spec: readonly ColumnPrefSpec[], defaultHidden: readonly string[]): string[] {
  const byId = new Map(spec.map((s) => [s.id, s]));
  const out: string[] = [];
  for (const id of defaultHidden) {
    const s = byId.get(id);
    if (s && s.hideable && !out.includes(id)) out.push(id);
  }
  return spec.length > 0 && out.length >= spec.length ? [] : out;
}

export function parseGridPrefs(
  raw: string | null | undefined,
  spec: readonly ColumnPrefSpec[],
  /** Hidden columns used when nothing valid is stored (stored prefs always win, even if empty). */
  defaultHidden: readonly string[] = [],
): GridPrefs {
  const fallback = (): GridPrefs => ({ hidden: defaultHiddenFor(spec, defaultHidden), widths: {} });
  if (!raw) return fallback();
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return fallback();
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fallback();
  const obj = parsed as Record<string, unknown>;
  if (obj.v !== GRID_PREFS_VERSION) return fallback();
  const byId = new Map(spec.map((s) => [s.id, s]));
  const hidden: string[] = [];
  if (Array.isArray(obj.hidden)) {
    for (const id of obj.hidden) {
      if (typeof id !== 'string') continue;
      const s = byId.get(id);
      if (s && s.hideable && !hidden.includes(id)) hidden.push(id);
    }
  }
  const widths: Record<string, number> = {};
  if (obj.widths && typeof obj.widths === 'object' && !Array.isArray(obj.widths)) {
    for (const [id, w] of Object.entries(obj.widths as Record<string, unknown>)) {
      const s = byId.get(id);
      if (!s || typeof w !== 'number' || !Number.isFinite(w)) continue;
      widths[id] = clampWidth(w, s.minSize, s.maxSize);
    }
  }
  // Never hide every column
  if (spec.length > 0 && hidden.length >= spec.length) return { hidden: [], widths };
  return { hidden, widths };
}

export function serializeGridPrefs(prefs: GridPrefs): string {
  return JSON.stringify({ v: GRID_PREFS_VERSION, hidden: prefs.hidden, widths: prefs.widths });
}

/** TanStack visibility state from hidden ids (absent = visible). */
export function visibilityFromHidden(hidden: readonly string[]): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  for (const id of hidden) out[id] = false;
  return out;
}

/** Hidden ids from TanStack visibility state (only explicit `false` hides). */
export function hiddenFromVisibility(visibility: Record<string, boolean>): string[] {
  return Object.keys(visibility).filter((id) => visibility[id] === false);
}

/** Keyboard resize on a focused handle: Left/Right by `step` (Shift: `bigStep`). Null = not a resize key. */
export function resizeByKey(
  key: string,
  width: number,
  limits: { min: number; max: number },
  shift = false,
  step = 8,
  bigStep = 32,
): number | null {
  const d = shift ? bigStep : step;
  if (key === 'ArrowRight') return clampWidth(width + d, limits.min, limits.max);
  if (key === 'ArrowLeft') return clampWidth(width - d, limits.min, limits.max);
  if (key === 'Home') return clampWidth(limits.min, limits.min, limits.max);
  return null;
}

// ── Scrolling ───────────────────────────────────────────────────────────────

/**
 * New scrollTop that brings an item fully into view below a sticky header and above a sticky
 * footer, or null when it is already visible. `itemTop` is in content coordinates.
 */
export function revealScrollTop(p: {
  scrollTop: number;
  viewHeight: number;
  itemTop: number;
  itemHeight: number;
  headerHeight?: number;
  footerHeight?: number;
}): number | null {
  const head = p.headerHeight ?? 0;
  const foot = p.footerHeight ?? 0;
  const visibleTop = p.scrollTop + head;
  const visibleBottom = p.scrollTop + p.viewHeight - foot;
  if (p.itemTop < visibleTop) return Math.max(0, p.itemTop - head);
  if (p.itemTop + p.itemHeight > visibleBottom) {
    return Math.max(0, p.itemTop + p.itemHeight - p.viewHeight + foot);
  }
  return null;
}

/** Index of the row whose rendering triggers `onEndReached` (last `threshold` rows). */
export function endReachedIndex(count: number, threshold = 10): number {
  return Math.max(0, count - threshold);
}

/**
 * Fire `onEndReached` once per row count: when a row within the last `threshold` rows has
 * rendered, nothing is loading, and it has not fired for this count yet.
 */
export function shouldFireEndReached(p: {
  lastRenderedIndex: number;
  count: number;
  threshold?: number;
  firedForCount: number | null;
  loading?: boolean;
}): boolean {
  if (p.count <= 0 || p.loading) return false;
  if (p.firedForCount === p.count) return false;
  return p.lastRenderedIndex >= endReachedIndex(p.count, p.threshold ?? 10);
}

export interface EndReachedMarker {
  count: number;
  firstId: string | null;
}

/**
 * Keep the "already fired" marker only while the data is the same list growing: it is dropped
 * when the first row id changed (data replaced) or the row count shrank.
 */
export function resetEndReachedMarker(
  marker: EndReachedMarker | null,
  count: number,
  firstId: string | null,
): EndReachedMarker | null {
  if (!marker) return null;
  if (marker.firstId !== firstId || count < marker.count) return null;
  return marker;
}

export interface VirtualItemLike {
  index: number;
  start: number;
  end: number;
}

/** Indexes of rendered items overlapping the visible band (below the sticky header, above the footer). */
export function visibleIndexes(
  items: readonly VirtualItemLike[],
  scrollTop: number,
  viewHeight: number,
  headerHeight = 0,
  footerHeight = 0,
): number[] {
  const top = scrollTop + headerHeight;
  const bottom = scrollTop + viewHeight - footerHeight;
  return items.filter((v) => v.end > top && v.start < bottom).map((v) => v.index);
}

/**
 * The row that carries tabindex 0: the preferred one (active / selected / first) when it is
 * rendered and visible, else the first visible rendered row, else the first rendered row.
 * -1 when nothing is rendered.
 */
export function pickTabStop(preferred: number, rendered: readonly number[], visible: readonly number[]): number {
  if (visible.includes(preferred)) return preferred;
  if (visible.length > 0) return visible[0];
  if (rendered.includes(preferred)) return preferred;
  return rendered[0] ?? -1;
}

/** Virtualise when asked, or automatically past `autoThreshold` rows. */
export function shouldVirtualize(flag: boolean | 'auto' | undefined, rowCount: number, autoThreshold = 200): boolean {
  if (flag === true) return true;
  if (flag === false) return false;
  return rowCount > autoThreshold;
}
