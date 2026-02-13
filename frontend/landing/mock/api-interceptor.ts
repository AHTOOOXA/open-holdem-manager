/**
 * Global fetch interceptor for the landing page.
 * Intercepts all /api/* requests and returns mock data.
 * Must be imported before any React code.
 */

import { mockGraphResponse, mockFilterOptions, mockBreakdown } from './graph-data';
import { mockHeroStats, mockDriftResponse } from './stats-data';
import { mockHandListResponse, mockHandDetails, mockTags } from './hands-data';

const originalFetch = window.fetch.bind(window);

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

type RouteHandler = (url: URL) => Response;

const routes: [RegExp, RouteHandler][] = [
  // Health
  [/^\/api\/health$/, () => json({ status: 'ok', hands: 800, rebuilding: false })],

  // Settings
  [/^\/api\/settings$/, () => json({ hero_username: 'Hero', hero_site: 'GG' })],

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

  // Hand detail
  [/^\/api\/hands\/([^/]+)$/, (url: URL) => {
    const id = url.pathname.split('/').pop()!;
    const detail = mockHandDetails[id];
    if (detail) return json(detail);
    // Return first available detail as fallback
    const fallback = Object.values(mockHandDetails)[0];
    return json(fallback);
  }],

  // Tags
  [/^\/api\/tags$/, () => json(mockTags)],

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
        return handler(url);
      }
    }

    // Unmatched API route — return empty 200
    return json({});
  }

  // Non-API requests (fonts, assets, etc.) pass through
  return originalFetch(input, init);
};
