/**
 * Line builder model (M8). A line is an ordered list of actions per street; `toDsl` (lib/lines/dsl.ts)
 * turns it into the matcher notation carried by the Reports `line` step. Spec: reports/04 §2.5 (Actions
 * tab) and §2.10 (Custom Filter), own words; docs/specs/QUERY-ENGINE-PRD.md (builder part).
 *
 * Matching (backend matcher, same as every General/Reports stat): on each street the actions must
 * appear in this order; between two listed actions only folds/checks may be skipped; every listed
 * street must match; `villain` actions with `same` bind one villain across the line (V1).
 */
import type { Pos, Street } from '../reports/types';

export type LineActor = 'hero' | 'villain';
export type LineActionType = 'fold' | 'check' | 'call' | 'bet' | 'raise';
/** Raise kinds the matcher can express directly. */
export type RaiseKind = 'any' | 'open' | '3bet';

export interface LineAction {
  id: string; // stable UI key
  street: Street;
  who: LineActor;
  a: LineActionType;
  raise?: RaiseKind; // only for 'raise' (open = first raise "fr", 3bet = "3b")
  pos?: Pos[]; // actor's position group(s); empty/undefined = any
  /** villain only: the same villain as the line's other bound villain actions (V1). Default true. */
  same?: boolean;
  /** "was the last action of this player on this street" */
  last?: boolean;
}

export interface Line {
  actions: LineAction[];
}

/**
 * Filter-dialog Actions tab (H2N's per-street "action rows"): rows on one street are OR'd, streets
 * AND'd; a row is hero's whole action on that street, e.g. "Bet Call" = hero bets, a villain raises,
 * hero calls. Converted to the same `line` step (rows joined with "|").
 */
export type StreetRow =
  | 'raise' | 'raise_fold' | 'raise_call' | 'raise_raise' | 'fold'
  | 'call' | 'call_fold' | 'call_call' | 'call_raise'
  | 'bet' | 'bet_fold' | 'bet_call' | 'bet_raise'
  | 'check' | 'check_fold' | 'check_call' | 'check_raise';

export interface ActionRows {
  streets: Partial<Record<Street, StreetRow[]>>; // preflop: no bet_* / check_* rows
  /** per street: "Selected action was the last action on this street" */
  last: Partial<Record<Street, boolean>>;
}

// ── Hand export (M8) ─────────────────────────────────────────────────────────────────────
// GET /api/hands/export?<every /api/hands filter param, incl. chain, marked, tag_ids, player_id>
//     &sort=&order=&format=txt  → text/plain attachment "OHM hands.txt": the original hand
//     histories of the whole filtered list (not just the page), in list order, separated by two
//     blank lines; at most 100,000 hands (header `X-OHM-Truncated: 1` when capped).
// Copy Hand History uses the hand detail's `raw_text` (GET /api/hands/{id}).
