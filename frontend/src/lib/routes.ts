/**
 * App routes: the rail destinations, old-URL redirects and the remembered start screen.
 * Pure (no React), covered by tests/routes.test.ts.
 */

/** Every destination in the left rail, top to bottom. */
export const RAIL_PATHS = [
  '/reports',
  '/statistics',
  '/sessions',
  '/marked',
  '/extras/stats',
  '/extras/compare',
  '/extras/cash-drop',
  '/extras/population',
  '/extras/players',
  '/databases',
  '/configuration',
] as const;

export type RailPath = (typeof RAIL_PATHS)[number];

/** Caption of each rail destination (rail tooltip/label and the caption row title). */
export const RAIL_LABELS: Record<RailPath, string> = {
  '/reports': 'Reports',
  '/statistics': 'Statistics',
  '/sessions': 'Sessions',
  '/marked': 'Marked Hands',
  '/extras/stats': 'Stats',
  '/extras/compare': 'Compare',
  '/extras/cash-drop': 'Cash Drop',
  '/extras/population': 'Population',
  '/extras/players': 'Players',
  '/databases': 'Databases',
  '/configuration': 'Configuration',
};

export const DEFAULT_ROUTE: RailPath = '/reports';

/** localStorage key holding the last rail destination the user visited. */
export const LAST_ROUTE_KEY = 'ohm.lastRoute';

function isPrefixPath(pathname: string, base: string): boolean {
  return pathname === base || pathname.startsWith(base + '/');
}

/** The rail destination a pathname belongs to (`/extras/stats/vpip` → `/extras/stats`), or null. */
export function railPathFor(pathname: string): RailPath | null {
  const clean = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  return RAIL_PATHS.find((p) => isPrefixPath(clean, p)) ?? null;
}

/** The screen `/` opens: the stored last destination if it is still a known one, else Reports. */
export function resolveLastRoute(stored: string | null | undefined): RailPath {
  return RAIL_PATHS.find((p) => p === stored) ?? DEFAULT_ROUTE;
}

/** Old URLs that still work (bookmarks, links in other tracks' screens). */
export const LEGACY_PATHS = [
  '/graph',
  '/range',
  '/hands',
  '/general',
  '/stats',
  '/stats/:statKey',
  '/cash-drop',
  '/compare',
  '/population',
  '/players',
  '/players/:playerId',
  '/players/identity/:identityId',
  '/settings',
  '/settings/workspaces',
] as const;

export type LegacyPath = (typeof LEGACY_PATHS)[number];

type Params = Readonly<Record<string, string | undefined>>;

const seg = (v: string | undefined) => encodeURIComponent(v ?? '');

/** Where each old URL lives now: a path, plus a `tab` for the Reports screen. */
const LEGACY_TARGETS: Record<LegacyPath, (p: Params) => { path: string; tab?: string }> = {
  '/graph': () => ({ path: '/reports', tab: 'graph' }),
  '/range': () => ({ path: '/reports', tab: 'range' }),
  '/hands': () => ({ path: '/reports', tab: 'hands' }),
  '/general': () => ({ path: '/statistics' }),
  '/stats': () => ({ path: '/extras/stats' }),
  '/stats/:statKey': (p) => ({ path: `/extras/stats/${seg(p.statKey)}` }),
  '/cash-drop': () => ({ path: '/extras/cash-drop' }),
  '/compare': () => ({ path: '/extras/compare' }),
  '/population': () => ({ path: '/extras/population' }),
  '/players': () => ({ path: '/extras/players' }),
  '/players/:playerId': (p) => ({ path: `/extras/players/${seg(p.playerId)}` }),
  '/players/identity/:identityId': (p) => ({ path: `/extras/players/identity/${seg(p.identityId)}` }),
  '/settings': () => ({ path: '/databases' }),
  '/settings/workspaces': () => ({ path: '/databases' }),
};

/**
 * The new URL for an old one. Route params carry over; the query string is kept, with
 * `tab` first when the target is a Reports tab (an incoming `tab` is replaced).
 */
export function legacyRedirect(from: LegacyPath, params: Params, search = '', hash = ''): string {
  const { path, tab } = LEGACY_TARGETS[from](params);
  const incoming = new URLSearchParams(search);
  const out = new URLSearchParams();
  if (tab) {
    out.set('tab', tab);
    incoming.delete('tab');
  }
  for (const [k, v] of incoming) out.append(k, v);
  const qs = out.toString();
  return `${path}${qs ? `?${qs}` : ''}${hash}`;
}
