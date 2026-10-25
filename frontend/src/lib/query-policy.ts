/**
 * What refetches when hand data changes (import, auto-import tick, rebuild, clear).
 *
 * Queries come in two weights:
 * - **cheap** (status, counts, workspaces, hero list, plain lists): refetched right away when visible.
 * - **heavy** (Reports spot / split / graph / range / strength, Statistics grid + popup, Extras
 *   aggregates, hand lists over a Reports chain): a cold request is a chain resolve or a replay
 *   that costs seconds at 200k hands. The backend extends its warm Reports resolutions and popup
 *   records with the new hands of an auto-import instead of recomputing them, so after a tick:
 *   - the visible heavy queries refetch once, shortly after the tick (ticks landing within
 *     `AUTO_REFRESH_DEBOUNCE_MS` share one refresh). A query that is already fetching is not
 *     cancelled and not fetched twice: it refetches once when that fetch lands;
 *   - heavy queries that are not showing are only marked stale and refetch once when they mount;
 *   - a visible query whose last automatic refresh took longer than `SLOW_REFRESH_MS` (the
 *     backend could not extend it) is not refreshed automatically any more: it keeps its numbers
 *     and gets the "New hands" refresh chip (`NewHandsIndicator`) until a refresh is fast again.
 *   A manual import, a rebuild or a clear still refetches the visible screen right away.
 *
 * Tag a heavy query with the meta flag, or spread the options helper (also sets the shorter cache
 * retention and no retry):
 *
 *     useQuery({ queryKey, queryFn: ({ signal }) => get(..., signal), ...HEAVY_QUERY })
 *
 * Until every heavy query is tagged, `HEAVY_KEY_PREFIXES` classifies the known heavy keys.
 *
 * Session pages (any key whose chain has a `{ k: 'session' }` step) follow the session list: their
 * chain's `end` moves when hands are added, so the key changes and they fetch once by themselves.
 * Data changes only mark them stale; `SessionsPage` refetches the ones whose row changed
 * (`sessionQueriesToRefetch`), so a live session is fetched once per tick, not twice.
 */
import type { Query, QueryClient, QueryKey } from '@tanstack/react-query';

/** Query meta of heavy queries: `meta: HEAVY_META`. */
export const HEAVY_META = { heavy: true } as const;

/** Cache retention of heavy payloads after the screen is left (default queries: 10 min). */
export const HEAVY_GC_MS = 60_000;

/** Options to spread into a heavy `useQuery`: the meta flag, short retention, no retry. */
export const HEAVY_QUERY = { meta: HEAVY_META, gcTime: HEAVY_GC_MS, retry: 0 } as const;

/** Auto-import ticks landing within this window share one refresh of the visible heavy queries. */
export const AUTO_REFRESH_DEBOUNCE_MS = 300;

/** A visible heavy query whose automatic refresh took longer than this falls back to the chip. */
export const SLOW_REFRESH_MS = 4_000;

/** Key prefixes of heavy queries (matched element by element against the key's start). */
export const HEAVY_KEY_PREFIXES: readonly (readonly string[])[] = [
  ['reports', 'spot'],
  ['reports', 'split'],
  ['reports', 'graph'],
  ['reports', 'preflop-range'],
  ['reports', 'hand-strength'],
  ['general'], // Statistics: grid, stat popup, popup hand list
  ['graph'],
  ['range'],
  ['stats'],
  ['population'],
  ['compare'],
  ['cash-drop'],
  ['drift'],
  ['players', 'list'],
  ['players', 'stats'],
  ['players', 'h2h'],
  ['identities'],
];

/** Keys no hand import can change (settings, status poll, static lists): left alone on auto-import ticks. */
const STATIC_KEY_HEADS: ReadonlySet<string> = new Set([
  'auto-import', 'config', 'app-settings', 'sites', 'tag-defs', 'statistics',
]);

type QueryLike = Pick<Query, 'queryKey' | 'meta'>;

function startsWith(key: QueryKey, prefix: readonly string[]): boolean {
  return prefix.every((p, i) => key[i] === p);
}

/** A hand list over a Reports chain (an empty chain too: it resolves every hand) costs like a report. */
function isChainHandList(key: QueryKey): boolean {
  if (key[0] !== 'hands' || key[1] !== 'list') return false;
  const params = key[2];
  return typeof params === 'object' && params !== null && (params as { chain?: unknown }).chain !== undefined;
}

export function isHeavyQuery(q: QueryLike): boolean {
  if (q.meta?.heavy === true) return true;
  const key = q.queryKey;
  return HEAVY_KEY_PREFIXES.some((p) => startsWith(key, p)) || isChainHandList(key);
}

export function isStaticQuery(q: QueryLike): boolean {
  const head = q.queryKey[0];
  if (typeof head === 'string' && STATIC_KEY_HEADS.has(head)) return true;
  return q.queryKey[0] === 'reports' && q.queryKey[1] === 'quick-filters';
}

/** A Sessions `session` chain step as it appears in query keys. */
export interface SessionStepRef {
  start: string;
  end: string;
}

function collectSessionSteps(v: unknown, out: SessionStepRef[], depth: number): void {
  if (depth > 6 || v === null || v === undefined) return;
  if (typeof v === 'string') {
    // Report keys carry the chain as a JSON string (queryKeyOf / chainParam)
    if (v.includes('session') && (v.startsWith('[') || v.startsWith('{'))) {
      try {
        collectSessionSteps(JSON.parse(v), out, depth + 1);
      } catch {
        // not JSON
      }
    }
    return;
  }
  if (Array.isArray(v)) {
    for (const x of v) collectSessionSteps(x, out, depth + 1);
    return;
  }
  if (typeof v === 'object') {
    const o = v as Record<string, unknown>;
    if (o.k === 'session' && typeof o.start === 'string' && typeof o.end === 'string') {
      out.push({ start: o.start, end: o.end });
      return;
    }
    for (const x of Object.values(o)) collectSessionSteps(x, out, depth + 1);
  }
}

/** Session steps in a query key (empty for everything outside the Sessions pages). */
export function sessionStepsOf(key: QueryKey): SessionStepRef[] {
  const out: SessionStepRef[] = [];
  collectSessionSteps(key, out, 0);
  return out;
}

const sessionStepCache = new WeakMap<object, boolean>();

/** True for queries of a Sessions page (their chain starts with a session step). */
export function isSessionChainQuery(q: Pick<Query, 'queryKey'>): boolean {
  const key = q.queryKey as unknown as object;
  let hit = sessionStepCache.get(key);
  if (hit === undefined) {
    hit = sessionStepsOf(q.queryKey).length > 0;
    sessionStepCache.set(key, hit);
  }
  return hit;
}

export type DataChange =
  /** Auto-import added hands (every few seconds while playing). */
  | 'auto-import'
  /** A manual import finished: the visible screen must show the new hands. */
  | 'import'
  /** Stats rebuilt, database cleared or replaced: everything can differ, session windows included. */
  | 'all';

/**
 * Invalidate after hand data changed (policy in the header). Resolves once the workspace list is
 * fresh (hand counts drive the welcome view); everything else refetches in the background.
 */
export function refreshAfterDataChange(qc: QueryClient, change: DataChange): Promise<void> {
  const workspaces = qc.invalidateQueries({ queryKey: ['workspaces'] });
  const rest = (q: Query) => q.queryKey[0] !== 'workspaces';
  if (change === 'all') {
    void qc.invalidateQueries({ predicate: rest });
    return workspaces;
  }
  // Sessions pages: marked stale only, SessionsPage refetches what its new rows require
  void qc.invalidateQueries({ predicate: (q) => rest(q) && isSessionChainQuery(q), refetchType: 'none' });
  if (change === 'import') {
    void qc.invalidateQueries({ predicate: (q) => rest(q) && !isSessionChainQuery(q) });
    return workspaces;
  }
  const heavy = (q: Query) => rest(q) && !isSessionChainQuery(q) && !isStaticQuery(q) && isHeavyQuery(q);
  // A heavy fetch already running started before these hands arrived; its success would clear the
  // stale mark. Mark it again once it settles, so a remount (or the visible refresh) refetches it.
  keepStaleAfterFetch(qc, qc.getQueryCache().findAll({ predicate: (q) => heavy(q) && q.state.fetchStatus !== 'idle' }));
  // The visible ones refresh shortly (no chip meanwhile): mark them before they turn stale.
  for (const q of qc.getQueryCache().findAll({ predicate: (q) => heavy(q) && q.isActive() && !slowRefresh.has(q) })) {
    markAwaiting(qc, q);
  }
  void qc.invalidateQueries({ predicate: heavy, refetchType: 'none' });
  void qc.invalidateQueries({
    predicate: (q) => rest(q) && !isSessionChainQuery(q) && !isStaticQuery(q) && !isHeavyQuery(q),
  });
  scheduleVisibleRefresh(qc);
  return workspaces;
}

/** Heavy queries whose automatic refresh was slow: they get the chip instead. */
const slowRefresh = new WeakSet<Query>();
/** Visible heavy queries due for the pending automatic refresh (the chip stays hidden for them). */
const awaiting = new WeakSet<Query>();
const awaitingByClient = new WeakMap<QueryClient, Set<Query>>();
const refreshTimers = new WeakMap<QueryClient, ReturnType<typeof setTimeout>>();

function markAwaiting(qc: QueryClient, q: Query): void {
  let set = awaitingByClient.get(qc);
  if (!set) {
    set = new Set();
    awaitingByClient.set(qc, set);
  }
  set.add(q);
  awaiting.add(q);
}

/** One refresh of the visible outdated heavy queries, `AUTO_REFRESH_DEBOUNCE_MS` after the last call. */
function scheduleVisibleRefresh(qc: QueryClient): void {
  const prev = refreshTimers.get(qc);
  if (prev !== undefined) clearTimeout(prev);
  refreshTimers.set(
    qc,
    setTimeout(() => {
      refreshTimers.delete(qc);
      for (const q of awaitingByClient.get(qc) ?? []) awaiting.delete(q);
      awaitingByClient.delete(qc);
      const due = qc.getQueryCache().findAll({ predicate: (q) => isOutdatedOnScreen(q) && !slowRefresh.has(q) });
      void Promise.all(due.map((q) => timedRefetch(qc, q)));
    }, AUTO_REFRESH_DEBOUNCE_MS),
  );
}

/** Refetch one query (never cancelling a running fetch) and remember whether that was slow. */
async function timedRefetch(qc: QueryClient, q: Query): Promise<void> {
  const t0 = Date.now();
  await qc.refetchQueries({ predicate: (x) => x === q, type: 'active' }, { cancelRefetch: false });
  if (q.state.status !== 'success') return;
  if (Date.now() - t0 > SLOW_REFRESH_MS) slowRefresh.add(q);
  else slowRefresh.delete(q);
}

/**
 * Re-mark `queries` stale when their running fetch settles (a success clears `isInvalidated`, a
 * cancel restores the pre-fetch state), then refresh the visible ones once (not cancelled, not
 * asked twice: the running fetch belongs to whatever started it, the refresh to the tick).
 */
function keepStaleAfterFetch(qc: QueryClient, queries: Query[]): void {
  if (queries.length === 0) return;
  const pending = new Set(queries);
  const cache = qc.getQueryCache();
  const unsubscribe = cache.subscribe((event) => {
    const q = event.query;
    if (!pending.has(q)) return;
    if (event.type === 'removed') pending.delete(q);
    else if (event.type === 'updated' && q.state.fetchStatus === 'idle') {
      pending.delete(q);
      if (q.isActive() && !slowRefresh.has(q)) markAwaiting(qc, q);
      if (!q.state.isInvalidated) void qc.invalidateQueries({ queryKey: q.queryKey, exact: true, refetchType: 'none' });
      scheduleVisibleRefresh(qc);
    }
    if (pending.size === 0) unsubscribe();
  });
}

/**
 * Visible heavy queries that show data older than the last auto-import (invalidated, not
 * refetching, last fetch succeeded) and are not about to be refreshed automatically: the
 * "New hands" chip. Sessions pages follow their list instead.
 */
export function isOutdatedOnScreen(q: Query): boolean {
  return (
    q.state.isInvalidated &&
    q.state.fetchStatus === 'idle' &&
    q.state.status === 'success' &&
    q.isActive() &&
    isHeavyQuery(q) &&
    !isSessionChainQuery(q) &&
    !awaiting.has(q)
  );
}

/** Refetch what `isOutdatedOnScreen` reports (the "New hands" chip's Refresh). */
export function refetchOutdatedOnScreen(qc: QueryClient): Promise<void> {
  const due = qc.getQueryCache().findAll({ predicate: isOutdatedOnScreen });
  return Promise.all(due.map((q) => timedRefetch(qc, q))).then(() => undefined);
}

// ── Sessions pages ──────────────────────────────────────────────────────────────────────────────

/** The parts of a session row that change when its hands change. */
export interface SessionRowLike {
  filter: { k: string; start?: unknown; end?: unknown };
  hands: number;
  last_hand_at: string;
  won: number;
  won_bb: number;
  won_ev: number;
}

const fingerprint = (r: SessionRowLike) => `${r.hands}|${r.last_hand_at}|${String(r.filter.end)}|${r.won}|${r.won_bb}|${r.won_ev}`;

function rowsByStart(rows: readonly SessionRowLike[]): Map<string, SessionRowLike> {
  const m = new Map<string, SessionRowLike>();
  for (const r of rows) if (typeof r.filter.start === 'string') m.set(r.filter.start, r);
  return m;
}

export interface SessionRefetchPlan {
  refetch: Query[];
  /** Hidden page-0 queries of a window that moved on: nobody can show them again. */
  remove: Query[];
}

/**
 * After the session list returned new rows: which Sessions-page queries to refetch and which to
 * drop. A query is refetched when it is visible, was marked stale by a data change (or `force`,
 * the Refresh button) and the row of its session changed (or `force`).
 */
export function sessionQueriesToRefetch(
  queries: readonly Query[],
  prevRows: readonly SessionRowLike[] | null,
  rows: readonly SessionRowLike[],
  force = false,
): SessionRefetchPlan {
  const plan: SessionRefetchPlan = { refetch: [], remove: [] };
  const prev = prevRows ? rowsByStart(prevRows) : null;
  const cur = rowsByStart(rows);
  for (const q of queries) {
    if (!isSessionChainQuery(q)) continue;
    const steps = sessionStepsOf(q.queryKey);
    const step = steps[0];
    const row = step ? cur.get(step.start) : undefined;
    if (!step || !row) continue;
    const current = step.end === String(row.filter.end);
    if (!q.isActive()) {
      if (!current && q.getObserversCount() === 0) plan.remove.push(q);
      continue;
    }
    if (!q.state.isInvalidated || q.state.fetchStatus !== 'idle') continue;
    const before = prev?.get(step.start);
    const changed = before !== undefined && fingerprint(before) !== fingerprint(row);
    if (force || changed) plan.refetch.push(q);
  }
  return plan;
}
