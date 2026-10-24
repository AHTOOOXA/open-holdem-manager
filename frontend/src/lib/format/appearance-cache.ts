/** localStorage copy of Stat Appearance, so the first paint already formats like the saved settings. */
import type { StatAppearance } from '../config/types';
import { setStatAppearance } from './h2n';

export const APPEARANCE_CACHE_KEY = 'ohm.statAppearance';

const NUMBER_KEYS = ['one_decimal_below', 'show_sample_below', 'dim_below', 'vs_user_substitute_above'] as const;
const BOOL_KEYS = ['show_99_for_100', 'leading_zero', 'shorten_amounts'] as const;

/** The stored appearance, or null when missing or malformed. */
export function parseStoredAppearance(raw: string | null | undefined): StatAppearance | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Record<string, unknown>;
    if (!v || typeof v !== 'object') return null;
    for (const k of NUMBER_KEYS) if (typeof v[k] !== 'number' || !Number.isFinite(v[k])) return null;
    for (const k of BOOL_KEYS) if (typeof v[k] !== 'boolean') return null;
    return v as unknown as StatAppearance;
  } catch {
    return null;
  }
}

/** Apply the cached appearance now (call once at startup). */
export function restoreCachedAppearance(storage: Pick<Storage, 'getItem'> | undefined = safeStorage()): void {
  const cfg = parseStoredAppearance(storage?.getItem(APPEARANCE_CACHE_KEY));
  if (cfg) setStatAppearance(cfg);
}

export function cacheAppearance(cfg: StatAppearance, storage: Pick<Storage, 'setItem'> | undefined = safeStorage()): void {
  try {
    storage?.setItem(APPEARANCE_CACHE_KEY, JSON.stringify(cfg));
  } catch {
    // storage full / unavailable
  }
}

function safeStorage(): Storage | undefined {
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage;
  } catch {
    return undefined;
  }
}
