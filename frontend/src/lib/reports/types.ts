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
  | { k: 'stakes'; v: string[] } // hands.stakes, e.g. "NL10"
  | { k: 'mode'; v: 'fast' | 'regular' } // fast-fold (Rush & Cash / Zoom) vs regular tables
  | { k: 'tsize'; v: number[] } // table size (max seats), e.g. [6]
  | { k: 'date'; from?: string; to?: string } // ISO dates (inclusive), local day boundaries
  | { k: 'hour'; v: number[] } // local start hour 0-23
  | { k: 'stack'; lo: number; hi: number | null } // hero starting stack in bb, [lo, hi)
  | { k: 'game'; stakes: string; mode: string; tsize: number } // a Results row
  | { k: 'cells'; v: string[] } // preflop hand classes, e.g. "AKs", "QQ", "T9o"
  | { k: 'hv'; street: Street; cats: string[] } // hand-value categories (backend keys)
  // ── spot steps (order matters; each moves the hit point) ──
  | { k: 'row'; key: string } // a named quick filter (General row key, e.g. "P01" = Raise 1st In)
  | { k: 'next'; street: Street; a: NextAction } // a Next Actions row after the current hit point
  | { k: 'faced'; street: Street; a: FacedAction } // a Faced Next row after the current hit point
  | { k: 'betsize'; bucket: string } // a Bet Sizing bucket of the current hit action
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
  | 'stack_sizes' | 'hour_of_day' | 'table_size';

export type ValueFormat = 'count' | 'pct' | 'money' | 'bb' | 'bb100' | 'bbh' | 'ratio';

export interface SplitColumn {
  id: string;
  caption: string; // full caption (header tooltip, column picker)
  abbrev?: string; // short header text
  format: ValueFormat;
  winnings?: boolean; // coloured money-style (> 0 pos, <= 0 neg)
  /** Sample-size column id for this column's small-sample dimming (e.g. "opps"). */
  sample?: string;
}

export interface SplitRow {
  key: string;
  caption: string; // row name = next page title (named spot when the chain has one)
  filter: Step; // appended to the next page's inherited chain when the row is clicked
  values: Record<string, number | null>;
  /** Lower tab to select on the page this row opens (Hand2Note: Faced Next after a hero action). */
  open_tab?: 'next_actions' | 'faced_next';
}

export interface SplitResponse {
  type: SplitType;
  entry_header: string; // first column header, e.g. "Position", "Next Actions"
  columns: SplitColumn[];
  rows: SplitRow[]; // default order (section 4/5 of the spec); empty = "No results yet"
  summary: Record<string, number | null> | null; // only when rows.length > 1
  total_hands: number; // hands of the whole dashboard before page filters (Hits per 1000 base)
}

export interface SplitQuery extends ReportQuery {
  type: SplitType;
}

// ── POST /api/reports/spot ─ page summary + Stats upper tab ("smart reports") ─────────────

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
}

export interface SpotResponse {
  hands: number; // hands matching the chain (cases at the hit point)
  kind: SpotKind;
  hit_label: string | null; // e.g. "Continuation Bet"
  stats: SpotStat[];
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
  pct: number; // share of known-cards hands on that street
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
