/**
 * Pure state model for a Hand2Note-style chain of pages (Reports, Statistics,
 * Sessions). Page k+1 is opened by clicking a row on page k and is filtered by
 * that click. Widths live in memory only.
 *
 * Page<I, S>:
 *  - id         stable slot id (kept when a slot is reused)
 *  - title      shown in the header chip (pages 1+)
 *  - inherited  filter inherited from the left page's click (replaced on reuse)
 *  - state      caller-owned per-page UI state (kept on reuse)
 *  - width      px, used by every page except the last
 *  - rev        bumped each time the page is (re)opened; drives focus handling
 */
import { useCallback, useMemo, useReducer } from 'react';

export const DEFAULT_PAGE_WIDTH = 820;
export const LAST_PAGE_BASE_WIDTH = 1000;
export const MIN_PAGE_WIDTH = 20;
export const KEY_STEP = 16;
export const KEY_STEP_LARGE = 64;
export const LEVEL_COUNT = 3;

export interface Page<I, S> {
  id: number;
  title: string;
  inherited: I;
  state: S;
  width: number;
  rev: number;
}

export interface PageChain<I, S> {
  pages: Page<I, S>[];
  nextId: number;
}

export interface NewPage<I, S> {
  title: string;
  inherited: I;
  state: S;
  width?: number;
}

export function clampWidth(px: number): number {
  return Math.max(MIN_PAGE_WIDTH, Math.round(px));
}

function make<I, S>(chain: PageChain<I, S>, p: NewPage<I, S>): Page<I, S> {
  return {
    id: chain.nextId,
    title: p.title,
    inherited: p.inherited,
    state: p.state,
    width: clampWidth(p.width ?? DEFAULT_PAGE_WIDTH),
    rev: 0,
  };
}

export function createChain<I, S>(first: NewPage<I, S>): PageChain<I, S> {
  const empty: PageChain<I, S> = { pages: [], nextId: 1 };
  return { pages: [make(empty, first)], nextId: 2 };
}

/** Open the page right of `fromIndex`: append if last, else reuse the slot and drop the rest. */
export function openNext<I, S>(
  chain: PageChain<I, S>,
  fromIndex: number,
  page: NewPage<I, S>,
): PageChain<I, S> {
  if (fromIndex < 0 || fromIndex >= chain.pages.length) return chain;
  const next = fromIndex + 1;
  if (next >= chain.pages.length) {
    return { pages: [...chain.pages, make(chain, page)], nextId: chain.nextId + 1 };
  }
  const slot = chain.pages[next];
  const reused: Page<I, S> = {
    ...slot,
    title: page.title,
    inherited: page.inherited,
    rev: slot.rev + 1,
  };
  return { ...chain, pages: [...chain.pages.slice(0, next), reused] };
}

/**
 * Statistics rule: close every page right of `fromIndex`, then append a brand-new page (new id,
 * fresh state). Unlike `openNext`, an existing next page is never reused.
 */
export function openFresh<I, S>(
  chain: PageChain<I, S>,
  fromIndex: number,
  page: NewPage<I, S>,
): PageChain<I, S> {
  if (fromIndex < 0 || fromIndex >= chain.pages.length) return chain;
  return { pages: [...chain.pages.slice(0, fromIndex + 1), make(chain, page)], nextId: chain.nextId + 1 };
}

/** Close page `index` and every page to its right. Page 0 can't be closed. */
export function closeFrom<I, S>(chain: PageChain<I, S>, index: number): PageChain<I, S> {
  if (index < 1 || index >= chain.pages.length) return chain;
  return { ...chain, pages: chain.pages.slice(0, index) };
}

/** Drop everything right of `index` (page `index`'s own filter changed). */
export function truncateAfter<I, S>(chain: PageChain<I, S>, index: number): PageChain<I, S> {
  if (index < 0 || index >= chain.pages.length - 1) return chain;
  return { ...chain, pages: chain.pages.slice(0, index + 1) };
}

export function setWidth<I, S>(chain: PageChain<I, S>, index: number, px: number): PageChain<I, S> {
  const page = chain.pages[index];
  if (!page) return chain;
  const width = clampWidth(px);
  if (page.width === width) return chain;
  return { ...chain, pages: chain.pages.map((p, i) => (i === index ? { ...p, width } : p)) };
}

/** Replace the caller-owned state of page `index`. */
export function setPageState<I, S>(chain: PageChain<I, S>, index: number, state: S): PageChain<I, S> {
  const page = chain.pages[index];
  if (!page) return chain;
  return { ...chain, pages: chain.pages.map((p, i) => (i === index ? { ...p, state } : p)) };
}

/** Background level of page i's upper area (its lower block uses the next level). */
/** Id of the page that should take focus when page `index` closes: its left neighbour (null for page 0). */
export function leftNeighbourId<I, S>(pages: readonly Page<I, S>[], index: number): number | null {
  if (index < 1 || index >= pages.length) return null;
  return pages[index - 1]?.id ?? null;
}

export function levelOf(index: number): { upper: number; lower: number } {
  const upper = ((index % LEVEL_COUNT) + LEVEL_COUNT) % LEVEL_COUNT;
  return { upper, lower: (upper + 1) % LEVEL_COUNT };
}

type Action<I, S> =
  | { type: 'open'; from: number; page: NewPage<I, S> }
  | { type: 'close'; index: number }
  | { type: 'truncate'; index: number }
  | { type: 'width'; index: number; px: number }
  | { type: 'state'; index: number; state: S };

function reducer<I, S>(chain: PageChain<I, S>, a: Action<I, S>): PageChain<I, S> {
  switch (a.type) {
    case 'open': return openNext(chain, a.from, a.page);
    case 'close': return closeFrom(chain, a.index);
    case 'truncate': return truncateAfter(chain, a.index);
    case 'width': return setWidth(chain, a.index, a.px);
    case 'state': return setPageState(chain, a.index, a.state);
  }
}

export function usePageChain<I, S>(initial: NewPage<I, S>) {
  const [chain, dispatch] = useReducer(
    reducer as (c: PageChain<I, S>, a: Action<I, S>) => PageChain<I, S>,
    initial,
    createChain<I, S>,
  );
  const open = useCallback((from: number, page: NewPage<I, S>) => dispatch({ type: 'open', from, page }), []);
  const close = useCallback((index: number) => dispatch({ type: 'close', index }), []);
  const truncate = useCallback((index: number) => dispatch({ type: 'truncate', index }), []);
  const resize = useCallback((index: number, px: number) => dispatch({ type: 'width', index, px }), []);
  const setState = useCallback((index: number, state: S) => dispatch({ type: 'state', index, state }), []);
  return useMemo(
    () => ({ chain, pages: chain.pages, open, close, truncate, resize, setState }),
    [chain, open, close, truncate, resize, setState],
  );
}
