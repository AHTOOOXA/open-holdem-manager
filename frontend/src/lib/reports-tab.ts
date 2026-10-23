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
