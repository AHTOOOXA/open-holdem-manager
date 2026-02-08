import { useState, useEffect, useMemo } from 'react';
import { getHeroStats, getSettings, getFilterOptions } from '@/lib/api';
import type { HeroStats, PositionalStats, StatValue, Settings, FilterOptions } from '@/lib/api';

// ── Helpers ──────────────────────────────────────────────────────────

type ColorClass = 'text-green' | 'text-red' | 'text-yellow' | 'text-blue' | 'text-text' | 'text-text-muted';

/** Format a StatValue for display. Returns {text, color, subscript?} */
function fmtStat(
  sv: StatValue | undefined,
  colorFn?: (v: number) => ColorClass,
  decimals: number = 0,
): { text: string; color: ColorClass; sub?: string } {
  if (!sv) return { text: '-', color: 'text-text-muted' };
  if (sv.sample === 0) return { text: '--', color: 'text-text-muted' };
  if (sv.value === null || sv.value === undefined) return { text: '--', color: 'text-text-muted' };

  const v = sv.value;
  const formatted = decimals > 0 ? v.toFixed(decimals) : Math.round(v).toString();
  const color = colorFn ? colorFn(v) : 'text-text';

  if (sv.sample < 10) {
    return { text: formatted, color: 'text-text-muted', sub: String(sv.sample) };
  }

  return { text: formatted, color };
}

/** Render a stat cell with optional subscript */
function StatCell({
  sv,
  colorFn,
  decimals = 0,
}: {
  sv: StatValue | undefined;
  colorFn?: (v: number) => ColorClass;
  decimals?: number;
}) {
  const { text, color, sub } = fmtStat(sv, colorFn, decimals);
  return (
    <td className="py-1 px-2 text-center font-mono text-[13px] leading-tight">
      <span className={color}>
        {text}
        {sub && <sub className="text-[9px] ml-0.5 text-text-muted">{sub}</sub>}
      </span>
    </td>
  );
}

// ── Color functions (thresholds inspired by H2N) ─────────────────────

const colorVpip = (v: number): ColorClass =>
  v >= 20 && v <= 28 ? 'text-green' : v > 35 ? 'text-red' : v < 15 ? 'text-blue' : 'text-yellow';

const colorPfr = (v: number): ColorClass =>
  v >= 16 && v <= 24 ? 'text-green' : v > 30 ? 'text-red' : v < 12 ? 'text-blue' : 'text-yellow';

const colorOpenRaise = (v: number): ColorClass =>
  v >= 15 && v <= 30 ? 'text-green' : v > 40 ? 'text-red' : v < 10 ? 'text-blue' : 'text-yellow';

const colorThreeBet = (v: number): ColorClass =>
  v >= 6 && v <= 10 ? 'text-green' : v > 14 ? 'text-red' : v < 4 ? 'text-blue' : 'text-yellow';

const colorFoldTo3Bet = (v: number): ColorClass =>
  v >= 55 && v <= 65 ? 'text-green' : v > 70 ? 'text-red' : v < 45 ? 'text-yellow' : 'text-text';

const colorCallOpen = (v: number): ColorClass =>
  v >= 5 && v <= 12 ? 'text-green' : v > 20 ? 'text-red' : 'text-text';

const colorFourBet = (v: number): ColorClass =>
  v >= 3 && v <= 7 ? 'text-green' : v > 10 ? 'text-red' : v < 2 ? 'text-blue' : 'text-text';

const colorSteal = (v: number): ColorClass =>
  v >= 25 && v <= 40 ? 'text-green' : v > 50 ? 'text-red' : v < 20 ? 'text-blue' : 'text-yellow';

const colorVsStealFold = (v: number): ColorClass =>
  v > 75 ? 'text-red' : v < 60 ? 'text-green' : 'text-yellow';

const colorVsSteal3Bet = (v: number): ColorClass =>
  v >= 8 && v <= 14 ? 'text-green' : v > 18 ? 'text-red' : v < 5 ? 'text-blue' : 'text-text';

const colorCbet = (v: number): ColorClass =>
  v >= 50 && v <= 70 ? 'text-green' : v > 80 ? 'text-red' : v < 40 ? 'text-blue' : 'text-yellow';

const colorFoldToCbet = (v: number): ColorClass =>
  v >= 40 && v <= 55 ? 'text-green' : v > 65 ? 'text-red' : v < 30 ? 'text-blue' : 'text-text';

const colorAf = (v: number): ColorClass =>
  v >= 2 && v <= 4 ? 'text-green' : v > 5 ? 'text-red' : v < 1.5 ? 'text-blue' : 'text-text';

const colorAfq = (v: number): ColorClass =>
  v >= 40 && v <= 60 ? 'text-green' : v > 70 ? 'text-red' : v < 30 ? 'text-blue' : 'text-text';

const colorDonk = (v: number): ColorClass =>
  v > 15 ? 'text-red' : v > 5 ? 'text-yellow' : 'text-green';

const colorWtsd = (v: number): ColorClass =>
  v >= 24 && v <= 30 ? 'text-green' : v > 35 ? 'text-red' : v < 20 ? 'text-blue' : 'text-text';

const colorWsd = (v: number): ColorClass =>
  v >= 50 && v <= 55 ? 'text-green' : v > 60 ? 'text-yellow' : v < 45 ? 'text-red' : 'text-text';

const colorWwsf = (v: number): ColorClass =>
  v >= 42 && v <= 50 ? 'text-green' : v > 55 ? 'text-yellow' : v < 38 ? 'text-red' : 'text-text';

const colorLimp = (v: number): ColorClass =>
  v > 10 ? 'text-red' : v > 3 ? 'text-yellow' : 'text-green';

const colorSqueeze = (v: number): ColorClass =>
  v >= 5 && v <= 10 ? 'text-green' : v > 14 ? 'text-red' : v < 3 ? 'text-blue' : 'text-text';

const colorFoldTo4Bet = (v: number): ColorClass =>
  v >= 55 && v <= 65 ? 'text-green' : v > 70 ? 'text-red' : v < 45 ? 'text-yellow' : 'text-text';

const colorMissedCbet = (v: number): ColorClass =>
  v > 50 ? 'text-red' : v > 30 ? 'text-yellow' : 'text-green';

// ── Section Components ───────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 py-1.5 bg-surface text-[11px] font-bold uppercase tracking-wider text-primary border-b border-border">
      {children}
    </div>
  );
}

/** Positional table: Stat | Total | pos columns */
function PosTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: {
    label: string;
    cells: { sv: StatValue | undefined; colorFn?: (v: number) => ColorClass; decimals?: number }[];
  }[];
}) {
  return (
    <table className="w-full">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1 px-2 text-left text-[11px] font-medium text-text-muted uppercase w-32">
            Stat
          </th>
          {headers.map((h) => (
            <th key={h} className="py-1 px-2 text-center text-[11px] font-medium text-text-muted uppercase">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label} className="border-b border-border/30 hover:bg-surface-hover">
            <td className="py-1 px-2 text-[13px] text-text-muted whitespace-nowrap">{row.label}</td>
            {row.cells.map((cell, i) => (
              <StatCell key={i} sv={cell.sv} colorFn={cell.colorFn} decimals={cell.decimals} />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Key-value grid: two columns of label + value pairs */
function KVGrid({
  items,
}: {
  items: { label: string; sv: StatValue | undefined; colorFn?: (v: number) => ColorClass; decimals?: number }[];
}) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 p-2">
      {items.map((item) => {
        const { text, color, sub } = fmtStat(item.sv, item.colorFn, item.decimals);
        return (
          <div key={item.label} className="flex items-baseline justify-between py-0.5">
            <span className="text-[12px] text-text-muted mr-2 whitespace-nowrap">{item.label}</span>
            <span className={`font-mono text-[13px] ${color}`}>
              {text}
              {sub && <sub className="text-[9px] ml-0.5 text-text-muted">{sub}</sub>}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Build positional row from PositionalStats */
function posRow(
  label: string,
  ps: PositionalStats | undefined,
  colorFn?: (v: number) => ColorClass,
  positions: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'],
) {
  if (!ps) {
    return {
      label,
      cells: positions.map(() => ({ sv: undefined, colorFn })),
    };
  }
  return {
    label,
    cells: positions.map((p) => ({ sv: ps[p], colorFn })),
  };
}

// ── Main Component ───────────────────────────────────────────────────

type DatePreset = 'today' | 'week' | 'month' | 'all';

function getPresetDates(preset: DatePreset): { date_from?: string; date_to?: string } {
  if (preset === 'all') return {};
  const now = new Date();
  if (preset === 'today') return { date_from: now.toISOString().slice(0, 10) };
  if (preset === 'week') {
    const day = now.getDay();
    const diff = day === 0 ? 6 : day - 1;
    const monday = new Date(now);
    monday.setDate(now.getDate() - diff);
    return { date_from: monday.toISOString().slice(0, 10) };
  }
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { date_from: first.toISOString().slice(0, 10) };
}

export default function StatsPage() {
  const [stats, setStats] = useState<HeroStats | null>(null);
  const [settings, setSettingsData] = useState<Settings | null>(null);
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [stakes, setStakes] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [activePreset, setActivePreset] = useState<DatePreset>('all');
  const filterParams = useMemo(() => ({
    stakes: stakes || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [stakes, dateFrom, dateTo]);

  // Load filter options + settings once
  useEffect(() => {
    Promise.all([getFilterOptions(), getSettings()])
      .then(([fo, st]) => { setFilterOpts(fo); setSettingsData(st); });
  }, []);

  // Load stats when filters change
  useEffect(() => {
    let cancelled = false;
    getHeroStats(filterParams).then(s => {
      if (!cancelled) setStats(s);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [filterParams]);

  const handlePreset = (preset: DatePreset) => {
    setActivePreset(preset);
    const dates = getPresetDates(preset);
    setDateFrom(dates.date_from ?? '');
    setDateTo(dates.date_to ?? '');
  };

  const presetBtn = (preset: DatePreset, label: string) => (
    <button
      className={`px-3 py-1.5 text-xs rounded transition-colors ${
        activePreset === preset
          ? 'bg-primary text-white'
          : 'bg-surface border border-border text-text-muted hover:text-text'
      }`}
      onClick={() => handlePreset(preset)}
    >
      {label}
    </button>
  );

  const filterBarJSX = (
    <div className="bg-surface rounded-lg border border-border px-4 py-3 mb-3 flex flex-wrap items-center gap-3">
      {/* Hero badge */}
      <div className="flex items-center gap-2">
        <span className="bg-primary/20 text-primary px-2.5 py-0.5 rounded text-sm font-semibold">
          {settings?.hero_username || 'Hero'}
        </span>
        <span className="text-[11px] text-text-muted uppercase">{settings?.hero_site || 'GGPoker'}</span>
      </div>

      {/* Stakes filter */}
      <select
        value={stakes}
        onChange={(e) => setStakes(e.target.value)}
        className="bg-background border border-border rounded px-3 py-1.5 text-sm text-text focus:outline-none focus:border-primary"
      >
        <option value="">All Stakes</option>
        {filterOpts?.stakes.map(s => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      {/* Date inputs */}
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => { setDateFrom(e.target.value); setActivePreset('all'); }}
        className="bg-background border border-border rounded px-3 py-1.5 text-sm text-text focus:outline-none focus:border-primary"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => { setDateTo(e.target.value); setActivePreset('all'); }}
        className="bg-background border border-border rounded px-3 py-1.5 text-sm text-text focus:outline-none focus:border-primary"
      />

      {/* Date presets */}
      <div className="flex gap-1.5">
        {presetBtn('today', 'Today')}
        {presetBtn('week', 'Week')}
        {presetBtn('month', 'Month')}
        {presetBtn('all', 'All')}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Summary stats */}
      {stats && stats.hands > 0 && (() => {
        const wr = stats.win_rate_bb100;
        const wrEv = stats.win_rate_ev_bb100;
        const wrColor = wr !== null ? (wr >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';
        const wrEvColor = wrEv !== null ? (wrEv >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';
        return (
          <div className="flex items-center gap-3">
            <span className="text-sm text-text-muted">{stats.hands.toLocaleString()} hands</span>
            <span className={`text-sm font-bold font-mono ${wrColor}`}>
              {wr !== null ? `${wr >= 0 ? '+' : ''}${wr.toFixed(2)} bb/100` : '—'}
            </span>
            <span className={`text-sm font-bold font-mono ${wrEvColor}`}>
              EV {wrEv !== null ? `${wrEv >= 0 ? '+' : ''}${wrEv.toFixed(2)}` : '—'}
            </span>
          </div>
        );
      })()}
    </div>
  );

  if (loading) return (
    <div className="max-w-6xl mx-auto px-2">
      {filterBarJSX}
      <p className="text-text-muted p-4 text-center">Loading stats...</p>
    </div>
  );
  if (!stats || stats.hands === 0) {
    return (
      <div className="max-w-6xl mx-auto px-2">
        {filterBarJSX}
        <div className="text-center py-12">
          <p className="text-text-muted text-lg">No hands match the selected filters.</p>
          <p className="text-text-muted text-sm mt-2">Try adjusting your filters or import more hand histories.</p>
        </div>
      </div>
    );
  }

  const wr = stats.win_rate_bb100;
  const wrEv = stats.win_rate_ev_bb100;

  const fullPosHeaders = ['Total', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
  const fullPosKeys: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'];

  return (
    <div className="max-w-6xl mx-auto px-2">
      {/* ── Filter Bar ── */}
      {filterBarJSX}

      {/* ── PRE-FLOP ── */}
      <SectionTitle>Pre-Flop</SectionTitle>
      <div className="flex gap-0 border-x border-b border-border">
        {/* Left: Positional table */}
        <div className="flex-1 min-w-0 overflow-x-auto border-r border-border">
          <PosTable
            headers={fullPosHeaders}
            rows={[
              posRow('Open Raise', stats.open_raise, colorOpenRaise, fullPosKeys),
              posRow('Fold to 3Bet', stats.fold_to_3bet, colorFoldTo3Bet, fullPosKeys),
              posRow('Call Open Raise', stats.call_open_raise, colorCallOpen, fullPosKeys),
              posRow('3-Bet', stats.three_bet, colorThreeBet, fullPosKeys),
              {
                label: '3-Bet IP',
                cells: [
                  { sv: stats.three_bet_ip.total, colorFn: colorThreeBet },
                  { sv: undefined },  // EP — not IP
                  { sv: stats.three_bet_ip.mp, colorFn: colorThreeBet },
                  { sv: stats.three_bet_ip.co, colorFn: colorThreeBet },
                  { sv: stats.three_bet_ip.btn, colorFn: colorThreeBet },
                  { sv: undefined },  // SB — not IP
                  { sv: undefined },  // BB — not IP
                ],
              },
              {
                label: '3-Bet OOP',
                cells: [
                  { sv: stats.three_bet_oop.total, colorFn: colorThreeBet },
                  { sv: stats.three_bet_oop.ep, colorFn: colorThreeBet },
                  { sv: undefined },  // MP — not OOP
                  { sv: undefined },  // CO — not OOP
                  { sv: undefined },  // BTN — not OOP
                  { sv: stats.three_bet_oop.sb, colorFn: colorThreeBet },
                  { sv: stats.three_bet_oop.bb, colorFn: colorThreeBet },
                ],
              },
            ]}
          />
        </div>

        {/* Right: KV grid */}
        <div className="w-72 shrink-0">
          <KVGrid
            items={[
              { label: 'VPIP', sv: stats.vpip.total, colorFn: colorVpip },
              { label: 'PFR', sv: stats.pfr.total, colorFn: colorPfr },
              { label: '4-Bet', sv: stats.four_bet.total, colorFn: colorFourBet },
              { label: 'Limp', sv: stats.limp.total, colorFn: colorLimp },
              { label: '4-Bet Range', sv: stats.four_bet_range, colorFn: colorFourBet, decimals: 1 },
              { label: 'Limp-Fold', sv: stats.limp_fold, colorFn: colorLimp },
              { label: 'Squeeze', sv: stats.squeeze, colorFn: colorSqueeze },
              { label: '4-Bet-Fold', sv: stats.four_bet_fold, colorFn: colorFoldTo4Bet },
              { label: 'Fold to 4-Bet', sv: stats.fold_to_4bet.total, colorFn: colorFoldTo4Bet },
              { label: 'Win Rate', sv: wr !== null ? { value: wr, sample: stats.hands } : undefined, colorFn: (v) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
              { label: 'Win Rate EV', sv: wrEv !== null ? { value: wrEv, sample: stats.hands } : undefined, colorFn: (v) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
              { label: 'Call 4-Bet', sv: stats.call_4bet },
              { label: 'Hands', sv: { value: stats.hands, sample: stats.hands } },
              { label: '5-Bet', sv: stats.five_bet, colorFn: colorFourBet },
            ]}
          />
        </div>
      </div>

      {/* ── STEAL ── */}
      <SectionTitle>Steal</SectionTitle>
      <div className="flex gap-0 border-x border-b border-border">
        {/* Left: Steal table (Total, BTN, SB) */}
        <div className="flex-1 min-w-0 overflow-x-auto border-r border-border">
          <PosTable
            headers={['Total', 'BTN', 'SB']}
            rows={[
              {
                label: 'Steal',
                cells: [
                  { sv: stats.steal.total, colorFn: colorSteal },
                  { sv: stats.steal.btn, colorFn: colorSteal },
                  { sv: stats.steal.sb, colorFn: colorSteal },
                ],
              },
              {
                label: 'Fold to 3Bet',
                cells: [
                  { sv: stats.fold_to_3bet_steal.total, colorFn: colorFoldTo3Bet },
                  { sv: stats.fold_to_3bet_steal.btn, colorFn: colorFoldTo3Bet },
                  { sv: stats.fold_to_3bet_steal.sb, colorFn: colorFoldTo3Bet },
                ],
              },
              {
                label: '4-Bet',
                cells: [
                  { sv: stats.four_bet_steal.total, colorFn: colorFourBet },
                  { sv: stats.four_bet_steal.btn, colorFn: colorFourBet },
                  { sv: stats.four_bet_steal.sb, colorFn: colorFourBet },
                ],
              },
              {
                label: '4-Bet-Fold',
                cells: [
                  { sv: stats.four_bet_fold_steal.total, colorFn: colorFoldTo4Bet },
                  { sv: stats.four_bet_fold_steal.btn, colorFn: colorFoldTo4Bet },
                  { sv: stats.four_bet_fold_steal.sb, colorFn: colorFoldTo4Bet },
                ],
              },
            ]}
          />
        </div>

        {/* Right: vs Steal (SB, BB) */}
        <div className="flex-1 min-w-0 overflow-x-auto">
          <PosTable
            headers={['SB', 'BB']}
            rows={[
              {
                label: 'Fold',
                cells: [
                  { sv: stats.vs_steal_fold.sb, colorFn: colorVsStealFold },
                  { sv: stats.vs_steal_fold.bb, colorFn: colorVsStealFold },
                ],
              },
              {
                label: 'Call',
                cells: [
                  { sv: stats.vs_steal_call.sb },
                  { sv: stats.vs_steal_call.bb },
                ],
              },
              {
                label: '3-Bet',
                cells: [
                  { sv: stats.vs_steal_3bet.sb, colorFn: colorVsSteal3Bet },
                  { sv: stats.vs_steal_3bet.bb, colorFn: colorVsSteal3Bet },
                ],
              },
            ]}
          />
          <div className="px-2 py-0.5 text-[10px] text-text-muted uppercase tracking-wide border-t border-border/30">
            vs. Steal
          </div>
        </div>
      </div>

      {/* ── POSTFLOP ── */}
      <SectionTitle>Postflop</SectionTitle>
      <div className="flex gap-0 border-x border-b border-border">
        {/* Left: Postflop stats by street */}
        <div className="flex-1 min-w-0 overflow-x-auto border-r border-border">
          <PosTable
            headers={['Flop', 'Turn', 'River']}
            rows={[
              {
                label: 'Continuation Bet',
                cells: [
                  { sv: stats.cbet_flop.total, colorFn: colorCbet },
                  { sv: stats.cbet_turn.total, colorFn: colorCbet },
                  { sv: stats.cbet_river.total, colorFn: colorCbet },
                ],
              },
              {
                label: 'Fold to CBet',
                cells: [
                  { sv: stats.fold_to_cbet_flop.total, colorFn: colorFoldToCbet },
                  { sv: stats.fold_to_cbet_turn.total, colorFn: colorFoldToCbet },
                  { sv: stats.fold_to_cbet_river.total, colorFn: colorFoldToCbet },
                ],
              },
              {
                label: 'Aggression',
                cells: [
                  { sv: stats.af_flop, colorFn: colorAf, decimals: 1 },
                  { sv: stats.af_turn, colorFn: colorAf, decimals: 1 },
                  { sv: stats.af_river, colorFn: colorAf, decimals: 1 },
                ],
              },
              {
                label: 'Agg Frequency',
                cells: [
                  { sv: stats.afq_flop, colorFn: colorAfq },
                  { sv: stats.afq_turn, colorFn: colorAfq },
                  { sv: stats.afq_river, colorFn: colorAfq },
                ],
              },
              {
                label: 'Donk Bet',
                cells: [
                  { sv: stats.donk_bet_flop, colorFn: colorDonk },
                  { sv: stats.donk_bet_turn, colorFn: colorDonk },
                  { sv: stats.donk_bet_river, colorFn: colorDonk },
                ],
              },
            ]}
          />
        </div>

        {/* Right: vs CBet Flop (Fold/Call/Raise) */}
        <div className="flex-1 min-w-0 overflow-x-auto">
          <PosTable
            headers={['Fold', 'Call', 'Raise']}
            rows={[
              {
                label: 'Raised Pot',
                cells: [
                  { sv: stats.fold_cbet_flop_raised, colorFn: colorFoldToCbet },
                  { sv: stats.call_cbet_flop_raised },
                  { sv: stats.raise_cbet_flop_raised },
                ],
              },
              {
                label: '3-Bet Pot',
                cells: [
                  { sv: stats.fold_cbet_flop_3bet, colorFn: colorFoldToCbet },
                  { sv: stats.call_cbet_flop_3bet },
                  { sv: stats.raise_cbet_flop_3bet },
                ],
              },
            ]}
          />
          <div className="px-2 py-0.5 text-[10px] text-text-muted uppercase tracking-wide border-t border-border/30">
            vs. Continuation Bet Flop
          </div>
        </div>
      </div>

      {/* ── MISSED C-BET ── */}
      <SectionTitle>Missed C-Bet</SectionTitle>
      <div className="flex gap-0 border-x border-b border-border">
        {/* Left: Missed CBet breakdown */}
        <div className="flex-1 min-w-0 p-2 border-r border-border">
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-text-muted">Missed Continuation Bet</span>
              <span className={`font-mono text-[13px] ${fmtStat(stats.missed_cbet_flop, colorMissedCbet).color}`}>
                {fmtStat(stats.missed_cbet_flop, colorMissedCbet).text}
                {fmtStat(stats.missed_cbet_flop, colorMissedCbet).sub && (
                  <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.missed_cbet_flop, colorMissedCbet).sub}</sub>
                )}
              </span>
            </div>
            <div className="pl-3 space-y-1">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">In Position</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.missed_cbet_flop_ip, colorMissedCbet).color}`}>
                  {fmtStat(stats.missed_cbet_flop_ip, colorMissedCbet).text}
                  {fmtStat(stats.missed_cbet_flop_ip, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.missed_cbet_flop_ip, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">→ Fold</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.missed_cbet_fold_ip, colorMissedCbet).color}`}>
                  {fmtStat(stats.missed_cbet_fold_ip, colorMissedCbet).text}
                  {fmtStat(stats.missed_cbet_fold_ip, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.missed_cbet_fold_ip, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Out of Position</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.missed_cbet_flop_oop, colorMissedCbet).color}`}>
                  {fmtStat(stats.missed_cbet_flop_oop, colorMissedCbet).text}
                  {fmtStat(stats.missed_cbet_flop_oop, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.missed_cbet_flop_oop, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">→ Fold</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.missed_cbet_fold_oop, colorMissedCbet).color}`}>
                  {fmtStat(stats.missed_cbet_fold_oop, colorMissedCbet).text}
                  {fmtStat(stats.missed_cbet_fold_oop, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.missed_cbet_fold_oop, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: vs Missed CBet */}
        <div className="flex-1 min-w-0 p-2">
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-text-muted">vs. Missed Continuation Bet</span>
              <span className={`font-mono text-[13px] ${fmtStat(stats.vs_missed_cbet).color}`}>
                {fmtStat(stats.vs_missed_cbet).text}
                {fmtStat(stats.vs_missed_cbet).sub && (
                  <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.vs_missed_cbet).sub}</sub>
                )}
              </span>
            </div>
            <div className="pl-3 space-y-1">
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Bet In Position</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.vs_missed_cbet_bet_ip).color}`}>
                  {fmtStat(stats.vs_missed_cbet_bet_ip).text}
                  {fmtStat(stats.vs_missed_cbet_bet_ip).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.vs_missed_cbet_bet_ip).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Check | Fold</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.vs_missed_cbet_check_fold_ip, colorMissedCbet).color}`}>
                  {fmtStat(stats.vs_missed_cbet_check_fold_ip, colorMissedCbet).text}
                  {fmtStat(stats.vs_missed_cbet_check_fold_ip, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.vs_missed_cbet_check_fold_ip, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Bet Out of Position Turn</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.vs_missed_cbet_bet_oop_turn).color}`}>
                  {fmtStat(stats.vs_missed_cbet_bet_oop_turn).text}
                  {fmtStat(stats.vs_missed_cbet_bet_oop_turn).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.vs_missed_cbet_bet_oop_turn).sub}</sub>
                  )}
                </span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[12px] text-text-muted">Check-Fold</span>
                <span className={`font-mono text-[13px] ${fmtStat(stats.vs_missed_cbet_check_fold_oop, colorMissedCbet).color}`}>
                  {fmtStat(stats.vs_missed_cbet_check_fold_oop, colorMissedCbet).text}
                  {fmtStat(stats.vs_missed_cbet_check_fold_oop, colorMissedCbet).sub && (
                    <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.vs_missed_cbet_check_fold_oop, colorMissedCbet).sub}</sub>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── SHOWDOWN ── */}
      <SectionTitle>Showdown</SectionTitle>
      <div className="border-x border-b border-border p-2">
        <div className="flex gap-6">
          <div className="flex items-baseline gap-2">
            <span className="text-[12px] text-text-muted">Went to Showdown</span>
            <span className={`font-mono text-[13px] ${fmtStat(stats.wtsd, colorWtsd).color}`}>
              {fmtStat(stats.wtsd, colorWtsd).text}
              {fmtStat(stats.wtsd, colorWtsd).sub && (
                <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.wtsd, colorWtsd).sub}</sub>
              )}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-[12px] text-text-muted">Won at Showdown</span>
            <span className={`font-mono text-[13px] ${fmtStat(stats.wsd, colorWsd).color}`}>
              {fmtStat(stats.wsd, colorWsd).text}
              {fmtStat(stats.wsd, colorWsd).sub && (
                <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.wsd, colorWsd).sub}</sub>
              )}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-[12px] text-text-muted">Won When Saw Flop</span>
            <span className={`font-mono text-[13px] ${fmtStat(stats.wwsf, colorWwsf).color}`}>
              {fmtStat(stats.wwsf, colorWwsf).text}
              {fmtStat(stats.wwsf, colorWwsf).sub && (
                <sub className="text-[9px] ml-0.5 text-text-muted">{fmtStat(stats.wwsf, colorWwsf).sub}</sub>
              )}
            </span>
          </div>
        </div>
      </div>

      <div className="h-4" />
    </div>
  );
}
