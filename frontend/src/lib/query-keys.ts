export const queryKeys = {
  filterOptions: ['filter-options'] as const,

  stats: {
    hero: (filters: Record<string, unknown> | object) => ['stats', 'hero', filters] as const,
    detail: (statKey: string, filters: Record<string, unknown> | object) => ['stats', 'detail', statKey, filters] as const,
  },

  graph: {
    data: (filters: Record<string, unknown> | object) => ['graph', 'data', filters] as const,
    breakdown: (filters: Record<string, unknown> | object) => ['graph', 'breakdown', filters] as const,
  },

  hands: {
    list: (params: Record<string, unknown> | object) => ['hands', 'list', params] as const,
    detail: (id: string) => ['hands', 'detail', id] as const,
  },

  cashDrop: (filters: Record<string, unknown> | object) => ['cash-drop', filters] as const,

  drift: (filters: Record<string, unknown> | object) => ['drift', filters] as const,

  population: {
    overview: (filters: Record<string, unknown> | object) => ['population', 'overview', filters] as const,
    fullStats: (filters: Record<string, unknown> | object) => ['population', 'full-stats', filters] as const,
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
