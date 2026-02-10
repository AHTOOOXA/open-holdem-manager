export const queryKeys = {
  filterOptions: ['filter-options'] as const,

  stats: {
    hero: (filters: Record<string, unknown>) => ['stats', 'hero', filters] as const,
    detail: (statKey: string, filters: Record<string, unknown>) => ['stats', 'detail', statKey, filters] as const,
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
};
