import { useState, useEffect, useMemo } from 'react';
import { getHeroStats, getFilterOptions } from '@/lib/api';
import type { HeroStats, PositionalStats, StatValue, FilterOptions, DriftStat } from '@/lib/api';
import { getPresetDates } from '@/lib/date-presets';
import type { DatePreset } from '@/lib/date-presets';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import LeakSummaryPanel from '@/components/LeakSummaryPanel';
import { useDrift } from '@/hooks/useDrift';
import {
  getBenchmarkForPosition,
  getStatHealth,
  STAT_DISPLAY_NAMES,
} from '@/lib/benchmarks';
import type { BenchmarkRange, StatHealth } from '@/lib/benchmarks';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ── Helpers ──────────────────────────────────────────────────────────

type ColorClass = 'text-green' | 'text-red' | 'text-yellow' | 'text-blue' | 'text-text' | 'text-text-muted';

const HEALTH_COLORS: Record<string, ColorClass> = {
  green: 'text-green',
  yellow: 'text-yellow',
  red: 'text-red',
  neutral: 'text-text',
};

function healthToColor(health: StatHealth): ColorClass {
  return HEALTH_COLORS[health.status] || 'text-text';
}

/** Format a StatValue for display. Returns {text, color, subscript?} */
function fmtStat(
  sv: StatValue | undefined,
  statKey?: string,
  position?: string,
  decimals: number = 0,
  colorFn?: (v: number) => ColorClass,
): { text: string; color: ColorClass; sub?: string; health?: StatHealth; benchmark?: BenchmarkRange } {
  if (!sv) return { text: '-', color: 'text-text-muted' };
  if (sv.sample === 0) return { text: '--', color: 'text-text-muted' };
  if (sv.value === null || sv.value === undefined) return { text: '--', color: 'text-text-muted' };

  const v = sv.value;
  const formatted = decimals > 0 ? v.toFixed(decimals) : Math.round(v).toString();

  if (sv.sample < 10) {
    return { text: formatted, color: 'text-text-muted', sub: String(sv.sample) };
  }

  // Use colorFn override (for win rate etc.)
  if (colorFn) {
    return { text: formatted, color: colorFn(v) };
  }

  // Use benchmark-based coloring
  if (statKey) {
    const benchmark = getBenchmarkForPosition(statKey, position);
    if (benchmark) {
      const health = getStatHealth(v, benchmark, sv.sample);
      return { text: formatted, color: healthToColor(health), health, benchmark };
    }
  }

  return { text: formatted, color: 'text-text' };
}

// ── Cell type ────────────────────────────────────────────────────────

interface CellDef {
  sv: StatValue | undefined;
  statKey?: string;
  position?: string;
  decimals?: number;
  colorFn?: (v: number) => ColorClass;
}

// ── Drift Arrow ──────────────────────────────────────────────────────

function DriftArrow({ drift, statKey }: { drift: DriftStat; statKey?: string }) {
  if (Math.abs(drift.z_score) < 1.5) return null;

  const arrow = drift.direction === 'up' ? '\u2191' : '\u2193';

  // Color: green if drifting toward benchmark midpoint, red if away
  let arrowColor = 'text-yellow';
  if (statKey) {
    const benchmark = getBenchmarkForPosition(statKey);
    if (benchmark) {
      const midpoint = (benchmark.low + benchmark.high) / 2;
      const lifetimeDist = Math.abs(drift.lifetime_avg - midpoint);
      const windowDist = Math.abs(drift.window_avg - midpoint);
      arrowColor = windowDist < lifetimeDist ? 'text-green' : 'text-red';
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={`ml-0.5 text-[11px] font-bold ${arrowColor} cursor-help`}>{arrow}</span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[240px] text-xs">
        <div className="space-y-1">
          <div className="font-semibold">{drift.interpretation}</div>
          <div className="text-text-muted">
            Lifetime: {drift.lifetime_avg.toFixed(1)}% &rarr; Recent: {drift.window_avg.toFixed(1)}%
          </div>
          <div className="text-text-muted">z = {drift.z_score.toFixed(2)}</div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

// ── Stat Cell ────────────────────────────────────────────────────────

/** Render a stat cell with optional tooltip and drift arrow */
function StatCell({
  sv,
  statKey,
  position,
  decimals = 0,
  colorFn,
  driftMap,
}: CellDef & { driftMap?: Map<string, DriftStat> }) {
  const { text, color, sub, health, benchmark } = fmtStat(sv, statKey, position, decimals, colorFn);

  // Map stat keys to drift keys (drift uses DB column names)
  const driftKeyMap: Record<string, string> = {
    vpip: 'vpip', pfr: 'pfr', fold_to_3bet: 'fold_to_3bet',
    cbet_flop: 'cbet_flop', wtsd: 'went_to_showdown', wsd: 'won_at_showdown',
    wwsf: 'saw_flop',
  };
  const driftKey = statKey ? driftKeyMap[statKey] : undefined;
  const drift = driftKey && driftMap?.get(driftKey);

  const hasTooltip = benchmark && health && sv?.value != null && health.status !== 'neutral';
  const displayName = statKey ? (STAT_DISPLAY_NAMES[statKey] || statKey) : '';

  const inner = (
    <span className={color}>
      {text}
      {sub && <sub className="text-[9px] ml-0.5 text-text-muted">{sub}</sub>}
      {drift && <DriftArrow drift={drift} statKey={statKey} />}
    </span>
  );

  if (!hasTooltip) {
    return (
      <td className="py-1 px-2 text-center font-mono text-[13px] leading-tight">
        {inner}
      </td>
    );
  }

  const tip = health.direction === 'low' ? benchmark.tipLow : benchmark.tipHigh;

  return (
    <td className="py-1 px-2 text-center font-mono text-[13px] leading-tight">
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help">{inner}</span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[280px] text-xs">
          <div className="space-y-1">
            <div className="font-semibold">{displayName}{position && position !== 'total' ? ` (${position.toUpperCase()})` : ''}</div>
            <div>Your value: <span className={`font-mono font-semibold ${color}`}>{text}</span></div>
            <div className="text-text-muted">Target: {benchmark.low}–{benchmark.high}</div>
            {tip && <div className="text-text-muted">{tip}</div>}
          </div>
        </TooltipContent>
      </Tooltip>
    </td>
  );
}

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
  driftMap,
}: {
  headers: string[];
  rows: { label: string; cells: CellDef[] }[];
  driftMap?: Map<string, DriftStat>;
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
              <StatCell key={i} {...cell} driftMap={driftMap} />
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
  driftMap,
}: {
  items: (CellDef & { label: string })[];
  driftMap?: Map<string, DriftStat>;
}) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 p-2">
      {items.map((item) => {
        const { text, color, sub, health, benchmark } = fmtStat(item.sv, item.statKey, item.position, item.decimals, item.colorFn);
        const displayName = item.statKey ? (STAT_DISPLAY_NAMES[item.statKey] || item.statKey) : item.label;

        // Drift arrow for KV items
        const driftKeyMap: Record<string, string> = {
          vpip: 'vpip', pfr: 'pfr', fold_to_3bet: 'fold_to_3bet',
          cbet_flop: 'cbet_flop', wtsd: 'went_to_showdown', wsd: 'won_at_showdown',
          wwsf: 'saw_flop',
        };
        const driftKey = item.statKey ? driftKeyMap[item.statKey] : undefined;
        const drift = driftKey && driftMap?.get(driftKey);

        const hasTooltip = benchmark && health && item.sv?.value != null && health.status !== 'neutral';
        const tip = health?.direction === 'low' ? benchmark?.tipLow : benchmark?.tipHigh;

        const valueSpan = (
          <span className={`font-mono text-[13px] ${color}`}>
            {text}
            {sub && <sub className="text-[9px] ml-0.5 text-text-muted">{sub}</sub>}
            {drift && <DriftArrow drift={drift} statKey={item.statKey} />}
          </span>
        );

        return (
          <div key={item.label} className="flex items-baseline justify-between py-0.5">
            <span className="text-[12px] text-text-muted mr-2 whitespace-nowrap">{item.label}</span>
            {hasTooltip ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="cursor-help">{valueSpan}</span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[280px] text-xs">
                  <div className="space-y-1">
                    <div className="font-semibold">{displayName}</div>
                    <div>Your value: <span className={`font-mono font-semibold ${color}`}>{text}</span></div>
                    <div className="text-text-muted">Target: {benchmark!.low}–{benchmark!.high}</div>
                    {tip && <div className="text-text-muted">{tip}</div>}
                  </div>
                </TooltipContent>
              </Tooltip>
            ) : valueSpan}
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
  statKey?: string,
  positions: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'],
) {
  if (!ps) {
    return {
      label,
      cells: positions.map(() => ({ sv: undefined as StatValue | undefined, statKey })),
    };
  }
  return {
    label,
    cells: positions.map((p) => ({ sv: ps[p], statKey, position: p })),
  };
}

/** Inline stat value for the missed-cbet / showdown sections */
function InlineStat({ sv, statKey, position, driftMap }: {
  sv: StatValue | undefined;
  statKey?: string;
  position?: string;
  driftMap?: Map<string, DriftStat>;
}) {
  const { text, color, sub, health, benchmark } = fmtStat(sv, statKey, position);
  const displayName = statKey ? (STAT_DISPLAY_NAMES[statKey] || statKey) : '';

  const driftKeyMap: Record<string, string> = {
    vpip: 'vpip', pfr: 'pfr', fold_to_3bet: 'fold_to_3bet',
    cbet_flop: 'cbet_flop', wtsd: 'went_to_showdown', wsd: 'won_at_showdown',
    wwsf: 'saw_flop',
  };
  const driftKey = statKey ? driftKeyMap[statKey] : undefined;
  const drift = driftKey && driftMap?.get(driftKey);

  const hasTooltip = benchmark && health && sv?.value != null && health.status !== 'neutral';
  const tip = health?.direction === 'low' ? benchmark?.tipLow : benchmark?.tipHigh;

  const inner = (
    <span className={`font-mono text-[13px] ${color}`}>
      {text}
      {sub && <sub className="text-[9px] ml-0.5 text-text-muted">{sub}</sub>}
      {drift && <DriftArrow drift={drift} statKey={statKey} />}
    </span>
  );

  if (!hasTooltip) return inner;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help">{inner}</span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[280px] text-xs">
        <div className="space-y-1">
          <div className="font-semibold">{displayName}</div>
          <div>Your value: <span className={`font-mono font-semibold ${color}`}>{text}</span></div>
          <div className="text-text-muted">Target: {benchmark!.low}–{benchmark!.high}</div>
          {tip && <div className="text-text-muted">{tip}</div>}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export default function StatsPage() {
  const [stats, setStats] = useState<HeroStats | null>(null);
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

  // Drift detection
  const { driftMap } = useDrift({
    stakes: filterParams.stakes,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
    enabled: (stats?.hands ?? 0) >= 1000,
  });

  // Load filter options once
  useEffect(() => {
    getFilterOptions().then(setFilterOpts);
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

  const handleDateFromChange = (v: string) => {
    setDateFrom(v);
    setActivePreset('all');
  };

  const handleDateToChange = (v: string) => {
    setDateTo(v);
    setActivePreset('all');
  };

  const hasFilters = !!(stakes || dateFrom || dateTo);

  const filterBarContent = (
    <FilterBar
      stakes={stakes}
      onStakesChange={setStakes}
      dateFrom={dateFrom}
      onDateFromChange={handleDateFromChange}
      dateTo={dateTo}
      onDateToChange={handleDateToChange}
      activePreset={activePreset}
      onPresetChange={handlePreset}
      filterOptions={filterOpts}
    >
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
    </FilterBar>
  );

  if (loading) return (
    <div className="max-w-6xl mx-auto px-2">
      {filterBarContent}
      <p className="text-text-muted p-4 text-center">Loading stats...</p>
    </div>
  );
  if (!stats || stats.hands === 0) {
    return (
      <div className="max-w-6xl mx-auto px-2">
        {filterBarContent}
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setStakes(''); setDateFrom(''); setDateTo(''); handlePreset('all'); } : undefined}
        />
      </div>
    );
  }

  const wr = stats.win_rate_bb100;
  const wrEv = stats.win_rate_ev_bb100;

  const fullPosHeaders = ['Total', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
  const fullPosKeys: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'];

  return (
    <TooltipProvider delayDuration={200}>
      <div className="max-w-6xl mx-auto px-2">
        {/* ── Filter Bar ── */}
        <div className="mb-3">{filterBarContent}</div>

        {/* ── Leak Summary Panel ── */}
        {stats.hands >= 200 && <LeakSummaryPanel stats={stats} />}

        {/* ── PRE-FLOP ── */}
        <SectionTitle>Pre-Flop</SectionTitle>
        <div className="flex flex-col lg:flex-row gap-0 border-x border-b border-border">
          {/* Left: Positional table */}
          <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
            <PosTable
              headers={fullPosHeaders}
              driftMap={driftMap}
              rows={[
                posRow('Open Raise', stats.open_raise, 'open_raise', fullPosKeys),
                posRow('Fold to 3Bet', stats.fold_to_3bet, 'fold_to_3bet', fullPosKeys),
                posRow('Call Open Raise', stats.call_open_raise, undefined, fullPosKeys),
                posRow('3-Bet', stats.three_bet, 'three_bet', fullPosKeys),
                posRow('3-Bet IP', stats.three_bet_ip, 'three_bet', fullPosKeys),
                posRow('3-Bet OOP', stats.three_bet_oop, 'three_bet', fullPosKeys),
              ]}
            />
          </div>

          {/* Right: KV grid */}
          <div className="w-full lg:w-72 lg:shrink-0">
            <KVGrid
              driftMap={driftMap}
              items={[
                { label: 'VPIP', sv: stats.vpip.total, statKey: 'vpip' },
                { label: 'PFR', sv: stats.pfr.total, statKey: 'pfr' },
                { label: '4-Bet', sv: stats.four_bet.total, statKey: 'four_bet' },
                { label: 'Limp', sv: stats.limp.total },
                { label: '4-Bet Range', sv: stats.four_bet_range, decimals: 1 },
                { label: 'Limp-Fold', sv: stats.limp_fold },
                { label: 'Squeeze', sv: stats.squeeze },
                { label: '4-Bet-Fold', sv: stats.four_bet_fold },
                { label: 'Fold to 4-Bet', sv: stats.fold_to_4bet.total, statKey: 'fold_to_4bet' },
                { label: 'Win Rate', sv: wr !== null ? { value: wr, sample: stats.hands } : undefined, colorFn: (v: number) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
                { label: 'Win Rate EV', sv: wrEv !== null ? { value: wrEv, sample: stats.hands } : undefined, colorFn: (v: number) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
                { label: 'Call 4-Bet', sv: stats.call_4bet },
                { label: 'Hands', sv: { value: stats.hands, sample: stats.hands } },
                { label: '5-Bet', sv: stats.five_bet },
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
              driftMap={driftMap}
              rows={[
                {
                  label: 'Steal',
                  cells: [
                    { sv: stats.steal.total, statKey: 'steal', position: 'total' },
                    { sv: stats.steal.btn, statKey: 'steal', position: 'btn' },
                    { sv: stats.steal.sb, statKey: 'steal', position: 'sb' },
                  ],
                },
                {
                  label: 'Fold to 3Bet',
                  cells: [
                    { sv: stats.fold_to_3bet_steal.total, statKey: 'fold_to_3bet', position: 'total' },
                    { sv: stats.fold_to_3bet_steal.btn, statKey: 'fold_to_3bet', position: 'btn' },
                    { sv: stats.fold_to_3bet_steal.sb, statKey: 'fold_to_3bet', position: 'sb' },
                  ],
                },
                {
                  label: '4-Bet',
                  cells: [
                    { sv: stats.four_bet_steal.total, statKey: 'four_bet', position: 'total' },
                    { sv: stats.four_bet_steal.btn, statKey: 'four_bet', position: 'btn' },
                    { sv: stats.four_bet_steal.sb, statKey: 'four_bet', position: 'sb' },
                  ],
                },
                {
                  label: '4-Bet-Fold',
                  cells: [
                    { sv: stats.four_bet_fold_steal.total },
                    { sv: stats.four_bet_fold_steal.btn },
                    { sv: stats.four_bet_fold_steal.sb },
                  ],
                },
              ]}
            />
          </div>

          {/* Right: vs Steal (SB, BB) */}
          <div className="flex-1 min-w-0 overflow-x-auto">
            <PosTable
              headers={['SB', 'BB']}
              driftMap={driftMap}
              rows={[
                {
                  label: 'Fold',
                  cells: [
                    { sv: stats.vs_steal_fold.sb, statKey: 'vs_steal_fold', position: 'sb' },
                    { sv: stats.vs_steal_fold.bb, statKey: 'vs_steal_fold', position: 'bb' },
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
                    { sv: stats.vs_steal_3bet.sb },
                    { sv: stats.vs_steal_3bet.bb },
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
              driftMap={driftMap}
              rows={[
                {
                  label: 'Continuation Bet',
                  cells: [
                    { sv: stats.cbet_flop.total, statKey: 'cbet_flop', position: 'total' },
                    { sv: stats.cbet_turn.total, statKey: 'cbet_turn', position: 'total' },
                    { sv: stats.cbet_river.total, statKey: 'cbet_river', position: 'total' },
                  ],
                },
                {
                  label: 'Fold to CBet',
                  cells: [
                    { sv: stats.fold_to_cbet_flop.total, statKey: 'fold_to_cbet_flop', position: 'total' },
                    { sv: stats.fold_to_cbet_turn.total, statKey: 'fold_to_cbet_turn', position: 'total' },
                    { sv: stats.fold_to_cbet_river.total },
                  ],
                },
                {
                  label: 'Aggression',
                  cells: [
                    { sv: stats.af_flop, statKey: 'af_flop', decimals: 1 },
                    { sv: stats.af_turn, statKey: 'af_turn', decimals: 1 },
                    { sv: stats.af_river, statKey: 'af_river', decimals: 1 },
                  ],
                },
                {
                  label: 'Agg Frequency',
                  cells: [
                    { sv: stats.afq_flop },
                    { sv: stats.afq_turn },
                    { sv: stats.afq_river },
                  ],
                },
                {
                  label: 'Donk Bet',
                  cells: [
                    { sv: stats.donk_bet_flop },
                    { sv: stats.donk_bet_turn },
                    { sv: stats.donk_bet_river },
                  ],
                },
              ]}
            />
          </div>

          {/* Right: vs CBet Flop (Fold/Call/Raise) */}
          <div className="flex-1 min-w-0 overflow-x-auto">
            <PosTable
              headers={['Fold', 'Call', 'Raise']}
              driftMap={driftMap}
              rows={[
                {
                  label: 'Raised Pot',
                  cells: [
                    { sv: stats.fold_cbet_flop_raised, statKey: 'fold_to_cbet_flop' },
                    { sv: stats.call_cbet_flop_raised },
                    { sv: stats.raise_cbet_flop_raised },
                  ],
                },
                {
                  label: '3-Bet Pot',
                  cells: [
                    { sv: stats.fold_cbet_flop_3bet, statKey: 'fold_to_cbet_flop' },
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
                <InlineStat sv={stats.missed_cbet_flop} driftMap={driftMap} />
              </div>
              <div className="pl-3 space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">In Position</span>
                  <InlineStat sv={stats.missed_cbet_flop_ip} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                  <InlineStat sv={stats.missed_cbet_fold_ip} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">Out of Position</span>
                  <InlineStat sv={stats.missed_cbet_flop_oop} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                  <InlineStat sv={stats.missed_cbet_fold_oop} driftMap={driftMap} />
                </div>
              </div>
            </div>
          </div>

          {/* Right: vs Missed CBet */}
          <div className="flex-1 min-w-0 p-2">
            <div className="space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] text-text-muted">vs. Missed Continuation Bet</span>
                <InlineStat sv={stats.vs_missed_cbet} driftMap={driftMap} />
              </div>
              <div className="pl-3 space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">Bet In Position</span>
                  <InlineStat sv={stats.vs_missed_cbet_bet_ip} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">Check | Fold</span>
                  <InlineStat sv={stats.vs_missed_cbet_check_fold_ip} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">Bet Out of Position Turn</span>
                  <InlineStat sv={stats.vs_missed_cbet_bet_oop_turn} driftMap={driftMap} />
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-text-muted">Check-Fold</span>
                  <InlineStat sv={stats.vs_missed_cbet_check_fold_oop} driftMap={driftMap} />
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
              <InlineStat sv={stats.wtsd} statKey="wtsd" driftMap={driftMap} />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[12px] text-text-muted">Won at Showdown</span>
              <InlineStat sv={stats.wsd} statKey="wsd" driftMap={driftMap} />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-[12px] text-text-muted">Won When Saw Flop</span>
              <InlineStat sv={stats.wwsf} statKey="wwsf" driftMap={driftMap} />
            </div>
          </div>
        </div>

        <div className="h-4" />
      </div>
    </TooltipProvider>
  );
}
