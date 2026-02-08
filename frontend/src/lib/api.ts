const BASE = '/api';

export interface ImportResult {
  imported: number;
  duplicates: number;
  errors: number;
  error_details: string[];
}

export interface Settings {
  hero_username: string;
  hero_site: string;
}

export interface GraphPoint {
  hand_number: number;
  cumulative_bb: number;
  cumulative_ev_bb: number;
  cumulative_rake_bb: number;
  cumulative_showdown_bb: number;
  cumulative_nonshowdown_bb: number;
  cumulative_usd: number;
  cumulative_ev_usd: number;
  cumulative_rake_usd: number;
  cumulative_showdown_usd: number;
  cumulative_nonshowdown_usd: number;
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
  three_bet_ip: StatValue;
  three_bet_oop: StatValue;
  four_bet: PositionalStats;
  five_bet: StatValue;
  fold_to_3bet: PositionalStats;
  fold_to_4bet: PositionalStats;
  call_open_raise: PositionalStats;
  limp: PositionalStats;
  squeeze: StatValue;
  four_bet_range: StatValue;
  steal: PositionalStats;
  fold_to_3bet_steal: PositionalStats;
  four_bet_steal: PositionalStats;
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
  af_flop: StatValue;
  af_turn: StatValue;
  af_river: StatValue;
  afq_flop: StatValue;
  afq_turn: StatValue;
  afq_river: StatValue;
  missed_cbet_flop: StatValue;
  missed_cbet_flop_ip: StatValue;
  missed_cbet_flop_oop: StatValue;
  missed_cbet_turn: StatValue;
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
        };
      }
    }
  }

  return finalResult ?? { imported: 0, duplicates: 0, errors: 0, error_details: [] };
}

export async function getHeroStats(params?: {
  position?: string;
  stakes?: string;
  date_from?: string;
  date_to?: string;
}): Promise<HeroStats> {
  const sp = new URLSearchParams();
  if (params?.position) sp.set('position', params.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  const res = await fetch(`${BASE}/stats/hero?${sp}`);
  if (!res.ok) throw new Error(`Stats failed: ${res.statusText}`);
  return res.json();
}

export async function getGraphData(params?: {
  stakes?: string;
  date_from?: string;
  date_to?: string;
}): Promise<GraphPoint[]> {
  const sp = new URLSearchParams();
  if (params?.stakes) sp.set('stakes', params.stakes);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
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
        };
      }
    }
  }

  return finalResult ?? { imported: 0, duplicates: 0, errors: 0, error_details: [] };
}
