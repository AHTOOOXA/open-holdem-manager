/** Typed client for tags + marked hands (contract in ./types.ts). */
import type { MarkBody, MarkState, MarkedImportResult, TagColor, TagDef } from './types';

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      // not JSON
    }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const tagDefsQueryKey = ['tag-defs'] as const;

export const getTagDefs = () => req<TagDef[]>('/api/tag-defs');
export const createTagDef = (body: { name?: string; color?: TagColor } = {}) => req<TagDef>('/api/tag-defs', json('POST', body));
export const updateTagDef = (id: number, body: { name?: string; color?: TagColor }) =>
  req<TagDef>(`/api/tag-defs/${id}`, json('PATCH', body));
export const deleteTagDef = (id: number) => req<void>(`/api/tag-defs/${id}`, { method: 'DELETE' });
export const moveTagDef = (id: number, direction: 'up' | 'down') =>
  req<TagDef[]>(`/api/tag-defs/${id}/move`, json('POST', { direction }));
export const resetTagDefs = () => req<TagDef[]>('/api/tag-defs/reset', { method: 'POST' });

export const markHand = (workspaceId: number, handId: string, body: MarkBody = {}, playerId?: number) =>
  req<MarkState>(
    `/api/hands/${encodeURIComponent(handId)}/mark?workspace_id=${workspaceId}${playerId !== undefined ? `&player_id=${playerId}` : ''}`,
    json('PUT', body),
  );
export const unmarkHand = (workspaceId: number, handId: string, playerId?: number) =>
  req<void>(
    `/api/hands/${encodeURIComponent(handId)}/mark?workspace_id=${workspaceId}${playerId !== undefined ? `&player_id=${playerId}` : ''}`,
    { method: 'DELETE' },
  );

export const unmarkAll = (workspaceId: number, tagIds?: number[]) =>
  req<{ unmarked: number }>(`/api/marked-hands/unmark?workspace_id=${workspaceId}`, json('POST', tagIds?.length ? { tag_ids: tagIds } : {}));

export function exportMarkedUrl(workspaceId: number, format: 'json' | 'txt', tagIds?: number[]): string {
  const sp = new URLSearchParams({ workspace_id: String(workspaceId), format });
  if (tagIds?.length) sp.set('tag_ids', tagIds.join(','));
  return `/api/marked-hands/export?${sp}`;
}

export function importMarked(workspaceId: number, files: File[]): Promise<MarkedImportResult> {
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  return req<MarkedImportResult>(`/api/marked-hands/import?workspace_id=${workspaceId}`, { method: 'POST', body: fd });
}
