/** Pure helpers behind the Configuration sections (no React; unit-tested). */
import type { ColorMarker } from './types';

export interface NumberSpec {
  min: number;
  max: number;
  /** Whole numbers only (default true). */
  integer?: boolean;
}

/** The number in `text`, or an inline error message. */
export function parseNumberField(text: string, spec: NumberSpec): { value: number } | { error: string } {
  const integer = spec.integer ?? true;
  const t = text.trim();
  const message = `Enter ${integer ? 'a whole number' : 'a number'} from ${spec.min} to ${spec.max}`;
  if (!(integer ? /^\d+$/ : /^\d+(\.\d+)?$/).test(t)) return { error: message };
  const value = Number(t);
  return value >= spec.min && value <= spec.max ? { value } : { error: message };
}

/** A low/high pair from two texts: both valid and low <= high. */
export function parseRangePair(lo: string, hi: string, spec: NumberSpec): { value: [number, number] } | { error: string } {
  const a = parseNumberField(lo, spec);
  if ('error' in a) return a;
  const b = parseNumberField(hi, spec);
  if ('error' in b) return b;
  if (a.value > b.value) return { error: 'The first value must not be above the second' };
  return { value: [a.value, b.value] };
}

/** "New Workspace", then "New Workspace (2)", "(3)", ... the first not in `existing` (case-insensitive). */
export function uniqueName(base: string, existing: readonly string[]): string {
  const taken = new Set(existing.map((n) => n.trim().toLowerCase()));
  if (!taken.has(base.toLowerCase())) return base;
  for (let i = 2; ; i += 1) {
    const candidate = `${base} (${i})`;
    if (!taken.has(candidate.toLowerCase())) return candidate;
  }
}

/** Trimmed name for a tag / marker, or null when empty or longer than `max`. */
export function validName(raw: string, max = 60): string | null {
  const t = raw.trim();
  return t && t.length <= max ? t : null;
}

/** A fresh colour marker: "new marker", tag-3, not regular. `id` comes from GET /api/config/color_markers/next-id (never reused). */
export function newColorMarker(id: number): ColorMarker {
  return { id, name: 'new marker', color: 'tag-3', is_regular: false };
}

export function patchMarker(markers: readonly ColorMarker[], id: number, patch: Partial<ColorMarker>): ColorMarker[] {
  return markers.map((m) => (m.id === id ? { ...m, ...patch } : m));
}

// ── Aliases ──────────────────────────────────────────────────────────────

export interface AliasLike {
  id: number;
  display_name: string;
  pinned?: boolean;
  aliases: { username: string }[];
}

/** Pinned first, then A-Z by name (case-insensitive). */
export function sortAliases<T extends AliasLike>(list: readonly T[]): T[] {
  return [...list].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    return a.display_name.localeCompare(b.display_name, undefined, { sensitivity: 'base' });
  });
}

/** Keep aliases whose name or any member nickname contains `query` (case-insensitive). */
export function filterAliases<T extends AliasLike>(list: readonly T[], query: string): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...list];
  return list.filter((a) => a.display_name.toLowerCase().includes(q) || a.aliases.some((m) => m.username.toLowerCase().includes(q)));
}

export interface Member {
  playerId: number;
  workspaceId: number;
  username: string;
  /** Alias row id when it already exists on the server. */
  aliasId?: number;
}

/** What to call on the server to turn `before` into `after`. */
export function diffMembers(before: readonly Member[], after: readonly Member[]): { add: Member[]; remove: Member[] } {
  const key = (m: Member) => `${m.workspaceId}:${m.playerId}`;
  const a = new Set(after.map(key));
  const b = new Set(before.map(key));
  return {
    add: after.filter((m) => !b.has(key(m))),
    remove: before.filter((m) => !a.has(key(m))),
  };
}
