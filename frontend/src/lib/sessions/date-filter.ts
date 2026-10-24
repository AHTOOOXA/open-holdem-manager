/** The Sessions date filter: All Time, a relative preset (re-derived on every use) or a custom range. */
import { sessionPresets } from '../reports/steps';

export type SessionDateFilter =
  | { kind: 'preset'; id: string }
  | { kind: 'custom'; from?: string; to?: string };

/** null = All Time. */
export type StoredDateFilter = SessionDateFilter | null;

export const dateStorageKey = (workspaceId: number) => `ohm.sessions.date.${workspaceId}`;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Presets offered by the popover (no "All Time" - it has its own item - and no "Last Session"). */
export function datePresets(now: Date = new Date(), dayStartHour = 0) {
  return sessionPresets(shiftForDayStart(now, dayStartHour)).filter((p) => p.id !== 'all');
}

/** "Day starts at (hour)": before that hour it is still the previous calendar day. */
export function shiftForDayStart(now: Date, dayStartHour: number): Date {
  return dayStartHour > 0 ? new Date(now.getTime() - dayStartHour * 3_600_000) : now;
}

export function parseDateFilter(raw: string | null | undefined, now: Date = new Date(), dayStartHour = 0): StoredDateFilter {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<{ kind: string; id: string; from: string; to: string }> | null;
    if (!v || typeof v !== 'object') return null;
    if (v.kind === 'preset' && typeof v.id === 'string') {
      return datePresets(now, dayStartHour).some((p) => p.id === v.id) ? { kind: 'preset', id: v.id } : null;
    }
    if (v.kind === 'custom') {
      const from = typeof v.from === 'string' && ISO_DATE.test(v.from) ? v.from : undefined;
      const to = typeof v.to === 'string' && ISO_DATE.test(v.to) ? v.to : undefined;
      return from || to ? { kind: 'custom', from, to } : null;
    }
  } catch {
    // corrupted value: fall back to All Time
  }
  return null;
}

export function serializeDateFilter(f: StoredDateFilter): string | null {
  return f ? JSON.stringify(f) : null;
}

/** Query bounds; presets are re-derived from `now`. */
export function resolveDateFilter(f: StoredDateFilter, now: Date = new Date(), dayStartHour = 0): { date_from?: string; date_to?: string } {
  if (!f) return {};
  if (f.kind === 'custom') return { ...(f.from ? { date_from: f.from } : {}), ...(f.to ? { date_to: f.to } : {}) };
  const p = datePresets(now, dayStartHour).find((x) => x.id === f.id);
  return p?.from ? { date_from: p.from, ...(p.to ? { date_to: p.to } : {}) } : {};
}

function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}-${m}-${y}`;
}

/** Button caption: "All Time", "This Month", "From 01-10-2026 to 17-10-2026". */
export function dateFilterLabel(f: StoredDateFilter, now: Date = new Date(), dayStartHour = 0): string {
  if (!f) return 'All Time';
  if (f.kind === 'preset') return datePresets(now, dayStartHour).find((p) => p.id === f.id)?.label ?? 'All Time';
  if (f.from && f.to) return `From ${shortDate(f.from)} to ${shortDate(f.to)}`;
  if (f.from) return `From ${shortDate(f.from)}`;
  return f.to ? `Until ${shortDate(f.to)}` : 'All Time';
}

