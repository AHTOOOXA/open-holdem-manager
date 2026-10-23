/** Hidden Hands filters that arrive with old links (`/reports?tab=hands&stat_flag=…`), made visible. */

export interface LegacyHandsFilters {
  statFlags: string[];
  position: string[];
  statKey?: string;
}

/** Readable list of the filters a legacy link applies to page 0's hand list; empty = none. */
export function legacyFilterLabels(f: LegacyHandsFilters | undefined | null): string[] {
  if (!f) return [];
  const out = [...f.statFlags];
  if (f.statKey) out.push(f.statKey);
  for (const p of f.position) out.push(p);
  return out;
}

/** Filters of a legacy arrival unless it was dismissed (same `rev`) or is not a hands link. */
export function activeLegacyFilters<T extends LegacyHandsFilters>(
  link: { tab: string } & T | null | undefined,
  rev: number,
  dismissedRev: number,
): T | undefined {
  if (!link || link.tab !== 'hands' || rev === dismissedRev) return undefined;
  return legacyFilterLabels(link).length > 0 ? link : undefined;
}
