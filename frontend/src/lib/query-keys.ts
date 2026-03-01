export const queryKeys = {
  filterOptions: ['filter-options'] as const,

  stats: {
    hero: (filters: Record<string, unknown> | object) => ['stats', 'hero', filters] as const,
    detail: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'detail', statKey, filters] as const,
    trend: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'trend', statKey, filters] as const,
    analysis: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'analysis', statKey, filters] as const,
    evBreakdown: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'ev-breakdown', statKey, filters] as const,
    sizing: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'sizing', statKey, filters] as const,
    foldEquity: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'fold-equity', statKey, filters] as const,
    byContext: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'by-context', statKey, filters] as const,
    composition: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'composition', statKey, filters] as const,
    money: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'money', statKey, filters] as const,
    postflopBridge: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'postflop-bridge', statKey, filters] as const,
    continuingRange: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'continuing-range', statKey, filters] as const,
    statRange: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'stat-range', statKey, filters] as const,
  },

  graph: {
    data: (filters: Record<string, unknown> | object) => ['graph', 'data', filters] as const,
    breakdown: (filters: Record<string, unknown> | object) => ['graph', 'breakdown', filters] as const,
  },

  hands: {
    list: (params: Record<string, unknown> | object) => ['hands', 'list', params] as const,
    detail: (id: string) => ['hands', 'detail', id] as const,
    tags: ['hands', 'tags'] as const,
  },

  range: (filters: Record<string, unknown> | object) => ['range', filters] as const,

  cashDrop: (filters: Record<string, unknown> | object) => ['cash-drop', filters] as const,

  drift: (filters: Record<string, unknown> | object) => ['drift', filters] as const,

  sessions: {
    list: ['sessions', 'list'] as const,
    detail: (index: number) => ['sessions', 'detail', index] as const,
  },

  population: {
    overview: (filters: Record<string, unknown> | object) => ['population', 'overview', filters] as const,
    preflop: (filters: Record<string, unknown> | object) => ['population', 'preflop', filters] as const,
    segments: (filters: Record<string, unknown> | object) => ['population', 'segments', filters] as const,
    postflop: (filters: Record<string, unknown> | object) => ['population', 'postflop', filters] as const,
    potTypes: (filters: Record<string, unknown> | object) => ['population', 'pot-types', filters] as const,
    showdown: (filters: Record<string, unknown> | object) => ['population', 'showdown', filters] as const,
    huVsMw: (filters: Record<string, unknown> | object) => ['population', 'hu-vs-mw', filters] as const,
    comparison: (filters: Record<string, unknown> | object) => ['population', 'comparison', filters] as const,
  },

  players: {
    list: (params: Record<string, unknown> | object) => ['players', 'list', params] as const,
    detail: (id: number) => ['players', 'detail', id] as const,
    stats: (id: number, filters: Record<string, unknown> | object) => ['players', 'stats', id, filters] as const,
    h2h: (id: number) => ['players', 'h2h', id] as const,
  },

  identities: {
    list: ['identities', 'list'] as const,
    detail: (id: number) => ['identities', 'detail', id] as const,
    stats: (id: number, filters: Record<string, unknown> | object) => ['identities', 'stats', id, filters] as const,
  },

};
