/** Auto-import: client and pure helpers (contract: ./types.ts §2). */
import type { AutoImportConfig, AutoImportStatus } from './types';

export const AUTO_IMPORT_STATUS_KEY = ['auto-import', 'status'] as const;
export const AUTO_IMPORT_POLL_MS = 2000;
/** Screens refresh at most this often while auto-import adds hands. */
export const AUTO_IMPORT_REFRESH_GAP_MS = 5000;

export async function getAutoImportStatus(): Promise<AutoImportStatus> {
  const res = await fetch('/api/auto-import/status');
  if (!res.ok) throw new Error(`Auto import status failed: ${res.status}`);
  return res.json();
}

/** The settings value when the config store gave no value (landing mock, old backend). */
export const AUTO_IMPORT_DEFAULTS: AutoImportConfig = {
  enabled: false,
  workspace_id: null,
  folders: [],
  archive_enabled: false,
  archive_dir: null,
};

export const isAbsolutePath = (p: string) => p.startsWith('/') || /^[A-Za-z]:[\\/]/.test(p) || p.startsWith('\\\\');

function normalizePath(p: string): string {
  const t = p.trim();
  const stripped = t.replace(/[\\/]+$/, '');
  return stripped === '' || /^[A-Za-z]:$/.test(stripped) ? t : stripped;
}

const sameFolder = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** Add a folder; an already listed one (case-insensitive) is ignored. */
export function addFolder(folders: readonly string[], path: string): { folders: string[]; added: boolean } {
  const p = normalizePath(path);
  if (!p || folders.some((f) => sameFolder(f, p))) return { folders: [...folders], added: false };
  return { folders: [...folders, p], added: true };
}

/** Replace the folder at `index` in place; a path already listed elsewhere just removes nothing and changes nothing. */
export function replaceFolder(folders: readonly string[], index: number, path: string): string[] {
  const p = normalizePath(path);
  if (!p || index < 0 || index >= folders.length) return [...folders];
  if (folders.some((f, i) => i !== index && sameFolder(f, p))) return [...folders];
  return folders.map((f, i) => (i === index ? p : f));
}

export const removeFolder = (folders: readonly string[], index: number): string[] => folders.filter((_, i) => i !== index);

/**
 * How long to wait before refreshing the screens after the status poll: null when no hands were added,
 * 0 when the refresh may run now, else the remaining part of the gap.
 */
export function refreshDelay(prevHands: number | null, hands: number, lastRefreshAt: number, now: number, gapMs = AUTO_IMPORT_REFRESH_GAP_MS): number | null {
  if (prevHands === null || hands <= prevHands) return null;
  return Math.max(0, lastRefreshAt + gapMs - now);
}

/** "Auto import: 1,234 hands, 56/h" */
export function statusText(s: Pick<AutoImportStatus, 'session_hands' | 'hands_per_hour'>, fmt: (n: number) => string): string {
  return `Auto import: ${fmt(s.session_hands)} ${s.session_hands === 1 ? 'hand' : 'hands'}, ${fmt(Math.round(s.hands_per_hour))}/h`;
}

/** Size in MB for the large-folder warning. */
export function megabytes(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}
