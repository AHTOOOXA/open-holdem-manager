/** Typed client for the Reports endpoints (contract in ./types.ts). */
import type {
  HandStrengthQuery,
  HandStrengthResponse,
  PreflopRangeResponse,
  QuickFilter,
  ReportQuery,
  SplitQuery,
  SplitResponse,
  SpotResponse,
  Step,
} from './types';

const BASE = '/api/reports';

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      // not JSON
    }
    throw new Error(`Reports ${path} failed: ${detail}`);
  }
  return res.json();
}

export function getSplit(q: SplitQuery, signal?: AbortSignal): Promise<SplitResponse> {
  return post('/split', q, signal);
}

export function getSpot(q: ReportQuery, signal?: AbortSignal): Promise<SpotResponse> {
  return post('/spot', q, signal);
}

export function getPreflopRange(q: ReportQuery, signal?: AbortSignal): Promise<PreflopRangeResponse> {
  return post('/preflop-range', q, signal);
}

export function getHandStrength(q: HandStrengthQuery, signal?: AbortSignal): Promise<HandStrengthResponse> {
  return post('/hand-strength', q, signal);
}

export async function getQuickFilters(): Promise<QuickFilter[]> {
  const res = await fetch(`${BASE}/quick-filters`);
  if (!res.ok) throw new Error(`Quick filters failed: ${res.statusText}`);
  return res.json();
}

/** Query-string value for GET endpoints that accept the chain (`/api/hands`, `/api/reports/graph`). */
export function chainParam(chain: Step[]): string {
  return JSON.stringify(
    chain.map((step) => {
      const rest: Partial<Step> = { ...step };
      delete rest.label;
      return rest;
    }),
  );
}

/** Stable react-query key part for a query (labels don't change results). */
export function queryKeyOf(q: ReportQuery): string {
  return JSON.stringify([q.workspace_id, q.player_id ?? null, chainParam(q.chain)]);
}
