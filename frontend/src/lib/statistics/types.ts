/**
 * Statistics dashboards contract (frontend ↔ backend). Spec: statistics-dashboards.md (own words).
 *
 * A workspace has one dashboard tree: folders (nestable) and dashboards. A dashboard stores only
 * its definition; pages, selections and results live in memory. The whole document is read and
 * written at once: GET/PUT /api/statistics/dashboards?workspace_id= (backend validates and stores
 * it as JSON in the `settings` table under `statistics_dashboards.<workspace_id>`).
 */
import type { Step } from '../reports/types';

export interface DashboardDefinition {
  /** null = the active hero (resolved by the backend, like the General screen today). */
  player_id: number | null;
  /**
   * Plain filter steps only ('date', 'stakes', 'mode'), in that order, none = All Time / every
   * game. A relative date preset keeps its `preset` id (see reports/steps.ts PresetDateStep) and is
   * re-derived on load; the backend stores the steps as given (it allows the extra `preset` key).
   */
  filters: Step[];
  /** 'default' = the General profile (profile dashboard); a GENERAL_CELLS action-cell id = a
   *  single-stat dashboard. Unknown ids show "--" in the profile dropdown. */
  profile_id: string;
}

export type DashboardNode =
  | { id: number; kind: 'folder'; name: string; parent_id: number | null }
  | { id: number; kind: 'dashboard'; name: string; parent_id: number | null; definition: DashboardDefinition };

export interface DashboardsConfig {
  selected_id: number | null;
  collapsed: boolean;
  tree_width: number; // 280-1000, default 300
}

export interface DashboardsDoc {
  nodes: DashboardNode[];
  config: DashboardsConfig;
}
// GET: when nothing is stored the backend seeds one dashboard "new dashboard" (id 1, root,
//   { player_id: null, filters: [], profile_id: 'default' }) selected, collapsed false, width 300.
// PUT body = DashboardsDoc → returns the stored doc. 422 when: duplicate ids, a parent that is
//   missing or not a folder, a cycle, an empty name (after trim) or > 200 chars, no dashboards at
//   all, a definition with a non-plain step, tree_width outside 280-1000. selected_id pointing at
//   a missing node is fixed to the first dashboard instead of failing.

/** General popup addition: GET /api/general/cell/{id}/detail returns the cell as a Reports chain. */
// CellDetail.chain: Step[] = the plain filters the request used (as steps) + { k:'pos' } when the
//   cell has a position group + { k:'row', key }. The popup's 13x13 grid (preflop stats), Next
//   Actions tab and their hand pages call the Reports endpoints with it, so they count exactly the
//   cell's cases. /api/general and /api/general/cell/* also accept `chain` (JSON plain steps) as
//   the filter, used instead of stakes/game_mode/date_from/date_to by the Statistics screen.
