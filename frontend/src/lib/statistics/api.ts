/** Typed client for /api/statistics/dashboards (contract in ./types.ts). */
import type { DashboardsDoc } from './types';

export async function getDashboards(workspaceId: number): Promise<DashboardsDoc> {
  const res = await fetch(`/api/statistics/dashboards?workspace_id=${workspaceId}`);
  if (!res.ok) throw new Error(`Dashboards failed: ${res.statusText}`);
  return res.json();
}

export async function putDashboards(workspaceId: number, doc: DashboardsDoc): Promise<DashboardsDoc> {
  const res = await fetch(`/api/statistics/dashboards?workspace_id=${workspaceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      // not JSON
    }
    throw new Error(`Saving dashboards failed: ${detail}`);
  }
  return res.json();
}

export const dashboardsQueryKey = (workspaceId: number) => ['statistics', 'dashboards', workspaceId] as const;
