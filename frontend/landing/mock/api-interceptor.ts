/**
 * Global fetch interceptor for the landing page.
 * Intercepts all /api/* requests and returns mock data.
 * Must be imported before any React code.
 */

import { mockGraphResponse, mockFilterOptions, mockBreakdown } from './graph-data';
import { mockHeroStats, mockDriftResponse } from './stats-data';
import { mockHandListResponse, mockHandDetails, mockTagDefs } from './hands-data';

const originalFetch = window.fetch.bind(window);

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

type RouteHandler = (url: URL, init?: RequestInit) => Response;

const routes: [RegExp, RouteHandler][] = [
  // Health
  [/^\/api\/health$/, () => json({ status: 'ok', hands: 800, rebuilding: false })],

  // Auto import is off on the landing page (the status bar item stays hidden)
  [/^\/api\/config\/auto_import$/, () => {
    const v = { enabled: false, workspace_id: null, folders: [], archive_enabled: false, archive_dir: null };
    return json({ value: v, default: v, is_default: true });
  }],
  [/^\/api\/auto-import\/status$/, () => json({
    enabled: false, running: false, workspace_id: null, session_hands: 0, hands_per_hour: 0,
    last_import_at: null, watched_files: 0, last_error: null, large_folders: [],
  })],

  // Settings
  [/^\/api\/settings$/, () => json({ hero_username: 'Hero', hero_site: 'GG' })],

  // Workspaces (the app pages read the active workspace and its checkpoints)
  [/^\/api\/workspaces$/, () => json([{
    id: 1, name: 'My Game', hero_username: 'Hero', hero_site: 'GG', description: null, color: null,
    hand_count: 800, date_range: { min: '2025-07-01', max: '2025-07-31' }, created_at: '2025-07-01T00:00:00',
  }])],
  [/^\/api\/workspaces\/\d+\/checkpoints$/, () => json([])],
  [/^\/api\/workspaces\/\d+\/heroes$/, () => json({
    auto_detect: true,
    accounts: [{ site: 'GG', site_name: 'GGPoker', username: 'Hero', source: 'auto', hand_count: 800 }],
    active: { site: 'GG', site_name: 'GGPoker', username: 'Hero', hand_count: 800 },
  })],

  // Graph
  [/^\/api\/reports\/graph/, () => json(mockGraphResponse)],

  // Filter options
  [/^\/api\/reports\/filter-options$/, () => json(mockFilterOptions)],

  // Breakdown
  [/^\/api\/reports\/breakdown/, () => json(mockBreakdown)],

  // Stats
  [/^\/api\/stats\/hero/, () => json(mockHeroStats)],

  // Drift
  [/^\/api\/reports\/drift/, () => json(mockDriftResponse)],

  // Hands list
  [/^\/api\/hands$/, () => json(mockHandListResponse)],

  // Mark / tag / unmark a hand: nothing is stored, the answer is a valid MarkState
  [/^\/api\/hands\/([^/]+)\/mark$/, (url: URL, init?: RequestInit) => {
    const id = decodeURIComponent(url.pathname.split('/')[3]);
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    let tagIds: number[] = [];
    try {
      const body = JSON.parse(String(init?.body ?? '{}')) as { tag_ids?: number[] };
      tagIds = body.tag_ids ?? [];
    } catch {
      // no body: plain mark
    }
    const tags = mockTagDefs
      .filter((t) => tagIds.includes(t.id))
      .map(({ id: tid, name, color }) => ({ id: tid, name, color }));
    return json({ hand_id: id, player_id: 1, marked: true, tags });
  }],

  // Hand detail
  [/^\/api\/hands\/([^/]+)$/, (url: URL) => {
    const id = url.pathname.split('/').pop()!;
    const detail = mockHandDetails[id];
    if (detail) return json(detail);
    // Return first available detail as fallback
    const fallback = Object.values(mockHandDetails)[0];
    return json(fallback);
  }],

  // Tag catalogue
  [/^\/api\/tag-defs$/, () => json(mockTagDefs)],

  // Stat detail endpoints — return minimal data
  [/^\/api\/stats\/detail\//, () => json({
    stat_key: 'vpip',
    stat_name: 'VPIP',
    action_count: 196,
    opportunity_count: 800,
    key_street: 'preflop',
    hands: [],
    total: 0,
    page: 1,
    per_page: 25,
    total_pages: 0,
  })],
];

window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = typeof input === 'string'
    ? new URL(input, window.location.origin)
    : input instanceof URL
      ? input
      : new URL(input.url, window.location.origin);

  if (url.pathname.startsWith('/api')) {
    // Small delay to simulate network
    await new Promise(r => setTimeout(r, 50 + Math.random() * 100));

    for (const [pattern, handler] of routes) {
      if (pattern.test(url.pathname)) {
        return handler(url, init);
      }
    }

    // Unmatched API route — return empty 200
    return json({});
  }

  // Non-API requests (fonts, assets, etc.) pass through
  return originalFetch(input, init);
};
