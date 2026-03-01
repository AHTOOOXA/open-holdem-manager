const BASE = '/api';

// ── Workspace ID injection ──────────────────────────────────────────

let _getWorkspaceId: () => number = () => {
  const stored = localStorage.getItem('ohm_active_workspace_id');
  return stored ? parseInt(stored, 10) : 1;
};

export function setWorkspaceIdGetter(fn: () => number) {
  _getWorkspaceId = fn;
}

function _addWorkspaceParam(sp: URLSearchParams) {
  sp.set('workspace_id', String(_getWorkspaceId()));
}

/** Translate game_mode filter: '__reg__' → '' (empty = Regular), undefined → skip */
function setGameModeParam(sp: URLSearchParams, gameMode: string | undefined) {
  if (gameMode !== undefined) {
    sp.set('game_mode', gameMode === '__reg__' ? '' : gameMode);
  }
}

/** Set position param, normalizing to uppercase (DB stores EP/MP/CO/BTN/SB/BB) */
function setPositionParam(sp: URLSearchParams, position: string | undefined) {
  if (position) sp.set('position', position.toUpperCase());
}

export interface ImportResult {
  imported: number;
  duplicates: number;
  errors: number;
  error_details: string[];
  elapsed_ms?: number;
  hands_per_sec?: number;
  parse_ms?: number;
  stats_ms?: number;
  equity_ms?: number;
  db_ms?: number;
}

export interface Settings {
  hero_username: string;
  hero_site: string;
}

export interface GraphPoint {
  hand_number: number;
  played_at: string;
  cumulative_bb: number;
  cumulative_ev_bb: number;
  cumulative_rake_bb: number;
  cumulative_jackpot_bb: number;
  cumulative_showdown_bb: number;
  cumulative_nonshowdown_bb: number;
  cumulative_usd: number;
  cumulative_ev_usd: number;
  cumulative_rake_usd: number;
  cumulative_jackpot_usd: number;
  cumulative_showdown_usd: number;
  cumulative_nonshowdown_usd: number;
}

export interface VarianceStats {
  sd_bb: number;
  sd_bb100: number;
  winrate_bb100: number;
  ci_lower_bb100: number;
  ci_upper_bb100: number;
  n: number;
}

export interface SessionMarker {
  start_hand: number;
  end_hand: number;
  start_time: string;
  end_time: string;
}

export interface GraphResponse {
  points: GraphPoint[];
  sessions: SessionMarker[];
  variance: VarianceStats | null;
}

export interface StatValue {
  value: number | null;
  sample: number;
}

export interface PositionalStats {
  total: StatValue;
  ep: StatValue;
  mp: StatValue;
  co: StatValue;
  btn: StatValue;
  sb: StatValue;
  bb: StatValue;
}

export interface HeroStats {
  hands: number;
  win_rate_bb100: number | null;
  win_rate_ev_bb100: number | null;
  vpip: PositionalStats;
  pfr: PositionalStats;
  open_raise: PositionalStats;
  three_bet: PositionalStats;
  three_bet_ip: PositionalStats;
  three_bet_oop: PositionalStats;
  four_bet: PositionalStats;
  five_bet: StatValue;
  fold_to_3bet: PositionalStats;
  fold_to_4bet: PositionalStats;
  call_open_raise: PositionalStats;
  limp: PositionalStats;
  limp_fold: StatValue;
  squeeze: StatValue;
  four_bet_range: StatValue;
  four_bet_fold: StatValue;
  call_4bet: StatValue;
  bb_defense: StatValue;
  iso_raise: StatValue;
  fold_to_squeeze: StatValue;
  steal: PositionalStats;
  fold_to_3bet_steal: PositionalStats;
  four_bet_steal: PositionalStats;
  four_bet_fold_steal: PositionalStats;
  vs_steal_fold: PositionalStats;
  vs_steal_call: PositionalStats;
  vs_steal_3bet: PositionalStats;
  cbet_flop: PositionalStats;
  cbet_turn: PositionalStats;
  cbet_river: PositionalStats;
  fold_to_cbet_flop: PositionalStats;
  fold_to_cbet_turn: PositionalStats;
  fold_to_cbet_river: PositionalStats;
  donk_bet_flop: StatValue;
  donk_bet_turn: StatValue;
  donk_bet_river: StatValue;
  fold_cbet_flop_raised: StatValue;
  call_cbet_flop_raised: StatValue;
  raise_cbet_flop_raised: StatValue;
  fold_cbet_flop_3bet: StatValue;
  call_cbet_flop_3bet: StatValue;
  raise_cbet_flop_3bet: StatValue;
  af_flop: StatValue;
  af_turn: StatValue;
  af_river: StatValue;
  afq_flop: StatValue;
  afq_turn: StatValue;
  afq_river: StatValue;
  missed_cbet_flop: StatValue;
  missed_cbet_flop_ip: StatValue;
  missed_cbet_flop_oop: StatValue;
  missed_cbet_fold_ip: StatValue;
  missed_cbet_fold_oop: StatValue;
  missed_cbet_turn: StatValue;
  vs_missed_cbet: StatValue;
  vs_missed_cbet_bet_ip: StatValue;
  vs_missed_cbet_check_fold_ip: StatValue;
  vs_missed_cbet_bet_oop_turn: StatValue;
  vs_missed_cbet_check_fold_oop: StatValue;
  wtsd: StatValue;
  wsd: StatValue;
  wwsf: StatValue;
}

export interface ImportProgress {
  type: 'start' | 'progress' | 'done';
  total_hands?: number;
  files?: number;
  processed?: number;
  total?: number;
  imported?: number;
  duplicates?: number;
  errors?: number;
  error_details?: string[];
  elapsed_ms?: number;
  hands_per_sec?: number;
  parse_ms?: number;
  stats_ms?: number;
  equity_ms?: number;
  db_ms?: number;
}

export async function uploadFiles(files: File[]): Promise<ImportResult> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f);
  }
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/files?${sp}`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Import failed: ${res.statusText}`);
  return res.json();
}

export async function uploadFilesStream(
  files: File[],
  onProgress: (progress: ImportProgress) => void,
): Promise<ImportResult> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f);
  }
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/files/stream?${sp}`, { method: 'POST', body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Import failed: ${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult: ImportResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      const msg: ImportProgress = JSON.parse(line);
      onProgress(msg);
      if (msg.type === 'done') {
        finalResult = {
          imported: msg.imported ?? 0,
          duplicates: msg.duplicates ?? 0,
          errors: msg.errors ?? 0,
          error_details: msg.error_details ?? [],
          elapsed_ms: msg.elapsed_ms,
          hands_per_sec: msg.hands_per_sec,
          parse_ms: msg.parse_ms,
          stats_ms: msg.stats_ms,
          equity_ms: msg.equity_ms,
          db_ms: msg.db_ms,
        };
      }
    }
  }

  return finalResult ?? { imported: 0, duplicates: 0, errors: 0, error_details: [] };
}

export async function getHeroStats(params?: {
  position?: string;
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
  last_n?: number;
}): Promise<HeroStats> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.last_n) sp.set('last_n', String(params.last_n));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/stats/hero?${sp}`);
  if (!res.ok) throw new Error(`Stats failed: ${res.statusText}`);
  return res.json();
}

export async function getGraphData(params?: {
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
  last_n?: number;
}): Promise<GraphResponse> {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.last_n) sp.set('last_n', String(params.last_n));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/reports/graph?${sp}`);
  if (!res.ok) throw new Error(`Graph failed: ${res.statusText}`);
  return res.json();
}

export async function getSettings(): Promise<Settings> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/settings?${sp}`);
  if (!res.ok) throw new Error(`Settings failed: ${res.statusText}`);
  return res.json();
}

export async function updateSettings(settings: Settings): Promise<Settings> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/settings?${sp}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.statusText}`);
  return res.json();
}

export interface HealthResponse {
  status: string;
  hands: number;
  rebuilding: boolean;
  rebuild_progress?: { processed: number; total: number };
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

// ── Hand Browser Types ──────────────────────────────────────────────

export interface ActionItem {
  a: string;       // R, B, C, X
  v?: number;      // amount in BB
  h: boolean;      // is hero
}

export interface HandSummary {
  id: string;
  played_at: string;
  stakes: string;
  bb_amount: number;
  position: string;
  card1: string | null;
  card2: string | null;
  won_bb: number;
  all_in_ev_bb: number;
  tags: string[];
  preflop_actions: ActionItem[];
  flop_cards: string[];
  flop_pot: number;
  flop_actions: ActionItem[];
  turn_card: string | null;
  turn_pot: number;
  turn_actions: ActionItem[];
  river_card: string | null;
  river_pot: number;
  river_actions: ActionItem[];
}

export interface HandListResponse {
  hands: HandSummary[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface HandPlayerDetail {
  seat: number;
  position: string;
  username: string;
  stack_bb: number;
  card1: string | null;
  card2: string | null;
  won_bb: number;
  is_hero: boolean;
  player_type: string;
}

export interface HandAction {
  street: string;
  player: string;
  position: string;
  action: string;
  amount_bb: number | null;
  is_all_in: boolean;
  is_hero: boolean;
}

export interface BoardCards {
  flop: string[];
  turn: string[];
  river: string[];
}

export interface HandDetail {
  id: string;
  played_at: string;
  stakes: string;
  bb_amount: number;
  table_name: string | null;
  table_size: number;
  raw_text: string | null;
  players: HandPlayerDetail[];
  board: BoardCards;
  actions: HandAction[];
  tags: string[];
  note: string | null;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface HandListParams {
  page?: number;
  per_page?: number;
  sort?: string;
  order?: string;
  position?: string;
  stakes?: string;
  result?: string;
  tags?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  stat_flag?: string[];
  stat_key?: string;
  player_id?: number;
}

export async function getHands(params?: HandListParams): Promise<HandListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set('page', String(params.page));
  if (params?.per_page) sp.set('per_page', String(params.per_page));
  if (params?.sort) sp.set('sort', params.sort);
  if (params?.order) sp.set('order', params.order);
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.result) sp.set('result', params.result);
  if (params?.tags) sp.set('tags', params.tags);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.search) sp.set('search', params.search);
  if (params?.stat_flag) {
    for (const flag of params.stat_flag) sp.append('stat_flag', flag);
  }
  if (params?.stat_key) sp.set('stat_key', params.stat_key);
  if (params?.player_id) sp.set('player_id', String(params.player_id));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands?${sp}`);
  if (!res.ok) throw new Error(`Hands failed: ${res.statusText}`);
  return res.json();
}

export async function getHandDetail(handId: string): Promise<HandDetail> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}?${sp}`);
  if (!res.ok) throw new Error(`Hand detail failed: ${res.statusText}`);
  return res.json();
}

export async function addTag(handId: string, tag: string): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/tags?${sp}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag }),
  });
  if (!res.ok) throw new Error(`Add tag failed: ${res.statusText}`);
}

export async function removeTag(handId: string, tag: string): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/tags/${encodeURIComponent(tag)}?${sp}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Remove tag failed: ${res.statusText}`);
}

export async function getTags(): Promise<TagCount[]> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/tags?${sp}`);
  if (!res.ok) throw new Error(`Tags failed: ${res.statusText}`);
  return res.json();
}

export async function updateNote(handId: string, note: string): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/note?${sp}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Update note failed: ${res.statusText}`);
}

export async function deleteNote(handId: string): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/note?${sp}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Delete note failed: ${res.statusText}`);
}

// ── Range Page Types ────────────────────────────────────────────────

export interface ComboStats {
  combo: string;
  hands: number;
  vpip: number;
  pfr: number;
  three_bet: number;
  won_bb: number;
  ev_bb: number;
  bb_per_100: number;
  ev_bb_per_100: number;
  wtsd: number;
  wtsd_opp: number;
  wsd: number;
  wsd_opp: number;
}

export interface RangeResponse {
  combos: ComboStats[];
  total_hands: number;
}

export async function getRangeStats(params?: {
  position?: string;
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
}): Promise<RangeResponse> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/stats/range?${sp}`);
  if (!res.ok) throw new Error(`Range stats failed: ${res.statusText}`);
  return res.json();
}

// ── Results Dashboard Types ──────────────────────────────────────────

export interface FilterOptions {
  stakes: string[];
  game_modes: string[];
  date_range: { min?: string; max?: string };
}

export interface StakeBreakdown {
  stakes: string;
  game_mode: string;
  bb_amount: number;
  hands: number;
  won_bb: number;
  won_usd: number;
  ev_bb: number;
  rake_bb: number;
  rake_usd: number;
  jackpot_bb: number;
  jackpot_usd: number;
  bb_per_100: number;
  ev_bb_per_100: number;
}

export interface MonthBreakdown {
  month: string;
  hands: number;
  won_bb: number;
  won_usd: number;
  ev_bb: number;
  rake_bb: number;
  rake_usd: number;
  jackpot_bb: number;
  jackpot_usd: number;
  bb_per_100: number;
  ev_bb_per_100: number;
}

export interface PositionBreakdown {
  position: string;
  hands: number;
  won_bb: number;
  won_usd: number;
  ev_bb: number;
  rake_bb: number;
  rake_usd: number;
  jackpot_bb: number;
  jackpot_usd: number;
  bb_per_100: number;
  ev_bb_per_100: number;
}

export interface ResultsBreakdown {
  by_stakes: StakeBreakdown[];
  by_month: MonthBreakdown[];
  by_position: PositionBreakdown[];
}

export async function getFilterOptions(): Promise<FilterOptions> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/reports/filter-options?${sp}`);
  if (!res.ok) throw new Error(`Filter options failed: ${res.statusText}`);
  return res.json();
}

export async function getResultsBreakdown(params?: {
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
  last_n?: number;
}): Promise<ResultsBreakdown> {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.last_n) sp.set('last_n', String(params.last_n));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/reports/breakdown?${sp}`);
  if (!res.ok) throw new Error(`Breakdown failed: ${res.statusText}`);
  return res.json();
}

// ── Cash Drop Types ──────────────────────────────────────────────────

export interface CashDropSummary {
  total_hands: number;
  cash_drop_hands: number;
  eligible_hands: number;
  pots_won: number;
  total_paid_bb: number;
  total_paid_usd: number;
  total_received_bb: number;
  total_received_usd: number;
  net_bb: number;
  net_usd: number;
  frequency: number;
  avg_drop_bb: number;
  hero_vpip_pct: number | null;
  hero_pfr_pct: number | null;
  hero_three_bet_pct: number | null;
  hero_limp_pct: number | null;
  hero_allin_raise_pct: number | null;
  hero_allin_call_pct: number | null;
  hero_wtsd_pct: number | null;
  hero_wsd_pct: number | null;
  hero_won_bb: number | null;
  hero_bb100: number | null;
}

export interface CashDropTypeBreakdown {
  drop_bb: number;
  count: number;
  total_usd: number;
}

export interface CashDropRangeCategory {
  label: string;
  combos: ComboStats[];
  total_hands: number;
}

export interface CashDropFieldStats {
  total_players: number;
  avg_players_per_pot: number | null;
  vpip_pct: number | null;
  pfr_pct: number | null;
  three_bet_pct: number | null;
  limp_pct: number | null;
  allin_raise_pct: number | null;
  allin_call_pct: number | null;
  wtsd_pct: number | null;
  wsd_pct: number | null;
  avg_won_bb: number | null;
}

export interface CashDropResponse {
  summary: CashDropSummary;
  field: CashDropFieldStats | null;
  by_type: CashDropTypeBreakdown[];
  ranges: CashDropRangeCategory[];
}

export async function getCashDropStats(params?: {
  stakes?: string;
  date_from?: string;
  date_to?: string;
}): Promise<CashDropResponse> {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/reports/cash-drop?${sp}`);
  if (!res.ok) throw new Error(`Cash drop stats failed: ${res.statusText}`);
  return res.json();
}

// ── Session Types ────────────────────────────────────────────────────

export interface SessionSummary {
  session_index: number;
  start_time: string;
  end_time: string;
  hands: number;
  duration_minutes: number;
  stakes: string[];
  won_bb: number;
  won_usd: number;
  ev_bb: number;
  ev_usd: number;
  rake_bb: number;
  rake_usd: number;
  bb_per_100: number;
  ev_bb_per_100: number;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface SessionGraphPoint {
  hand_number: number;
  played_at: string;
  cumulative_bb: number;
  cumulative_ev_bb: number;
  cumulative_showdown_bb: number;
  cumulative_nonshowdown_bb: number;
  cumulative_usd: number;
  cumulative_ev_usd: number;
  cumulative_showdown_usd: number;
  cumulative_nonshowdown_usd: number;
}

export interface SessionStats extends SessionSummary {
  hands_per_hour: number;
  usd_per_hour: number;
  bb_per_hour: number;
  vpip_pct: number | null;
  pfr_pct: number | null;
  three_bet_pct: number | null;
  cbet_flop_pct: number | null;
  wtsd_pct: number | null;
  wsd_pct: number | null;
  wwsf_pct: number | null;
  steal_pct: number | null;
  afq_flop_pct: number | null;
}

export interface SessionBigHand {
  hand_id: string;
  played_at: string;
  won_bb: number;
  won_usd: number;
  position: string;
  card1: string | null;
  card2: string | null;
  stakes: string;
}

export interface SessionDetailResponse {
  session_index: number;
  stats: SessionStats;
  graph: SessionGraphPoint[];
  biggest_wins: SessionBigHand[];
  biggest_losses: SessionBigHand[];
}

export async function getSessions(): Promise<SessionListResponse> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/sessions?${sp}`);
  if (!res.ok) throw new Error(`Sessions failed: ${res.statusText}`);
  return res.json();
}

export async function getSessionDetail(index: number): Promise<SessionDetailResponse> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/sessions/${index}?${sp}`);
  if (!res.ok) throw new Error(`Session detail failed: ${res.statusText}`);
  return res.json();
}

// ── Stat Detail Types ────────────────────────────────────────────────

export interface StatDetailHand {
  hand_id: string;
  played_at: string;
  position: string;
  card1: string | null;
  card2: string | null;
  action_taken: boolean;
  won_bb: number;
  stakes: string;
  all_in_ev_bb: number;
  bb_amount: number;
  board_flop: string[];
  board_turn: string | null;
  board_river: string | null;
  preflop_actions: ActionItem[];
  flop_actions: ActionItem[];
  flop_pot: number;
  turn_actions: ActionItem[];
  turn_pot: number;
  river_actions: ActionItem[];
  river_pot: number;
  key_street_actions: ActionItem[];
}

export interface StatDetailHandsResponse {
  stat_key: string;
  stat_name: string;
  action_count: number;
  opportunity_count: number;
  key_street: string | null;
  hands: StatDetailHand[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export async function getStatDetailHands(
  statKey: string,
  params?: {
    position?: string;
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    per_page?: number;
  },
  signal?: AbortSignal,
): Promise<StatDetailHandsResponse> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.page) sp.set('page', String(params.page));
  if (params?.per_page) sp.set('per_page', String(params.per_page));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/hands?${sp}`, { signal });
  if (!res.ok) throw new Error(`Stat detail failed: ${res.statusText}`);
  return res.json();
}

// ── Stat Trend / Analysis Types ──────────────────────────────────────

export interface TrendPoint {
  hand_number: number;
  rolling_pct: number;
  sample: number;
}

export interface StatTrendResponse {
  stat_key: string;
  overall_pct: number;
  points: TrendPoint[];
}

export interface ResponseDistributionData {
  fold_count: number;
  call_count: number;
  raise_count: number;
  fold_pct: number;
  call_pct: number;
  raise_pct: number;
  total: number;
}

export interface StatAnalysisResponse {
  stat_key: string;
  response_distribution: ResponseDistributionData | null;
}

export async function getStatTrend(
  statKey: string,
  params?: {
    position?: string;
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
    bucket_size?: number;
  },
  signal?: AbortSignal,
): Promise<StatTrendResponse> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.game_mode !== undefined) sp.set('game_mode', params.game_mode === '__reg__' ? '' : params.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.bucket_size) sp.set('bucket_size', String(params.bucket_size));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/trend?${sp}`, { signal });
  if (!res.ok) throw new Error(`Trend failed: ${res.statusText}`);
  return res.json();
}

export async function getStatAnalysis(
  statKey: string,
  params?: {
    position?: string;
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  },
  signal?: AbortSignal,
): Promise<StatAnalysisResponse> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.game_mode !== undefined) sp.set('game_mode', params.game_mode === '__reg__' ? '' : params.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/analysis?${sp}`, { signal });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

// ── Drift Detection Types ────────────────────────────────────────────

export interface DriftStat {
  stat: string;
  lifetime_avg: number;
  window_avg: number;
  lifetime_n: number;
  window_n: number;
  drift_pct: number;
  ci_lower: number;
  ci_upper: number;
  direction: string;
  interpretation: string;
}

export interface DriftResponse {
  stats: DriftStat[];
  window_hands: number;
  total_hands: number;
}

export async function getDrift(params?: {
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
}): Promise<DriftResponse> {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/reports/drift?${sp}`);
  if (!res.ok) throw new Error(`Drift failed: ${res.statusText}`);
  return res.json();
}

// ── Player Types ──────────────────────────────────────────────────────

export interface PlayerSummary {
  id: number;
  username: string;
  player_type: string;
  hands: number;
  vpip: number | null;
  pfr: number | null;
  three_bet: number | null;
  af: number | null;
  last_seen: string | null;
  stakes: string[];
}

export interface PlayerListResponse {
  players: PlayerSummary[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PlayerListParams {
  search?: string;
  player_type?: string;
  min_hands?: number;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  per_page?: number;
}

export interface PlayerHeader {
  id: number;
  username: string;
  player_type: string;
  hands: number;
  first_seen: string | null;
  last_seen: string | null;
  stakes: string[];
  notes: string | null;
  color_tag: string | null;
}

export interface HeadToHeadRow {
  hero_position: string;
  hands: number;
  hero_won_bb: number;
  bb_per_100: number;
}

export interface HeadToHeadResponse {
  rows: HeadToHeadRow[];
  total_hands: number;
  total_won_bb: number;
  overall_bb_per_100: number;
}

export async function getPlayers(params?: PlayerListParams): Promise<PlayerListResponse> {
  const sp = new URLSearchParams();
  if (params?.search) sp.set('search', params.search);
  if (params?.player_type) sp.set('player_type', params.player_type);
  if (params?.min_hands !== undefined) sp.set('min_hands', String(params.min_hands));
  if (params?.sort_by) sp.set('sort_by', params.sort_by);
  if (params?.sort_dir) sp.set('sort_dir', params.sort_dir);
  if (params?.page) sp.set('page', String(params.page));
  if (params?.per_page) sp.set('per_page', String(params.per_page));
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/players?${sp}`);
  if (!res.ok) throw new Error(`Players failed: ${res.statusText}`);
  return res.json();
}

export async function getPlayer(playerId: number): Promise<PlayerHeader> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/players/${playerId}?${sp}`);
  if (!res.ok) throw new Error(`Player failed: ${res.statusText}`);
  return res.json();
}

export async function getPlayerStats(playerId: number, params?: {
  position?: string;
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
}): Promise<HeroStats> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/players/${playerId}/stats?${sp}`);
  if (!res.ok) throw new Error(`Player stats failed: ${res.statusText}`);
  return res.json();
}

export async function getHeadToHead(playerId: number): Promise<HeadToHeadResponse> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/players/${playerId}/head-to-head?${sp}`);
  if (!res.ok) throw new Error(`H2H failed: ${res.statusText}`);
  return res.json();
}

export async function updatePlayerNotes(playerId: number, data: { notes?: string; color_tag?: string }): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/players/${playerId}/notes?${sp}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Update player notes failed: ${res.statusText}`);
}

// ── Population Types ──────────────────────────────────────────────────

export interface PopulationOverview {
  player_count: number;
  observation_count: number;
  date_min: string | null;
  date_max: string | null;
}

export interface PositionStat {
  position: string;
  value: number | null;
  sample: number;
}

export interface PreflopResponse {
  open_raise: PositionStat[];
  three_bet_matrix: unknown[];
  fold_to_3bet_matrix: unknown[];
  vpip_by_position: PositionStat[];
  pfr_by_position: PositionStat[];
  limp_by_position: PositionStat[];
  squeeze: PositionStat | null;
  four_bet: PositionStat[];
}

export interface SegmentStats {
  player_type: string;
  count: number;
  avg_hands: number;
  vpip: number | null;
  pfr: number | null;
  three_bet: number | null;
  af: number | null;
  wtsd: number | null;
  wwsf: number | null;
}

export interface SegmentsResponse {
  segments: SegmentStats[];
}

export interface PostflopLineStat {
  street: string;
  stat: string;
  pot_type: string;
  value: number | null;
  sample: number;
}

export interface PostflopResponse {
  lines: PostflopLineStat[];
}

export interface ComparisonStat {
  stat: string;
  hero_value: number | null;
  pop_value: number | null;
  diff: number | null;
}

export interface ComparisonResponse {
  stats: ComparisonStat[];
}

export interface PotTypeStat {
  pot_type: string;
  hands: number;
  cbet_flop: number | null;
  fold_to_cbet_flop: number | null;
  wtsd: number | null;
}

export interface PotTypesResponse {
  pot_types: PotTypeStat[];
}

export interface ShowdownPositionStat {
  position: string;
  wtsd: number | null;
  wsd: number | null;
  wwsf: number | null;
  sample: number;
}

export interface ShowdownResponse {
  by_position: ShowdownPositionStat[];
  af_flop: number | null;
  af_turn: number | null;
  af_river: number | null;
  afq_flop: number | null;
  afq_turn: number | null;
  afq_river: number | null;
}

export interface HuMwStat {
  category: string;
  hands: number;
  vpip: number | null;
  pfr: number | null;
  cbet_flop: number | null;
  fold_to_cbet_flop: number | null;
  wtsd: number | null;
}

export interface HuMwResponse {
  stats: HuMwStat[];
}

export interface PopulationFilterParams {
  stakes?: string;
  date_from?: string;
  date_to?: string;
  min_hands?: number;
  exclude_hero?: boolean;
  player_type?: string;
  exclude_identity_ids?: string;
  exclude_tags?: string;
}

function _buildPopParams(params?: PopulationFilterParams): URLSearchParams {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.min_hands !== undefined) sp.set('min_hands', String(params.min_hands));
  if (params?.exclude_hero !== undefined) sp.set('exclude_hero', String(params.exclude_hero));
  if (params?.player_type) sp.set('player_type', params.player_type);
  if (params?.exclude_identity_ids) sp.set('exclude_identity_ids', params.exclude_identity_ids);
  if (params?.exclude_tags) sp.set('exclude_tags', params.exclude_tags);
  _addWorkspaceParam(sp);
  return sp;
}

export async function getPopulationOverview(params?: PopulationFilterParams): Promise<PopulationOverview> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/overview?${sp}`);
  if (!res.ok) throw new Error(`Population overview failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationPreflop(params?: PopulationFilterParams): Promise<PreflopResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/preflop?${sp}`);
  if (!res.ok) throw new Error(`Population preflop failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationSegments(params?: PopulationFilterParams): Promise<SegmentsResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/segments?${sp}`);
  if (!res.ok) throw new Error(`Population segments failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationPostflop(params?: PopulationFilterParams): Promise<PostflopResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/postflop?${sp}`);
  if (!res.ok) throw new Error(`Population postflop failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationPotTypes(params?: PopulationFilterParams): Promise<PotTypesResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/pot-types?${sp}`);
  if (!res.ok) throw new Error(`Population pot types failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationShowdown(params?: PopulationFilterParams): Promise<ShowdownResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/showdown?${sp}`);
  if (!res.ok) throw new Error(`Population showdown failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationHuVsMw(params?: PopulationFilterParams): Promise<HuMwResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/hu-vs-mw?${sp}`);
  if (!res.ok) throw new Error(`Population HU vs MW failed: ${res.statusText}`);
  return res.json();
}

export async function getPopulationComparison(params?: PopulationFilterParams): Promise<ComparisonResponse> {
  const sp = _buildPopParams(params);
  const res = await fetch(`${BASE}/population/comparison?${sp}`);
  if (!res.ok) throw new Error(`Population comparison failed: ${res.statusText}`);
  return res.json();
}

export async function clearDatabase(): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/clear?${sp}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Clear failed: ${res.statusText}`);
}

export async function exportDb(): Promise<void> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/export?${sp}`);
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition');
  const match = disposition?.match(/filename="?(.+?)"?$/);
  const filename = match?.[1] ?? 'ohm-backup.duckdb';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function importDb(file: File): Promise<{ status: string; hands: number }> {
  const form = new FormData();
  form.append('file', file);
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/database?${sp}`, { method: 'POST', body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Import DB failed: ${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`);
  }
  return res.json();
}

export async function rebuildHands(): Promise<{ status: string; total?: number }> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/import/rebuild?${sp}`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Rebuild failed: ${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`);
  }
  return res.json();
}

// ── Widget API Types ──────────────────────────────────────────────────

export interface EvScenario {
  label: string;
  bb_per_100: number;
  hands: number;
  total_won_bb: number;
}

export interface EvBreakdownResponse {
  stat_key: string;
  scenarios: EvScenario[];
  overall_bb_per_100: number;
  overall_hands: number;
}

export interface SizingBucket {
  size_bb: number;
  count: number;
  pct: number;
}

export interface SizingResponse {
  buckets: SizingBucket[];
  avg_size_bb: number | null;
  median_size_bb: number | null;
  total: number;
}

export interface FoldEquityResponse {
  fold_pct: number;
  fold_count: number;
  total: number;
}

export interface ContextBucket {
  label: string;
  actions: number;
  opportunities: number;
  pct: number | null;
}

export interface ByContextResponse {
  dimension: string;
  buckets: ContextBucket[];
}

export interface CompositionSlice {
  label: string;
  count: number;
  pct: number;
}

export interface CompositionResponse {
  slices: CompositionSlice[];
  total: number;
}

export interface MoneyResponse {
  total_bb: number;
  hands: number;
  bb_per_100: number;
}

export interface PostflopBridgeResponse {
  cbet_pct: number | null;
  cbet_count: number;
  cbet_opp: number;
  avg_spr: number | null;
}

export interface ContinuingCombo {
  combo: string;
  fold: number;
  call: number;
  raise_count: number;
  total: number;
}

export interface ContinuingRangeResponse {
  combos: ContinuingCombo[];
  total_hands: number;
}

export interface StatRangeCombo {
  combo: string;
  hands: number;
  actions: number;
  won_bb: number;
  ev_bb: number;
  bb_per_100: number;
  ev_bb_per_100: number;
  total_won_bb: number;
  total_bb_per_100: number;
}

export interface StatRangeResponse {
  combos: StatRangeCombo[];
  total_hands: number;
  total_actions: number;
}

// ── Widget API Fetch Functions ────────────────────────────────────────

type StatFilterParams = {
  position?: string;
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
};

function _buildStatParams(params?: StatFilterParams): URLSearchParams {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.game_mode !== undefined) sp.set('game_mode', params.game_mode === '__reg__' ? '' : params.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  _addWorkspaceParam(sp);
  return sp;
}

export async function getEvBreakdown(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<EvBreakdownResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/ev-breakdown?${sp}`, { signal });
  if (!res.ok) throw new Error(`EV breakdown failed: ${res.statusText}`);
  return res.json();
}

export async function getSizing(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<SizingResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/sizing?${sp}`, { signal });
  if (!res.ok) throw new Error(`Sizing failed: ${res.statusText}`);
  return res.json();
}

export async function getFoldEquity(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<FoldEquityResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/fold-equity?${sp}`, { signal });
  if (!res.ok) throw new Error(`Fold equity failed: ${res.statusText}`);
  return res.json();
}

export async function getByContext(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<ByContextResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/by-context?${sp}`, { signal });
  if (!res.ok) throw new Error(`By context failed: ${res.statusText}`);
  return res.json();
}

export async function getComposition(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<CompositionResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/composition?${sp}`, { signal });
  if (!res.ok) throw new Error(`Composition failed: ${res.statusText}`);
  return res.json();
}

export async function getMoney(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<MoneyResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/money?${sp}`, { signal });
  if (!res.ok) throw new Error(`Money failed: ${res.statusText}`);
  return res.json();
}

export async function getPostflopBridge(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<PostflopBridgeResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/postflop-bridge?${sp}`, { signal });
  if (!res.ok) throw new Error(`Postflop bridge failed: ${res.statusText}`);
  return res.json();
}

export async function getContinuingRange(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<ContinuingRangeResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/continuing-range?${sp}`, { signal });
  if (!res.ok) throw new Error(`Continuing range failed: ${res.statusText}`);
  return res.json();
}

export async function getStatRange(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<StatRangeResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/range?${sp}`, { signal });
  if (!res.ok) throw new Error(`Stat range failed: ${res.statusText}`);
  return res.json();
}

// ── Workspace & Checkpoint Types ─────────────────────────────────────

export interface Workspace {
  id: number;
  name: string;
  hero_username: string;
  hero_site: string;
  description: string | null;
  color: string | null;
  hand_count: number;
  date_range: { min: string | null; max: string | null };
  created_at: string;
}

export interface Checkpoint {
  id: number;
  workspace_id: number;
  name: string;
  checkpoint_at: string;
  note: string | null;
  created_at: string;
}

// ── Workspace CRUD ───────────────────────────────────────────────────

export async function getWorkspaces(): Promise<Workspace[]> {
  const res = await fetch(`${BASE}/workspaces`);
  if (!res.ok) throw new Error('Failed to fetch workspaces');
  return res.json();
}

export async function createWorkspace(data: { name: string; hero_username?: string; hero_site?: string; description?: string; color?: string }): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create workspace');
  return res.json();
}

export async function updateWorkspace(id: number, data: Partial<{ name: string; hero_username: string; hero_site: string; description: string; color: string }>): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update workspace');
  return res.json();
}

export async function deleteWorkspace(id: number): Promise<void> {
  const res = await fetch(`${BASE}/workspaces/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete workspace');
}

// ── Checkpoint CRUD ──────────────────────────────────────────────────

export async function getCheckpoints(workspaceId: number): Promise<Checkpoint[]> {
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/checkpoints`);
  if (!res.ok) throw new Error('Failed to fetch checkpoints');
  return res.json();
}

export async function createCheckpoint(workspaceId: number, data: { name: string; checkpoint_at?: string; note?: string }): Promise<Checkpoint> {
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/checkpoints`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create checkpoint');
  return res.json();
}

export async function updateCheckpoint(workspaceId: number, id: number, data: Partial<{ name: string; checkpoint_at: string; note: string }>): Promise<Checkpoint> {
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/checkpoints/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update checkpoint');
  return res.json();
}

export async function deleteCheckpoint(workspaceId: number, id: number): Promise<void> {
  const res = await fetch(`${BASE}/workspaces/${workspaceId}/checkpoints/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete checkpoint');
}

// ── Identity & Alias Types ──────────────────────────────────────────

export interface Alias {
  id: number;
  identity_id: number;
  workspace_id: number;
  player_id: number;
  username: string;
  workspace_name: string;
}

export interface Identity {
  id: number;
  display_name: string;
  notes: string | null;
  color: string | null;
  tags: string[];
  aliases: Alias[];
  total_hands: number;
  created_at: string;
}

// ── Identity CRUD ───────────────────────────────────────────────────

export async function getIdentities(): Promise<Identity[]> {
  const res = await fetch(`${BASE}/identities`);
  if (!res.ok) throw new Error('Failed to fetch identities');
  return res.json();
}

export async function createIdentity(data: { display_name: string; notes?: string; color?: string; tags?: string[] }): Promise<Identity> {
  const res = await fetch(`${BASE}/identities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create identity');
  return res.json();
}

export async function getIdentity(id: number): Promise<Identity> {
  const res = await fetch(`${BASE}/identities/${id}`);
  if (!res.ok) throw new Error('Failed to fetch identity');
  return res.json();
}

export async function updateIdentity(id: number, data: Partial<{ display_name: string; notes: string; color: string; tags: string[] }>): Promise<Identity> {
  const res = await fetch(`${BASE}/identities/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update identity');
  return res.json();
}

export async function deleteIdentity(id: number): Promise<void> {
  const res = await fetch(`${BASE}/identities/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete identity');
}

export async function addAlias(identityId: number, data: { workspace_id: number; player_id: number }): Promise<Identity> {
  const res = await fetch(`${BASE}/identities/${identityId}/aliases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to add alias');
  return res.json();
}

export async function removeAlias(identityId: number, aliasId: number): Promise<void> {
  const res = await fetch(`${BASE}/identities/${identityId}/aliases/${aliasId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to remove alias');
}

export async function getIdentityStats(identityId: number, params?: {
  position?: string;
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
}): Promise<HeroStats> {
  const sp = new URLSearchParams();
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  const res = await fetch(`${BASE}/identities/${identityId}/stats?${sp}`);
  if (!res.ok) throw new Error('Failed to fetch identity stats');
  return res.json();
}
