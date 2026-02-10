const BASE = '/api';

/** Translate game_mode filter: '__reg__' → '' (empty = Regular), undefined → skip */
function setGameModeParam(sp: URLSearchParams, gameMode: string | undefined) {
  if (gameMode !== undefined) {
    sp.set('game_mode', gameMode === '__reg__' ? '' : gameMode);
  }
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
  db_ms?: number;
}

export async function uploadFiles(files: File[]): Promise<ImportResult> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f);
  }
  const res = await fetch(`${BASE}/import/files`, { method: 'POST', body: form });
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
  const res = await fetch(`${BASE}/import/files/stream`, { method: 'POST', body: form });
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
  if (params?.position) sp.set('position', params.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.last_n) sp.set('last_n', String(params.last_n));
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
  const res = await fetch(`${BASE}/reports/graph?${sp}`);
  if (!res.ok) throw new Error(`Graph failed: ${res.statusText}`);
  return res.json();
}

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${BASE}/settings`);
  if (!res.ok) throw new Error(`Settings failed: ${res.statusText}`);
  return res.json();
}

export async function updateSettings(settings: Settings): Promise<Settings> {
  const res = await fetch(`${BASE}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.statusText}`);
  return res.json();
}

export async function getHealth(): Promise<{ status: string; hands: number }> {
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
}

export async function getHands(params?: HandListParams): Promise<HandListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set('page', String(params.page));
  if (params?.per_page) sp.set('per_page', String(params.per_page));
  if (params?.sort) sp.set('sort', params.sort);
  if (params?.order) sp.set('order', params.order);
  if (params?.position) sp.set('position', params.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.result) sp.set('result', params.result);
  if (params?.tags) sp.set('tags', params.tags);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.search) sp.set('search', params.search);
  if (params?.stat_flag) {
    for (const flag of params.stat_flag) sp.append('stat_flag', flag);
  }
  const res = await fetch(`${BASE}/hands?${sp}`);
  if (!res.ok) throw new Error(`Hands failed: ${res.statusText}`);
  return res.json();
}

export async function getHandDetail(handId: string): Promise<HandDetail> {
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}`);
  if (!res.ok) throw new Error(`Hand detail failed: ${res.statusText}`);
  return res.json();
}

export async function addTag(handId: string, tag: string): Promise<void> {
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag }),
  });
  if (!res.ok) throw new Error(`Add tag failed: ${res.statusText}`);
}

export async function removeTag(handId: string, tag: string): Promise<void> {
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/tags/${encodeURIComponent(tag)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Remove tag failed: ${res.statusText}`);
}

export async function getTags(): Promise<TagCount[]> {
  const res = await fetch(`${BASE}/tags`);
  if (!res.ok) throw new Error(`Tags failed: ${res.statusText}`);
  return res.json();
}

export async function updateNote(handId: string, note: string): Promise<void> {
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/note`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Update note failed: ${res.statusText}`);
}

export async function deleteNote(handId: string): Promise<void> {
  const res = await fetch(`${BASE}/hands/${encodeURIComponent(handId)}/note`, {
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
  if (params?.position) sp.set('position', params.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
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
  const res = await fetch(`${BASE}/reports/filter-options`);
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
  const res = await fetch(`${BASE}/reports/cash-drop?${sp}`);
  if (!res.ok) throw new Error(`Cash drop stats failed: ${res.statusText}`);
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
}

export interface StatDetailHandsResponse {
  stat_key: string;
  stat_name: string;
  action_count: number;
  opportunity_count: number;
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
  if (params?.position) sp.set('position', params.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  setGameModeParam(sp, params?.game_mode);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.page) sp.set('page', String(params.page));
  if (params?.per_page) sp.set('per_page', String(params.per_page));
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/hands?${sp}`, { signal });
  if (!res.ok) throw new Error(`Stat detail failed: ${res.statusText}`);
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
  const res = await fetch(`${BASE}/reports/drift?${sp}`);
  if (!res.ok) throw new Error(`Drift failed: ${res.statusText}`);
  return res.json();
}

export async function clearDatabase(): Promise<void> {
  const res = await fetch(`${BASE}/import/clear`, { method: 'POST' });
  if (!res.ok) throw new Error(`Clear failed: ${res.statusText}`);
}

export async function rebuildHands(
  onProgress: (progress: ImportProgress) => void,
): Promise<ImportResult> {
  const res = await fetch(`${BASE}/import/rebuild`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Rebuild failed: ${res.status} ${res.statusText}${body ? ` — ${body}` : ''}`);
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
          db_ms: msg.db_ms,
        };
      }
    }
  }

  return finalResult ?? { imported: 0, duplicates: 0, errors: 0, error_details: [] };
}
