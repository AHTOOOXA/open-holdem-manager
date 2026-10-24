/** Import from another tracker's database: client + pure helpers (contract: ./types.ts §3). */
import type { TrackerConnection, TrackerDatabase, TrackerDatabases, TrackerSoftware } from './types';

export type ImportSoftware = 'h2n4' | TrackerSoftware;

export const SOFTWARE_OPTIONS: { id: ImportSoftware; label: string }[] = [
  { id: 'h2n4', label: 'Hand2Note 4' },
  { id: 'pt4', label: 'PokerTracker 4' },
  { id: 'hm3', label: 'Holdem Manager 3' },
];

export const softwareLabel = (s: ImportSoftware) => SOFTWARE_OPTIONS.find((o) => o.id === s)?.label ?? s;

/** Query string of GET /api/import/tracker/databases; blank fields are left out so the backend defaults apply. */
export function trackerQuery(software: TrackerSoftware, conn: TrackerConnection | null): string {
  const sp = new URLSearchParams({ software });
  if (conn) {
    if (conn.host?.trim()) sp.set('host', conn.host.trim());
    if (conn.port != null && Number.isFinite(conn.port)) sp.set('port', String(conn.port));
    if (conn.user?.trim()) sp.set('user', conn.user.trim());
    if (conn.password) sp.set('password', conn.password);
  }
  return sp.toString();
}

export async function getTrackerDatabases(
  software: TrackerSoftware,
  conn: TrackerConnection | null,
  signal?: AbortSignal,
): Promise<TrackerDatabases> {
  const res = await fetch(`/api/import/tracker/databases?${trackerQuery(software, conn)}`, { signal });
  if (!res.ok) throw new Error(`Looking for databases failed: ${res.status} ${res.statusText}`);
  return res.json();
}

/** "name (1,234 hands)" */
export function databaseOptionLabel(db: TrackerDatabase, fmt: (n: number) => string): string {
  return `${db.name} (${fmt(db.hands)} ${db.hands === 1 ? 'hand' : 'hands'})`;
}

/** Text under the Database select when the search is over; null when there is something to pick. */
export function searchMessage(result: TrackerDatabases | null): string | null {
  if (!result) return null;
  if (result.databases.length > 0) return null;
  return result.error || 'Databases not found';
}

/** Port field text -> number, or undefined when blank/invalid. */
export function parsePort(text: string): number | undefined {
  const t = text.trim();
  if (!/^\d{1,5}$/.test(t)) return undefined;
  const n = Number(t);
  return n >= 1 && n <= 65535 ? n : undefined;
}

export interface SavedConnection {
  custom: boolean;
  host: string;
  port: string;
  user: string;
}

export const connectionKey = (s: TrackerSoftware) => `ohm.import.tracker.${s}`;
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

export function loadConnection(storage: StorageLike | null, s: TrackerSoftware): SavedConnection {
  const blank: SavedConnection = { custom: false, host: '', port: '', user: '' };
  if (!storage) return blank;
  try {
    const r = JSON.parse(storage.getItem(connectionKey(s)) ?? 'null');
    if (!r || typeof r !== 'object') return blank;
    const str = (v: unknown) => (typeof v === 'string' ? v : '');
    return { custom: r.custom === true, host: str(r.host), port: str(r.port), user: str(r.user) };
  } catch {
    return blank;
  }
}

/** Host, port and user only. The password is never written anywhere. */
export function saveConnection(storage: StorageLike | null, s: TrackerSoftware, c: SavedConnection): void {
  if (!storage) return;
  try {
    storage.setItem(connectionKey(s), JSON.stringify({ custom: c.custom, host: c.host, port: c.port, user: c.user }));
  } catch {
    // not remembered
  }
}

/** Connection to send: nothing unless "Custom settings" is on. */
export function activeConnection(c: SavedConnection, password: string): TrackerConnection | null {
  if (!c.custom) return null;
  return { host: c.host, port: parsePort(c.port), user: c.user, password };
}

/** What the user picked to import; the "Import Hand History" step sits between this and the request. */
export type ImportSource =
  | { kind: 'files'; files: File[] }
  | { kind: 'h2n'; path: string; name: string }
  | { kind: 'tracker'; software: TrackerSoftware; database: string; conn: TrackerConnection | null };
