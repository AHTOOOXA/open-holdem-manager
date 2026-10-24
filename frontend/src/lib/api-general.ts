/**
 * API client + types for the H2N-style General screen.
 *
 * GET /api/general?{filters}&workspace_id= → GeneralResponse. Cell ids come
 * from lib/h2n-layout.ts (GENERAL_CELL_IDS).
 *
 * The page always reads the real backend. The mock data (the numbers from
 * the reference screenshot) is only used when VITE_GENERAL_MOCK=1 is set
 * explicitly, e.g. to look at the layout without a database. Responses built
 * from mock data carry `mock: true` so the page can label them.
 *
 * Stat popup (page 1) and hands list (page 2):
 *   GET /api/general/cell/{cell_id}/detail → CellDetail
 *   GET /api/general/cell/{cell_id}/hands  → CellHands
 * Shapes mirror backend/app/api/general_popup.py.
 */

import { chainParam } from './reports/api';
import type { Step } from './reports/types';
import type { H2NCellInput, WireNumber } from './h2n-format';
import { GENERAL_CELL_IDS, SUMMARY_CELL_IDS } from './h2n-layout';

const BASE = '/api';

export const GENERAL_FORCE_MOCK = import.meta.env.VITE_GENERAL_MOCK === '1';

/**
 * One cell. Either raw counters (`cases`/`opps`, value = cases / opps * 100
 * computed client-side in that order) or a precomputed `value` + `sample`
 * (expressions; `sample` = the largest referenced sample, or null when the
 * stat has none). `value: null` means NaN ("--"); infinity is 'inf'/'-inf'.
 */
export interface GeneralCell extends H2NCellInput {
  value?: WireNumber;
  sample?: number | null;
  cases?: number;
  opps?: number;
  /** Same stat restricted to hands vs. the user; only relevant for opponents. */
  vs_user?: { value?: WireNumber; sample: number; cases?: number; opps?: number } | null;
}

export interface GeneralResponse {
  hands: number;
  /** Win rate in bb/100; null when there are no hands. */
  bb100: number | null;
  /** Selected player name and site, when the backend knows them. */
  player?: string | null;
  site?: string | null;
  /** The player the numbers are for (the workspace hero when none was asked for). */
  player_id?: number | null;
  is_hero?: boolean;
  cells: Record<string, GeneralCell>;
  /** True when the numbers are the built-in sample data, not the user's hands. */
  mock?: boolean;
}

export interface GeneralFilterParams {
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
  workspace_id?: number;
  /** Defaults to the workspace hero on the backend. */
  player_id?: number;
  /** Plain Reports steps (date / stakes / mode) used as the filter instead of the fields above
   *  (Statistics dashboards). Sent as JSON. */
  chain?: Step[];
}

function filterSearchParams(params: GeneralFilterParams): URLSearchParams {
  const sp = new URLSearchParams();
  if (params.stakes) sp.set('stakes', params.stakes);
  if (params.game_mode !== undefined && params.game_mode !== '') {
    sp.set('game_mode', params.game_mode === '__reg__' ? '' : params.game_mode);
  }
  if (params.date_from) sp.set('date_from', params.date_from);
  if (params.date_to) sp.set('date_to', params.date_to);
  if (params.workspace_id !== undefined) sp.set('workspace_id', String(params.workspace_id));
  if (params.player_id !== undefined) sp.set('player_id', String(params.player_id));
  if (params.chain && params.chain.length > 0) sp.set('chain', chainParam(params.chain));
  return sp;
}

async function errorText(res: Response, what: string): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === 'string') return `${what}: ${body.detail}`;
  } catch {
    // not JSON
  }
  return `${what}: ${res.status} ${res.statusText}`;
}

export function generalQueryKey(params: GeneralFilterParams) {
  return ['general', 'grid', params] as const;
}

export async function getGeneral(params: GeneralFilterParams = {}): Promise<GeneralResponse> {
  if (GENERAL_FORCE_MOCK) return getGeneralMock();
  const res = await fetch(`${BASE}/general?${filterSearchParams(params)}`);
  if (!res.ok) throw new Error(await errorText(res, 'General stats failed'));
  return res.json();
}

// ── Stat popup (page 1) ─────────────────────────────────────────────

/** cases / opps * 100; `value` null when opps == 0. */
export interface Ratio {
  value: number | null;
  cases: number;
  opps: number;
}

/**
 * Hero's next decision after the stat action. Fold / Call / Raise are shown
 * only when `show_fold_call_raise`, Bet / Check only when `show_bet_check`.
 */
export interface NextActions {
  fold: Ratio;
  call: Ratio;
  raise: Ratio;
  bet: Ratio;
  check: Ratio;
  show_fold_call_raise: boolean;
  show_bet_check: boolean;
}

/** One hand-value category of the stat street. index -1 = "Other". */
export interface StrengthBucket {
  index: number;
  key: string;
  label: string;
  /** Hand2Note's colour from the backend; the UI draws hvColor(key) instead. */
  color: string;
  weak: boolean;
  description: string;
  count: number;
  pct: number | null;
}

/**
 * Range histogram / strength bar: every category of the street in display
 * order (zeros included), "Other" only when it has hands.
 */
export interface Strength {
  street: string;
  total: number;
  weak: number;
  weak_pct: number | null;
  buckets: StrengthBucket[];
}

export interface PopupSummary {
  won_hand: Ratio;
  wtsd: Ratio;
  wsd: Ratio;
  next: NextActions;
}

/** One row of the Boards or Bet Sizes tab. Bet-size keys are opaque bucket keys. */
export interface SplitRow {
  key: string;
  label: string;
  value: number | null;
  cases: number;
  opps: number;
  strength: Strength | null;
  next: NextActions;
  /** Bet sizes: the measured action type of the bucket (bet / raise / call / fold). */
  action: string | null;
}

export interface CellDetail {
  cell_id: string;
  row: string;
  /** Matcher notation of the stat (e.g. "pre H:R[first_raise, last]; flop H:B"). */
  notation: string;
  /** Stat street: preflop / flop / turn / river. */
  street: string;
  player: string | null;
  player_id: number | null;
  value: number | null;
  cases: number;
  opps: number;
  /** Null for preflop stats. */
  strength: Strength | null;
  summary: PopupSummary;
  boards: SplitRow[];
  bet_sizes: SplitRow[];
  replayed: number;
  replay_failed: number;
  /** The cell as a Reports chain (filters + pos + row), for the popup's Reports-backed tabs. */
  chain: Step[];
}

export function cellDetailQueryKey(cellId: string, params: GeneralFilterParams) {
  return ['general', 'detail', cellId, params] as const;
}

export async function getCellDetail(cellId: string, params: GeneralFilterParams = {}): Promise<CellDetail> {
  const res = await fetch(
    `${BASE}/general/cell/${encodeURIComponent(cellId)}/detail?${filterSearchParams(params)}`,
  );
  if (!res.ok) throw new Error(await errorText(res, 'Stat detail failed'));
  return res.json();
}

// ── Hands list (page 2 and the Hands tab) ───────────────────────────

/**
 * One action in a street cell. `t`: X check, B bet, C call, R raise, F fold.
 * `amt_bb`: chips put in for B / C, the raise-to total for R, null for X / F.
 * `pos` is the actor's position (token colour); `hero` marks the stat
 * owner's actions (dashed underline).
 */
export interface ActionToken {
  t: string;
  amt_bb: number | null;
  allin: boolean;
  pos: string;
  hero: boolean;
  player: string;
}

export interface StreetCell {
  street: string;
  /** One group per distinct board (run it twice); empty preflop. */
  cards: string[][];
  /** Initial pot of the street in bb (gross on GG); null preflop. */
  pot_bb: number | null;
  pot: number | null;
  actions: ActionToken[];
}

export interface HandValueLabel {
  index: number;
  key: string;
  label: string;
  color: string;
}

export interface HandRow {
  hand_id: string;
  played_at: string | null;
  stakes: string | null;
  site_id: number | null;
  position: string | null;
  /** Hand value on the stat street, one label per board. */
  hand_value: HandValueLabel[];
  /** Sorted high first; pairs in hearts, diamonds, clubs, spades order. */
  hole_cards: string[];
  /** preflop, flop, turn, river; null after the player folded. */
  streets: (StreetCell | null)[];
  won: number | null;
  won_bb: number | null;
  ev_diff_bb: number | null;
  error: string | null;
}

export interface CellHands {
  cell_id: string;
  total: number;
  offset: number;
  limit: number;
  rows: HandRow[];
}

export type HandsSort = 'date' | 'won' | 'ev';
export type HandsOrder = 'desc' | 'asc';

/**
 * What the hands list is filtered to. Every field is optional and they
 * combine: a Boards mini-bar segment is `board` + `bucket`, a Bet Sizes one
 * `size` + `bucket`. No filter = every case of the stat (the Hands tab).
 */
export interface HandsFilter {
  /** Hand-value category key ("trash", "other", ...). */
  bucket?: string;
  /** Board texture key ("paired", ...). */
  board?: string;
  /** Bet-size bucket id. */
  size?: string;
}

/** A selection in the popup that opens the hands pane. */
export interface HandsSelection extends HandsFilter {
  /** Title pill of the hands pane ("Trash", "Paired · Trash"). */
  label: string;
}

/** Hard cap of the list per sort order (as in the reference app). */
export const HANDS_MAX_ROWS = 512;
export const HANDS_PAGE_SIZE = 50;

export interface HandsPageParams extends HandsFilter {
  offset?: number;
  limit?: number;
  sort?: HandsSort;
  order?: HandsOrder;
}

export function cellHandsQueryKey(
  cellId: string,
  params: GeneralFilterParams,
  filter: HandsFilter,
  sort: HandsSort,
  order: HandsOrder,
) {
  return ['general', 'hands', cellId, params, filter, sort, order] as const;
}

export async function getCellHands(
  cellId: string,
  params: GeneralFilterParams = {},
  page: HandsPageParams = {},
): Promise<CellHands> {
  const sp = filterSearchParams(params);
  if (page.bucket) sp.set('bucket', page.bucket);
  if (page.board) sp.set('board', page.board);
  if (page.size) sp.set('size', page.size);
  sp.set('offset', String(page.offset ?? 0));
  sp.set('limit', String(page.limit ?? HANDS_PAGE_SIZE));
  if (page.sort) sp.set('sort', page.sort);
  if (page.order) sp.set('order', page.order);
  const res = await fetch(`${BASE}/general/cell/${encodeURIComponent(cellId)}/hands?${sp}`);
  if (!res.ok) throw new Error(await errorText(res, 'Hands failed'));
  return res.json();
}

// ── Mock data (reference screenshot numbers) ───────────────────────

/** A big sample so nothing is dimmed; small samples are spelled out below. */
const BIG = 500;

const MOCK_VALUES: Record<string, GeneralCell> = {
  // Summary
  [SUMMARY_CELL_IDS.hands]: { value: 44210, sample: null },
  [SUMMARY_CELL_IDS.bb100]: { value: 9.83, sample: 44210 },
  [SUMMARY_CELL_IDS.vpip]: { value: 22, sample: 44100 },
  [SUMMARY_CELL_IDS.pfr]: { value: 17, sample: 44000 },

  // PRE-FLOP
  'preflop.open_raise.Total': { value: 26, sample: 30000 },
  'preflop.open_raise.EP': { value: 20, sample: 7000 },
  'preflop.open_raise.MP': { value: 20, sample: 7000 },
  'preflop.open_raise.CO': { value: 28, sample: 7000 },
  'preflop.open_raise.BTN': { value: 35, sample: 6000 },
  'preflop.open_raise.SB': { value: 39, sample: 3000 },
  'preflop.fold_to_3bet.Total': { value: 60, sample: 1300 },
  'preflop.fold_to_3bet.EP': { value: 59, sample: 150 },
  'preflop.fold_to_3bet.MP': { value: 63, sample: 220 },
  'preflop.fold_to_3bet.CO': { value: 63, sample: 300 },
  'preflop.fold_to_3bet.BTN': { value: 57, sample: 400 },
  'preflop.fold_to_3bet.SB': { value: 57, sample: 230 },
  'preflop.call_open_raise.Total': { value: 9.5, sample: 20000 },
  'preflop.call_open_raise.EP': { value: null, sample: 0 },
  'preflop.call_open_raise.MP': { value: 7.1, sample: 1500 },
  'preflop.call_open_raise.CO': { value: 7.7, sample: 2500 },
  'preflop.call_open_raise.BTN': { value: 7.8, sample: 3500 },
  'preflop.call_open_raise.SB': { value: 9.2, sample: 4500 },
  'preflop.call_open_raise.BB': { value: 12, sample: 5000 },
  'preflop.three_bet.Total': { value: 6, sample: 20000 },
  'preflop.three_bet.EP': { cases: 0, opps: 3 },
  'preflop.three_bet.MP': { value: 3.5, sample: 1500 },
  'preflop.three_bet.CO': { value: 5.1, sample: 2500 },
  'preflop.three_bet.BTN': { value: 6.2, sample: 3500 },
  'preflop.three_bet.SB': { value: 6.4, sample: 4500 },
  'preflop.three_bet.BB': { value: 7.4, sample: 5000 },
  'preflop.three_bet_ip.Total': { value: 6.1, sample: 8000 },
  'preflop.three_bet_ip.EP': { cases: 0, opps: 3 },
  'preflop.three_bet_ip.MP': { value: 3.5, sample: 1500 },
  'preflop.three_bet_ip.CO': { value: 5.1, sample: 2500 },
  'preflop.three_bet_ip.BTN': { value: 6.2, sample: 3500 },
  'preflop.three_bet_ip.BB': { value: 9.8, sample: 2000 },
  'preflop.three_bet_oop.Total': { value: 6.5, sample: 9000 },
  'preflop.three_bet_oop.SB': { value: 6.4, sample: 4500 },
  'preflop.three_bet_oop.BB': { value: 6.7, sample: 3000 },
  'preflop.four_bet.Total': { value: 18, sample: 1300 },
  'preflop.four_bet_range.Total': { value: 4.68, sample: 30000 },
  'preflop.four_bet_fold.Total': { value: 18, sample: 230 },
  'preflop.fold_to_4bet.Total': { value: 44, sample: 300 },
  'preflop.call_4bet.Total': { value: 29, sample: 300 },
  'preflop.five_bet.Total': { value: 41, sample: 100 },
  'preflop.limp.Total': { value: 0.4, sample: 25000 },
  'preflop.limp_fold.Total': { value: 90, sample: 60 },
  'preflop.squeeze.Total': { value: 4.6, sample: 3000 },

  // Steal
  'steal.steal.Total': { value: 37, sample: 9000 },
  'steal.steal.BTN': { value: 35, sample: 6000 },
  'steal.steal.SB': { value: 39, sample: 3000 },
  'steal.fold_to_3bet.Total': { value: 56, sample: 600 },
  'steal.fold_to_3bet.BTN': { value: 57, sample: 400 },
  'steal.fold_to_3bet.SB': { value: 56, sample: 230 },
  'steal.four_bet.Total': { value: 22, sample: 600 },
  'steal.four_bet.BTN': { value: 23, sample: 400 },
  'steal.four_bet.SB': { value: 20, sample: 230 },
  'steal.four_bet_fold.Total': { value: 30, sample: 20 },
  'steal.four_bet_fold.BTN': { cases: 3, opps: 11 },
  'steal.four_bet_fold.SB': { cases: 3, opps: 9 },
  'steal.vs_steal_fold.SB': { value: 83, sample: 2500 },
  'steal.vs_steal_fold.BB': { value: 75, sample: 4500 },
  'steal.vs_steal_call.SB': { value: 9.5, sample: 2500 },
  'steal.vs_steal_call.BB': { value: 15, sample: 4500 },
  'steal.vs_steal_3bet.SB': { value: 7.8, sample: 2500 },
  'steal.vs_steal_3bet.BB': { value: 9.6, sample: 4500 },

  // POSTFLOP
  'postflop.cbet.Flop': { value: 55, sample: 5000 },
  'postflop.cbet.Turn': { value: 41, sample: 1800 },
  'postflop.cbet.River': { value: 44, sample: 600 },
  'postflop.fold_to_cbet.Flop': { value: 61, sample: 2000 },
  'postflop.fold_to_cbet.Turn': { value: 29, sample: 500 },
  'postflop.fold_to_cbet.River': { value: 34, sample: 200 },
  'postflop.af.Flop': { value: 3.1, sample: BIG },
  'postflop.af.Turn': { value: 2, sample: BIG },
  'postflop.af.River': { value: 1.3, sample: BIG },
  'postflop.afq.Flop': { value: 35, sample: BIG },
  'postflop.afq.Turn': { value: 30, sample: BIG },
  'postflop.afq.River': { value: 21, sample: BIG },
  'postflop.donk.Flop': { value: 2.1, sample: 3000 },
  'postflop.donk.Turn': { value: 0.9, sample: 1000 },
  'postflop.donk.River': { value: 5.9, sample: 700 },
  'postflop.vs_cbet_raised.Fold': { value: 61, sample: 2000 },
  'postflop.vs_cbet_raised.Call': { value: 29, sample: 2000 },
  'postflop.vs_cbet_raised.Raise': { value: 10, sample: 2000 },
  'postflop.vs_cbet_3bet.Fold': { value: 50, sample: 200 },
  'postflop.vs_cbet_3bet.Call': { value: 29, sample: 200 },
  'postflop.vs_cbet_3bet.Raise': { value: 21, sample: 200 },
  'postflop.missed_cbet.Flop': { value: 45, sample: 5000 },
  'postflop.missed_cbet_ip.Flop': { value: 35, sample: 3000 },
  'postflop.missed_cbet_ip_fold.Turn': { value: 65, sample: 400 },
  'postflop.missed_cbet_oop.Flop': { value: 51, sample: 1500 },
  'postflop.missed_cbet_oop_fold.Flop': { value: 61, sample: 300 },
  'postflop.vs_missed_cbet.Flop': { value: 52, sample: 1500 },
  'postflop.vs_missed_cbet_bet_ip.Flop': { value: 57, sample: 600 },
  'postflop.vs_missed_cbet_check_fold_ip.Turn': { value: 60, sample: 200 },
  'postflop.vs_missed_cbet_bet_oop.Turn': { value: 51, sample: 500 },
  'postflop.vs_missed_cbet_check_fold_oop.Turn': { value: 62, sample: 200 },
  'postflop.wtsd.Total': { value: 26, sample: 12000 },
  'postflop.wsd.Total': { value: 58, sample: 3500 },
  'postflop.wwsf.Total': { value: 42, sample: 12000 },
};

/** Mock response with every layout id present (unknown ids fall back to "--"). */
export function getGeneralMock(): GeneralResponse {
  const cells: Record<string, GeneralCell> = {};
  for (const id of GENERAL_CELL_IDS) cells[id] = MOCK_VALUES[id] ?? { value: null, sample: 0 };
  return { hands: 44210, bb100: 9.83, player: null, site: null, cells, mock: true };
}
