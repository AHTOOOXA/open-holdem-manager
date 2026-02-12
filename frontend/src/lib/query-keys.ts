export const queryKeys = {
  filterOptions: ['filter-options'] as const,

  stats: {
    hero: (filters: Record<string, unknown>) => ['stats', 'hero', filters] as const,
    detail: (statKey: string, filters: Record<string, unknown>) => ['stats', 'detail', statKey, filters] as const,
    trend: (statKey: string, filters: Record<string, unknown>) => ['stats', 'trend', statKey, filters] as const,
    analysis: (statKey: string, filters: Record<string, unknown>) => ['stats', 'analysis', statKey, filters] as const,
    evBreakdown: (statKey: string, filters: Record<string, unknown>) => ['stats', 'ev-breakdown', statKey, filters] as const,
    sizing: (statKey: string, filters: Record<string, unknown>) => ['stats', 'sizing', statKey, filters] as const,
    foldEquity: (statKey: string, filters: Record<string, unknown>) => ['stats', 'fold-equity', statKey, filters] as const,
    byContext: (statKey: string, filters: Record<string, unknown>) => ['stats', 'by-context', statKey, filters] as const,
    composition: (statKey: string, filters: Record<string, unknown>) => ['stats', 'composition', statKey, filters] as const,
    money: (statKey: string, filters: Record<string, unknown>) => ['stats', 'money', statKey, filters] as const,
    postflopBridge: (statKey: string, filters: Record<string, unknown>) => ['stats', 'postflop-bridge', statKey, filters] as const,
    continuingRange: (statKey: string, filters: Record<string, unknown>) => ['stats', 'continuing-range', statKey, filters] as const,
    statRange: (statKey: string, filters: Record<string, unknown>) => ['stats', 'stat-range', statKey, filters] as const,
  },

  graph: {
    data: (filters: Record<string, unknown>) => ['graph', 'data', filters] as const,
    breakdown: (filters: Record<string, unknown>) => ['graph', 'breakdown', filters] as const,
  },

  hands: {
    list: (params: Record<string, unknown>) => ['hands', 'list', params] as const,
    detail: (id: string) => ['hands', 'detail', id] as const,
    tags: ['hands', 'tags'] as const,
  },

  range: (filters: Record<string, unknown>) => ['range', filters] as const,

  cashDrop: (filters: Record<string, unknown>) => ['cash-drop', filters] as const,

  drift: (filters: Record<string, unknown>) => ['drift', filters] as const,

  sessions: {
    list: ['sessions', 'list'] as const,
    detail: (index: number) => ['sessions', 'detail', index] as const,
  },
};
