/** Typed client for /api/sessions (contract in ./types.ts). */
import { responseError } from '../api-error';
import type { SessionsLive, SessionsQuery, SessionsResponse } from './types';

export async function getSessions(q: SessionsQuery, signal?: AbortSignal): Promise<SessionsResponse> {
  const sp = new URLSearchParams({ workspace_id: String(q.workspace_id) });
  if (q.player_id !== undefined) sp.set('player_id', String(q.player_id));
  if (q.date_from) sp.set('date_from', q.date_from);
  if (q.date_to) sp.set('date_to', q.date_to);
  const res = await fetch(`/api/sessions?${sp}`, { signal });
  if (!res.ok) throw await responseError(res, 'Sessions failed');
  return res.json();
}

export async function getSessionsLive(workspaceId: number, signal?: AbortSignal): Promise<SessionsLive> {
  const res = await fetch(`/api/sessions/live?workspace_id=${workspaceId}`, { signal });
  if (!res.ok) throw new Error(`Live session check failed: ${res.statusText}`);
  return res.json();
}

export const sessionsQueryKey = (q: SessionsQuery) => ['sessions', q] as const;
export const sessionsLiveQueryKey = (workspaceId: number) => ['sessions', 'live', workspaceId] as const;
