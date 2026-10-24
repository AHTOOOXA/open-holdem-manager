/** Typed client for /api/config/{section} and /api/system/info (contract in ./types.ts). */
import type { ConfigEnvelope, SystemInfo } from './types';

export type ConfigSection = 'stat_appearance' | 'game_types' | 'color_markers';

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
  return res.json();
}

export const configQueryKey = (section: ConfigSection) => ['config', section] as const;

export const getConfig = <T>(section: ConfigSection) => req<ConfigEnvelope<T>>(`/api/config/${section}`);
export const putConfig = <T>(section: ConfigSection, value: T) =>
  req<ConfigEnvelope<T>>(`/api/config/${section}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  });
export const resetConfig = <T>(section: ConfigSection) => req<ConfigEnvelope<T>>(`/api/config/${section}`, { method: 'DELETE' });

/** Reserve a never-reused colour marker id. */
export const getNextMarkerId = () => req<{ id: number }>('/api/config/color_markers/next-id');

export const systemInfoQueryKey = ['system', 'info'] as const;
export const getSystemInfo = () => req<SystemInfo>('/api/system/info');
