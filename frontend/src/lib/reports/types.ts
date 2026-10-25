/**
 * Reports contract (frontend ↔ backend). Hand2Note's Reports screen: a row of pages; each page
 * adds filter steps to the chain it inherited. Every Reports endpoint takes the **full chain**
 * (inherited steps + the page's own steps, in order) and the player the dashboard reports on.
 *
 * Backend: `backend/app/reports/` (POST endpoints under /api/reports/*, JSON bodies).
 * Plain steps narrow the hand set in SQL. Spot steps (`row`, `next`, `faced`) move the page's
 * "hit point" (the decision the page is about) and are evaluated per hand with the same H2N
 * matcher as the General screen, so the same spot gives the same numbers on both screens.
 */

export type Street = 'preflop' | 'flop' | 'turn' | 'river';
export type Pos = 'EP' | 'MP' | 'CO' | 'BTN' | 'SB' | 'BB';

/** One filter step. `label` is the chip / page-title text; the backend fills it on steps it returns. */
export type Step = { label?: string } & (
  // ── plain steps (any order, narrow the hand set) ──
  | { k: 'pos'; v: Pos[] } // hero's 6-max position group (h2n_pos)
  | { k: 'stakes'; v: string[] } // hands.stakes values as stored, e.g. "$0.05/$0.10"
  | { k: 'mode'; v: 'fast' | 'regular' } // fast-fold (Rush & Cash / Zoom) vs regular tables
  | { k: 'tsize'; v: number[] } // table size (max seats), e.g. [6]
  | { k: 'date'; from?: string; to?: string } // ISO dates (inclusive), local day boundaries
  | { k: 'hour'; v: number[] } // local start hour 0-23
  | { k: 'stack'; lo: number; hi: number | null } // hero starting stack in bb, [lo, hi)
  | { k: 'game'; stakes: string; mode: string; tsize: number | null } // a Results row (mode: 'fast' | 'regular')
  | { k: 'cells'; v: string[] } // preflop hand classes, e.g. "AKs", "QQ", "T9o"
  | { k: 'hv'; street: Street; cats: string[] } // hand-value category keys ('other' too); flop/turn/river only
  // M5 (Sessions): plain steps a Sessions page adds
  | { k: 'session'; start: string; end: string } // played_at in [start, end], local naive ISO datetimes
  //   ("2026-10-17T20:10:05"); end = the session's LAST hand start (not the +180 s estimate)
  | { k: 'table'; v: string[] } // hands.table_name values
  | { k: 'with'; player_id: number } // hands where this player was dealt in (Sessions: villain pages use the hero)
  // ── spot steps (order matters; each moves the hit point) ──
  | { k: 'row'; key: string } // a named quick filter (General row key, e.g. "P01" = Raise 1st In)
  | { k: 'next'; street: Street; a: NextAction } // a Next Actions row after the current hit point
  | { k: 'faced'; street: Street; a: FacedAction } // a Faced Next row after the current hit point (backend
  //   generates all but villain_open_4bet / villain_limp_call / villain_limp_raise / villain_open_call; those are 422)
  | { k: 'betsize'; bucket: string } // a Bet Sizing bucket of the current hit action
  // M8: a custom action line (line builder / filter-dialog Actions tab). `dsl` is the H2N
  //   matcher row notation (backend/app/h2n/matcher.py docstring), e.g.
  //   "pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R". Evaluated per hand like `row` (same
  //   matcher → the hit point moves to the line's last filter action, so Next Actions etc. work
  //   after it). Invalid notation → 422 with a readable `detail`. Built by lib/lines (never typed).
  | { k: 'line'; dsl: string }
);

export type NextAction =
  | 'fold_vs_raise' | 'call_vs_raise' | 'raise_vs_raise'
  | 'fold_vs_bet' | 'call_vs_bet' | 'raise_vs_bet'
  | 'check_vs_call' | 'bet_vs_call'
  | 'check' | 'bet' | 'fold' | 'call' | 'raise'
  | 'limp_fold' | 'limp_call' | 'limp_raise';

export type FacedAction =
  | 'all_fold' | 'villain_bet' | 'villain_raise' | 'villain_squeeze' | 'villains_check'
  | 'one_call' | 'two_calls' | 'three_calls' | 'four_plus_calls'
  | 'villain_3bet' | 'villain_open_4bet' | 'villain_limp_call' | 'villain_limp_raise' | 'villain_open_call';

export interface ReportQuery {
  workspace_id: number;
  /** Player the dashboard reports on; omitted = the active hero (resolved by the backend). */
  player_id?: number;
  chain: Step[];
}

// ── POST /api/reports/split ─────────────────────────────────────────────────────────────────

export type SplitType =
  | 'results' | 'positions' | 'next_actions' | 'faced_next' | 'bet_sizing'
  | 'stack_sizes' | 'hour_of_day' | 'table_size'
  // M5 (Sessions lower tabs)
  | 'tables' // one row per hands.table_name; row filter = { k: 'table', v: [name] }
  | 'players'; // one row per opponent dealt in; values are the OPPONENT's (see SplitRow.player)

export type ValueFormat = 'count' | 'pct' | 'money' | 'bb' | 'bb100' | 'bbh' | 'ratio'
  | 'duration' // seconds, shown "2h 13m" / "13m"
  | 'rate'; // a per-hour figure (hands / h, $ / h): plain number, 1 decimal under 100

export interface SplitColumn {
  id: string;
  caption: string; // full caption (header tooltip, column picker)
  abbrev?: string; // short header text
  format: ValueFormat;
  winnings?: boolean; // coloured money-style (> 0 pos, <= 0 neg)
  /**
   * Key in `SplitRow.values` (and `summary`) holding this column's sample size, for small-sample
   * dimming. Either another column id ("hands") or an extra sample-only key the backend adds to
   * `values` ("vpip_opps", "stat_value_opps", "sd_hands", ...); sample keys are not columns.
   */
  sample?: string;
}

export interface SplitRow {
  key: string;
  caption: string; // row name = next page title (named spot when the chain has one)
  filter: Step; // appended to the next page's inherited chain when the row is clicked
  values: Record<string, number | null>;
  /** Lower tab to select on the page this row opens (Hand2Note: Faced Next after a hero action). */
  open_tab?: 'next_actions' | 'faced_next';
  /**
   * `players` split only: the opponent of the row. The page this row opens reports on that
   * player (`player_id` = this id) with the parent chain + `filter` ({ k: 'with', player_id:
   * <the reporting player> }), so its numbers are the opponent's in hands against hero.
   */
  player?: { id: number; username: string };
}

export interface SplitResponse {
  type: SplitType;
  entry_header: string; // first column header, e.g. "Position", "Next Actions"
  columns: SplitColumn[];
  rows: SplitRow[]; // default order (section 4/5 of the spec); empty = "No results yet"
  // (Faced Next at hand start, Bet Sizing without a hit action, rows without a case are dropped)
  summary: Record<string, number | null> | null; // only when rows.length > 1
  total_hands: number; // hands of the whole dashboard before page filters (Hits per 1000 base)
}

export interface SplitQuery extends ReportQuery {
  type: SplitType;
}

// ── POST /api/reports/spot ─ page summary + Stats upper tab ("smart reports") ─────────────
// Body: SpotQuery. Without `recipe` the stats follow the hit point's kind (M4). With a recipe the
// fixed Sessions recipes are returned instead (sessions.md §5.2):
//   session: anchors Hands, Duration, Hands / h | Won, Won EV, Win Rate EV;
//            grid Avg. Tables, VPIP, PFR, Ag., 3Bet, WTSD, W%SD, WWSF%, Rake paid, Rake Paid bb/100, Won bb
//   table:   as session without Avg. Tables
//   villain: anchors Hands, VPIP, PFR | EV diff. (Won EV - Won; "Won From Hero" is not computed);
//            grid Ag., Win Rate, Won Without Showdown, 3Bet, WTSD, W%SD, WWSF%, Rake paid, Rake Paid bb/100
// Stat ids: hands, duration, hands_h, won, won_ev, ev_bb100, avg_tables, vpip, pfr, ag, threebet,
// wtsd, wsd, wwsf, rake, rake_bb100, won_bb; villain: ev_diff, bb100, won_nsd.
// Recipe stats are never clickable (no `filter`). `group` splits anchors from the grid.

export type SpotRecipe = 'session' | 'table' | 'villain';

export interface SpotQuery extends ReportQuery {
  recipe?: SpotRecipe;
}

export type SpotKind = 'plain' | 'hero_raise' | 'hero_bet' | 'hero_call' | 'hero_check' | 'hero_fold' | 'villain';

export interface SpotStat {
  id: string;
  caption: string;
  value: number | null;
  sample: number | null; // opportunities; drives StatValue's sample display / dimming
  format: ValueFormat;
  winnings?: boolean;
  /** A step that opens the next page for this stat (clickable stats); absent = not clickable. */
  filter?: Step;
  /** Recipe responses only: 'anchor1' | 'anchor2' (the two anchor groups) or 'grid'. */
  group?: 'anchor1' | 'anchor2' | 'grid';
}

export interface SpotResponse {
  hands: number; // hands matching the chain (cases at the hit point)
  kind: SpotKind;
  hit_label: string | null; // e.g. "Continuation Bet"
  stats: SpotStat[];
  total_hands?: number; // every hand of the player (page 0's header count)
}

// ── POST /api/reports/preflop-range ─────────────────────────────────────────────────────────

export interface RangeCell {
  cls: string; // "AA", "AKs", "AKo" …
  hands: number;
  won_bb: number;
  /** 0-3: how often the class appears vs. its share of all dealt combos (4-level shade). */
  level: 0 | 1 | 2 | 3;
}

export interface PreflopRangeResponse {
  total: number;
  cells: RangeCell[]; // all 169 classes
}

// ── POST /api/reports/hand-strength ─────────────────────────────────────────────────────────

export interface HandStrengthQuery extends ReportQuery {
  street: Exclude<Street, 'preflop'>;
}

export interface HandStrengthRow {
  key: string; // category key (same keys as hvColor / backend hand_value.py)
  label: string;
  hands: number;
  pct: number; // share of known-cards hands on that street, 0-100 (percent, not a fraction)
  won_bb: number;
  weak: boolean;
}

export interface HandStrengthResponse {
  street: Exclude<Street, 'preflop'>;
  known: number;
  rows: HandStrengthRow[];
}

// ── GET /api/reports/quick-filters ──────────────────────────────────────────────────────────

export interface QuickFilter {
  key: string; // General row key for `{ k: 'row', key }`
  label: string; // "Raise 1st In"
  group: 'preflop' | 'flop' | 'turn' | 'river';
}

// ── Existing endpoints that also take the chain ─────────────────────────────────────────────
// GET /api/hands?…&chain=<url-encoded JSON Step[]>       (hand list for the Hands lower tab)
// GET /api/reports/graph?…&chain=<url-encoded JSON>     (Graph upper tab)
// The chain is the full chain; other filter params still work and are combined with AND.
// Both take `player_id` (default: the active hero); the chain is resolved for that player.
// The graph then plots that player's results; the hand list keeps its usual hero columns,
// restricted to the chain's hands. An invalid chain is a 422.
