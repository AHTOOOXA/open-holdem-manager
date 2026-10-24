/** Pure helpers for the "Import Hand History" date filter (no React, unit-tested). */
import { sessionPresets, type DatePresetDef } from '@/lib/reports/steps';
import type { ImportDateFilter } from './types';

export const IMPORT_FILTER_KEY = 'ohm.import.dateFilter';

/** Query params every import endpoint takes. */
export interface ImportRange {
  date_from?: string;
  date_to?: string;
}

/** "All Time" plus the presets of the other date filters, without "Last Session" (never offered; none exists in sessionPresets). */
export function importPresets(now: Date = new Date(), dayStartHour?: number): DatePresetDef[] {
  const all = dayStartHour === undefined ? sessionPresets(now) : sessionPresets(now, dayStartHour);
  return all.filter((p) => p.id !== 'all' && p.id !== 'last-session' && p.id !== 'lastsession');
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const isDate = (v: unknown): v is string => typeof v === 'string' && ISO_DATE.test(v);

/** Normalise anything stored or typed into a filter: unknown presets and bad dates are dropped. */
export function sanitizeFilter(raw: unknown, now: Date = new Date(), dayStartHour?: number): ImportDateFilter {
  if (!raw || typeof raw !== 'object') return {};
  const r = raw as Record<string, unknown>;
  if (typeof r.preset === 'string') {
    return importPresets(now, dayStartHour).some((p) => p.id === r.preset) ? { preset: r.preset } : {};
  }
  const out: ImportDateFilter = {};
  if (isDate(r.from)) out.from = r.from;
  if (isDate(r.to)) out.to = r.to;
  return out;
}

/** The range to send: presets are re-derived from `now`, so "Today" stays today. */
export function resolveFilter(filter: ImportDateFilter, now: Date = new Date(), dayStartHour?: number): ImportRange {
  let from = filter.from;
  let to = filter.to;
  if (filter.preset) {
    const p = importPresets(now, dayStartHour).find((x) => x.id === filter.preset);
    if (p) {
      from = p.from;
      to = p.to;
    }
  }
  const out: ImportRange = {};
  if (from) out.date_from = from;
  if (to) out.date_to = to;
  return out;
}

export function isAllTime(filter: ImportDateFilter): boolean {
  return !filter.preset && !filter.from && !filter.to;
}

/** A custom range with both ends set must not run backwards. */
export function isValidFilter(filter: ImportDateFilter): boolean {
  return !(filter.from && filter.to && filter.from > filter.to);
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export function loadFilter(storage: StorageLike | null, now: Date = new Date(), dayStartHour?: number): ImportDateFilter {
  if (!storage) return {};
  try {
    const raw = storage.getItem(IMPORT_FILTER_KEY);
    return raw ? sanitizeFilter(JSON.parse(raw), now, dayStartHour) : {};
  } catch {
    return {};
  }
}

/** Relative presets are stored by id only; all time clears the key. */
export function saveFilter(storage: StorageLike | null, filter: ImportDateFilter): void {
  if (!storage) return;
  try {
    if (isAllTime(filter)) storage.removeItem(IMPORT_FILTER_KEY);
    else storage.setItem(IMPORT_FILTER_KEY, JSON.stringify(filter.preset ? { preset: filter.preset } : { from: filter.from, to: filter.to }));
  } catch {
    // storage full or blocked: the filter just is not remembered
  }
}

/** Value of the filter Select: 'all', 'custom' or a preset id. */
export function filterMode(filter: ImportDateFilter): string {
  return filter.preset ?? (filter.from || filter.to ? 'custom' : 'all');
}
