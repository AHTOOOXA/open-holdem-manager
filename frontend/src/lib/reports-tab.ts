export const REPORT_TABS = ['graph', 'range', 'hands'] as const;
export type ReportTab = (typeof REPORT_TABS)[number];

/** Resolve the `tab` query param; anything unknown falls back to the graph. */
export function parseReportTab(value: string | null | undefined): ReportTab {
  return (REPORT_TABS as readonly string[]).includes(value ?? '') ? (value as ReportTab) : 'graph';
}

/** Copy of `params` with `tab` set; all other params are preserved. */
export function withReportTab(params: URLSearchParams, tab: ReportTab): URLSearchParams {
  const next = new URLSearchParams(params);
  next.set('tab', tab);
  return next;
}

/** Query params of the old preview links that the Reports page consumes once on arrival. */
export const LEGACY_REPORT_PARAMS = ['tab', 'stat_flag', 'stat_key', 'position'] as const;

export interface LegacyReportLink {
  tab: ReportTab;
  /** Hands-list filters for page 0's Hands tab (leak links: `?tab=hands&stat_flag=…`). */
  statFlags: string[];
  statKey?: string;
  position: string[];
}

/**
 * Read an old `?tab=graph|range|hands` link (redirects from /graph, /range, /hands and leak links).
 * Null when the URL has none of the legacy params.
 */
export function parseLegacyReportLink(params: URLSearchParams): LegacyReportLink | null {
  if (!LEGACY_REPORT_PARAMS.some((k) => params.has(k))) return null;
  const statFlags = params.getAll('stat_flag').filter(Boolean);
  const position = params.get('position')?.toUpperCase();
  const raw = params.get('tab');
  // Hand filters without a tab can only mean the hands list
  const tab = raw === null && statFlags.length > 0 ? 'hands' : parseReportTab(raw);
  return {
    tab,
    statFlags,
    statKey: params.get('stat_key') || undefined,
    position: position ? [position] : [],
  };
}

/** Copy of `params` without the legacy params (after they were consumed). */
export function withoutLegacyParams(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const k of LEGACY_REPORT_PARAMS) next.delete(k);
  return next;
}
