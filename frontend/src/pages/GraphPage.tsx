import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import {
  getGraphData,
  getResultsBreakdown,
} from '@/lib/api';
import type {
  GraphPoint,
  SessionMarker,
  StakeBreakdown,
  MonthBreakdown,
  PositionBreakdown,
} from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { queryKeys } from '@/lib/query-keys';
import { getPresetDates } from '@/lib/date-presets';
import type { DatePreset } from '@/lib/date-presets';
import { formatStakes } from '@/lib/utils';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Toggle } from '@/components/ui/toggle';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';

function formatXTick(value: number) {
  if (value >= 1000) return `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  return String(value);
}

function niceXTicks(max: number): number[] {
  if (max <= 0) return [0];
  // Pick a "nice" step from the sequence: 1k, 2.5k, 5k, 10k, 25k, 50k, 100k...
  const steps = [1000, 2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000];
  // Target ~6-10 ticks
  let step = steps[steps.length - 1];
  for (const s of steps) {
    if (max / s <= 10) { step = s; break; }
  }
  const ticks: number[] = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < max) ticks.push(max);
  return ticks;
}

type LineToggle = 'ev' | 'showdown' | 'rake' | 'ci' | 'sessions';

const LINE_COLORS = {
  main: '#fbbf24',
  ev: '#06b6d4',
  showdown: '#22c55e',
  nonshowdown: '#ef4444',
  rake: '#a78bfa',
  ci: '#fbbf24',
  session: 'oklch(0.553 0.013 58.071)',
} as const;

function formatDateTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }) + ' ' + d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function formatTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function sessionDurationHours(s: SessionMarker): number {
  if (!s.start_time || !s.end_time) return 0;
  return (new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 3600000;
}

function totalSessionHours(sessions: SessionMarker[]): number {
  return sessions.reduce((sum, s) => sum + sessionDurationHours(s), 0);
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number | number[]; color: string }>;
  label?: number;
  unit: 'bb' | 'usd';
  tooltipNames: Record<string, string>;
  activeSession?: SessionMarker | null;
}

function CustomTooltip({ active, payload, label, unit, tooltipNames, activeSession }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload as GraphPoint | undefined;
  const prefix = unit === 'usd' ? '$' : '';
  const suffix = unit === 'bb' ? ' BB' : '';
  return (
    <div style={{
      backgroundColor: 'oklch(0.216 0.006 56.043)',
      border: '1px solid oklch(1 0 0 / 10%)',
      borderRadius: '8px',
      color: 'oklch(0.985 0.001 106.423)',
      padding: '8px 12px',
      fontSize: '13px',
    }}>
      <div style={{ marginBottom: 4, color: 'oklch(0.709 0.01 56.259)' }}>
        {point?.played_at ? formatDateTime(point.played_at) : ''}
      </div>
      <div style={{ marginBottom: 6, fontWeight: 600 }}>
        Hand #{Number(label).toLocaleString()}
      </div>
      {payload.map((entry, i) => {
        const name = tooltipNames[entry.name] ?? entry.name;
        if (Array.isArray(entry.value)) {
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color, display: 'inline-block', flexShrink: 0 }} />
              <span>{name}: {prefix}{entry.value[0].toFixed(1)}{suffix} to {prefix}{entry.value[1].toFixed(1)}{suffix}</span>
            </div>
          );
        }
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color, display: 'inline-block', flexShrink: 0 }} />
            <span>{name}: {prefix}{entry.value.toFixed(2)}{suffix}</span>
          </div>
        );
      })}
      {activeSession && (() => {
        const hands = activeSession.end_hand - activeSession.start_hand + 1;
        const hrs = sessionDurationHours(activeSession);
        const hph = hrs > 0 ? Math.round(hands / hrs) : 0;
        return (
          <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid oklch(1 0 0 / 10%)', color: 'oklch(0.709 0.01 56.259)', fontSize: 11 }}>
            Session: {formatTime(activeSession.start_time)} – {formatTime(activeSession.end_time)}
            <span style={{ marginLeft: 8 }}>({hands} hands{hph > 0 ? ` · ${hph} hands/hr` : ''})</span>
          </div>
        );
      })()}
    </div>
  );
}

function formatMonth(ym: string): string {
  const [y, m] = ym.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

export default function GraphPage() {
  // Data
  const [activeSession, setActiveSession] = useState<SessionMarker | null>(null);

  // Filters
  const [stakes, setStakes] = useState<string>('');
  const [gameMode, setGameMode] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [activePreset, setActivePreset] = useState<DatePreset>('all');
  const [lastN, setLastN] = useState<string>('');

  // Display toggles
  const [unit, setUnit] = useState<'bb' | 'usd'>('bb');
  const [lines, setLines] = useState<Set<LineToggle>>(new Set(['ev', 'showdown', 'sessions']));

  const toggle = (line: LineToggle) => {
    setLines(prev => {
      const next = new Set(prev);
      if (next.has(line)) next.delete(line);
      else next.add(line);
      return next;
    });
  };

  // Debounce lastN so typing doesn't trigger a refetch on every keystroke
  const [debouncedLastN, setDebouncedLastN] = useState<string>('');
  const lastNTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    lastNTimer.current = setTimeout(() => setDebouncedLastN(lastN), 500);
    return () => clearTimeout(lastNTimer.current);
  }, [lastN]);

  const lastNParsed = debouncedLastN ? parseInt(debouncedLastN, 10) : undefined;
  const filterParams = useMemo(() => ({
    stakes: stakes || undefined,
    game_mode: gameMode || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    last_n: lastNParsed && lastNParsed > 0 ? lastNParsed : undefined,
  }), [stakes, gameMode, dateFrom, dateTo, lastNParsed]);

  // Shared filter options
  const { data: filterOpts } = useFilterOptions();

  // Graph data query
  const { data: graphResp, isPending: graphLoading } = useQuery({
    queryKey: queryKeys.graph.data(filterParams),
    queryFn: () => getGraphData(filterParams),
  });

  const data = useMemo(() => graphResp?.points ?? [], [graphResp]);
  const sessions = useMemo(() => graphResp?.sessions ?? [], [graphResp]);
  const variance = graphResp?.variance ?? null;

  // Breakdown query
  const { data: breakdown, isPending: breakdownLoading } = useQuery({
    queryKey: queryKeys.graph.breakdown(filterParams),
    queryFn: () => getResultsBreakdown(filterParams),
  });

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

  const hasEVData = useMemo(() => data.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [data]);

  const handleChartMouseMove = useCallback((e: { activeLabel?: number }) => {
    if (!e.activeLabel || !lines.has('sessions')) { setActiveSession(null); return; }
    const hand = e.activeLabel;
    const found = sessions.find(s => hand >= s.start_hand && hand <= s.end_hand) ?? null;
    setActiveSession(found);
  }, [sessions, lines]);

  const handleChartMouseLeave = useCallback(() => setActiveSession(null), []);

  const chartData = useMemo(() => {
    const max = 1000;
    if (data.length <= max) return data;
    const step = (data.length - 1) / (max - 1);
    const sampled: GraphPoint[] = [];
    for (let i = 0; i < max - 1; i++) {
      sampled.push(data[Math.round(i * step)]);
    }
    sampled.push(data[data.length - 1]);
    return sampled;
  }, [data]);

  const chartDataEnriched = useMemo(() => {
    const addRake = lines.has('rake');
    const addCI = lines.has('ci') && variance;
    if (!addRake && !addCI) return chartData;
    const mean = variance ? variance.winrate_bb100 / 100 : 0;
    const sd = variance ? variance.sd_bb : 0;
    return chartData.map(d => {
      const i = d.hand_number;
      const sqrtI = Math.sqrt(i);
      return {
        ...d,
        ...(addRake ? {
          neg_rake_bb: -d.cumulative_rake_bb,
          neg_rake_usd: -d.cumulative_rake_usd,
        } : {}),
        ...(addCI ? {
          ci_range: [
            Math.round((mean * i - 1.96 * sd * sqrtI) * 100) / 100,
            Math.round((mean * i + 1.96 * sd * sqrtI) * 100) / 100,
          ],
        } : {}),
      };
    });
  }, [chartData, lines, variance]);

  // Helpers
  const clr = (v: number) => v >= 0 ? 'text-green' : 'text-red';
  const fmtBB = (v: number) => `${v.toFixed(1)} BB`;
  const fmtUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;


  // Toggle button helper
  const toggleBtn = (key: LineToggle, label: string, color: string, show = true) =>
    show && (
      <Toggle
        key={key}
        size="sm"
        className="h-7 text-xs data-[state=on]:text-white"
        pressed={lines.has(key)}
        onPressedChange={() => toggle(key)}
        style={lines.has(key) ? { backgroundColor: color } : undefined}
      >
        {label}
      </Toggle>
    );

  const hasFilters = !!(stakes || gameMode || dateFrom || dateTo || lastN);

  // Stat card data from last graph point
  const last = data.length > 0 ? data[data.length - 1] : null;
  const n = data.length;

  const wonBB = last?.cumulative_bb ?? 0;
  const wonUSD = last?.cumulative_usd ?? 0;
  const evBB = last?.cumulative_ev_bb ?? 0;
  const evUSD = last?.cumulative_ev_usd ?? 0;
  const rakeBB = last?.cumulative_rake_bb ?? 0;
  const rakeUSD = last?.cumulative_rake_usd ?? 0;
  const jackpotBB = last?.cumulative_jackpot_bb ?? 0;
  const jackpotUSD = last?.cumulative_jackpot_usd ?? 0;
  const sdBB = last?.cumulative_showdown_bb ?? 0;
  const sdUSD = last?.cumulative_showdown_usd ?? 0;
  const nsdBB = last?.cumulative_nonshowdown_bb ?? 0;
  const nsdUSD = last?.cumulative_nonshowdown_usd ?? 0;

  const rateBB = n > 0 ? (wonBB / n) * 100 : 0;
  const evRateBB = n > 0 ? (evBB / n) * 100 : 0;
  const rakePerBB = n > 0 ? (rakeBB / n) * 100 : 0;

  const totalHrs = totalSessionHours(sessions);
  const handsPerHour = totalHrs > 0 ? Math.round(n / totalHrs) : 0;
  const usdPerHour = totalHrs > 0 ? wonUSD / totalHrs : 0;
  const bbPerHour = totalHrs > 0 ? wonBB / totalHrs : 0;

  const k = (base: string) => unit === 'bb' ? `${base}_bb` : `${base}_usd`;
  const mainKey = k('cumulative');
  const evKey = k('cumulative_ev');
  const sdKey = k('cumulative_showdown');
  const nsdKey = k('cumulative_nonshowdown');
  const negRakeKey = unit === 'bb' ? 'neg_rake_bb' : 'neg_rake_usd';

  const tooltipNames: Record<string, string> = {
    [mainKey]: 'Actual',
    [evKey]: 'All-in EV',
    [sdKey]: 'Showdown',
    [nsdKey]: 'Non-Showdown',
    [negRakeKey]: 'Rake',
    ci_range: '95% CI',
  };

  const filterBarContent = (
    <FilterBar
      stakes={stakes}
      onStakesChange={setStakes}
      gameMode={gameMode}
      onGameModeChange={setGameMode}
      dateFrom={dateFrom}
      onDateFromChange={handleDateFromChange}
      dateTo={dateTo}
      onDateToChange={handleDateToChange}
      activePreset={activePreset}
      onPresetChange={handlePreset}
      filterOptions={filterOpts ?? null}
    >
      {/* Last N hands */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-muted">Last</span>
        <Input
          type="number"
          value={lastN}
          onChange={(e) => setLastN(e.target.value)}
          placeholder="All"
          min={1}
          className="w-20 h-8 text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        />
        <span className="text-xs text-text-muted">hands</span>
      </div>
    </FilterBar>
  );

  const displayToolbar = (
    <div className="flex items-center gap-2.5 px-2 py-1">
      <ToggleGroup type="single" value={unit} onValueChange={(v) => { if (v) setUnit(v as 'bb' | 'usd'); }}>
        <ToggleGroupItem value="bb" className="h-7 text-xs px-3">BB</ToggleGroupItem>
        <ToggleGroupItem value="usd" className="h-7 text-xs px-3">$</ToggleGroupItem>
      </ToggleGroup>
      {toggleBtn('ev', 'EV', LINE_COLORS.ev, hasEVData)}
      {toggleBtn('showdown', 'SD', LINE_COLORS.showdown)}
      {toggleBtn('rake', 'Rake', LINE_COLORS.rake)}
      {toggleBtn('ci', 'CI', LINE_COLORS.ci, !!variance)}
      {toggleBtn('sessions', 'Sessions', LINE_COLORS.session, sessions.length > 1)}
    </div>
  );

  // Empty state
  if (!graphLoading && !breakdownLoading && data.length === 0 && !breakdown?.by_stakes.length) {
    return (
      <div className="max-w-6xl mx-auto space-y-1.5">
        {filterBarContent}
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setStakes(''); setGameMode(''); setDateFrom(''); setDateTo(''); setLastN(''); handlePreset('all'); } : undefined}
        />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-1.5">
      {/* Filter Bar */}
      {filterBarContent}

      {/* Graph — skeleton while loading or chart not yet rendered */}
      {graphLoading ? (
        <Card className="gap-0 py-0 p-2">
          <Skeleton className="h-[400px] w-full rounded" />
        </Card>
      ) : data.length > 0 && (
        <Card className="gap-0 py-0 p-2">
          {displayToolbar}
          <div className="flex justify-center gap-4 mt-1.5 mb-1 text-xs text-text-muted">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.main }} />
              Actual
            </span>
            {lines.has('ev') && hasEVData && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.ev, opacity: 0.8 }} />
                All-in EV
              </span>
            )}
            {lines.has('showdown') && (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.showdown }} />
                  Showdown
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.nonshowdown }} />
                  Non-Showdown
                </span>
              </>
            )}
            {lines.has('rake') && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.rake }} />
                Rake
              </span>
            )}
            {lines.has('ci') && variance && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-2 rounded opacity-30" style={{ background: LINE_COLORS.ci }} />
                95% CI
              </span>
            )}
            {lines.has('sessions') && sessions.length > 1 && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.session, borderTop: '1px dashed oklch(0.553 0.013 58.071)' }} />
                Sessions
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={chartDataEnriched} margin={{ top: 4, right: 16, bottom: 4, left: 8 }} onMouseMove={handleChartMouseMove} onMouseLeave={handleChartMouseLeave}>
              <defs>
                <linearGradient id="gradientMain" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={LINE_COLORS.main} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={LINE_COLORS.main} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="oklch(0.268 0.007 34.298)" strokeDasharray="none" />
              <XAxis
                dataKey="hand_number"
                type="number"
                domain={[0, 'dataMax']}
                ticks={niceXTicks(data.length)}
                stroke="oklch(0.553 0.013 58.071)"
                tick={{ fontSize: 11, fill: 'oklch(0.553 0.013 58.071)' }}
                tickFormatter={formatXTick}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="oklch(0.553 0.013 58.071)"
                tick={{ fontSize: 11, fill: 'oklch(0.553 0.013 58.071)' }}
                axisLine={false}
                tickLine={false}
                width={50}
                tickFormatter={(v: number) => unit === 'usd' ? `$${v}` : String(v)}
              />
              <Tooltip
                content={<CustomTooltip unit={unit} tooltipNames={tooltipNames} activeSession={activeSession} />}
              />
              <ReferenceLine y={0} stroke="oklch(0.553 0.013 58.071 / 50%)" strokeDasharray="4 4" />
              {lines.has('sessions') && activeSession && (
                <ReferenceArea
                  x1={activeSession.start_hand}
                  x2={activeSession.end_hand}
                  fill="oklch(0.77 0.16 70)"
                  fillOpacity={0.06}
                  strokeOpacity={0}
                />
              )}
              {lines.has('sessions') && sessions.slice(1).map(s => (
                <ReferenceLine
                  key={`session-${s.start_hand}`}
                  x={s.start_hand}
                  stroke={LINE_COLORS.session}
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  label={{
                    value: formatTime(s.start_time),
                    position: 'top',
                    fill: 'oklch(0.553 0.013 58.071)',
                    fontSize: 9,
                  }}
                />
              ))}
              {lines.has('ci') && variance && (
                <Area
                  type="monotone"
                  dataKey="ci_range"
                  name="ci_range"
                  stroke={LINE_COLORS.ci}
                  strokeWidth={0.5}
                  strokeOpacity={0.3}
                  fill={LINE_COLORS.ci}
                  fillOpacity={0.08}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              )}
              <Area
                type="monotone"
                dataKey={mainKey}
                name={mainKey}
                fill="url(#gradientMain)"
                stroke={LINE_COLORS.main}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                baseValue={0}
              />
              {lines.has('ev') && hasEVData && (
                <Line
                  type="monotone"
                  dataKey={evKey}
                  name={evKey}
                  stroke={LINE_COLORS.ev}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  strokeDasharray="6 3"
                  opacity={0.8}
                  isAnimationActive={false}
                />
              )}
              {lines.has('showdown') && (
                <Line
                  type="monotone"
                  dataKey={sdKey}
                  name={sdKey}
                  stroke={LINE_COLORS.showdown}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              )}
              {lines.has('showdown') && (
                <Line
                  type="monotone"
                  dataKey={nsdKey}
                  name={nsdKey}
                  stroke={LINE_COLORS.nonshowdown}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              )}
              {lines.has('rake') && (
                <Line
                  type="monotone"
                  dataKey={negRakeKey}
                  name={negRakeKey}
                  stroke={LINE_COLORS.rake}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  strokeDasharray="4 2"
                  isAnimationActive={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Stats Panel */}
      {graphLoading ? (
        <Card className="gap-0 py-0 overflow-hidden">
          <div className="px-4 py-2"><Skeleton className="h-4 w-64" /></div>
          <div className="grid grid-cols-2 border-t border-border">
            <div className="px-4 py-3 space-y-2"><Skeleton className="h-6 w-24" /><Skeleton className="h-5 w-20" /><Skeleton className="h-3 w-16" /></div>
            <div className="px-4 py-3 space-y-2 border-l border-border"><Skeleton className="h-6 w-24" /><Skeleton className="h-5 w-20" /><Skeleton className="h-3 w-16" /></div>
          </div>
          <div className="px-4 py-2 border-t border-border"><Skeleton className="h-4 w-full" /></div>
        </Card>
      ) : (
        <Card className="gap-0 py-0 overflow-hidden">
          {/* Context strip */}
          <div className="px-4 py-2 text-xs font-mono text-text-muted">
            {n.toLocaleString()} hands · {handsPerHour > 0 ? `${handsPerHour}/hr · ` : ''}{totalHrs > 0 ? `${totalHrs.toFixed(0)}h played · ` : ''}{sessions.length} sessions
          </div>

          {/* Hero pair: Actual vs EV */}
          <div className="grid grid-cols-2 border-t border-border">
            {/* Actual */}
            <div className="px-4 py-3 grid grid-cols-2 gap-x-4">
              <div className={`text-xl font-bold font-mono ${clr(wonUSD)}`}>{fmtUSD(wonUSD)}</div>
              <div className={`text-xl font-bold font-mono ${clr(rateBB)}`}>{rateBB.toFixed(2)}</div>
              <div className={`text-sm font-mono ${clr(wonBB)}`}>{fmtBB(wonBB)}</div>
              <div className="text-sm font-mono text-text-muted">bb/100</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wide">Won</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wide">Rate</div>
            </div>
            {/* EV */}
            <div className="px-4 py-3 border-l border-border grid grid-cols-2 gap-x-4">
              {hasEVData ? (
                <>
                  <div className={`text-xl font-bold font-mono ${clr(evUSD)}`}>{fmtUSD(evUSD)}</div>
                  <div className={`text-xl font-bold font-mono ${clr(evRateBB)}`}>{evRateBB.toFixed(2)}</div>
                  <div className={`text-sm font-mono ${clr(evBB)}`}>{fmtBB(evBB)}</div>
                  <div className="text-sm font-mono text-text-muted">EV bb/100</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
                </>
              ) : (
                <>
                  <div className="text-xl font-bold font-mono text-text-muted">—</div>
                  <div className="text-xl font-bold font-mono text-text-muted">—</div>
                  <div className="text-sm font-mono text-text-muted">&nbsp;</div>
                  <div className="text-sm font-mono text-text-muted">&nbsp;</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
                </>
              )}
            </div>
          </div>

          {/* Footer: secondary stats */}
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-x-6 px-4 py-2.5 border-t border-border">
            {/* $/hr */}
            <div>
              <div className={`text-sm font-bold font-mono ${totalHrs > 0 ? clr(usdPerHour) : 'text-text-muted'}`}>
                {totalHrs > 0 ? `${usdPerHour >= 0 ? '' : '-'}$${Math.abs(usdPerHour).toFixed(2)}/hr` : '—'}
              </div>
              <div className="text-xs text-text-muted">$/hr {totalHrs > 0 ? <span className={`font-mono ${clr(bbPerHour)}`}>{bbPerHour.toFixed(1)} BB</span> : ''}</div>
            </div>
            {/* SD Won */}
            <div>
              <div className={`text-sm font-bold font-mono ${clr(sdUSD)}`}>{fmtUSD(sdUSD)}</div>
              <div className="text-xs text-text-muted">Showdown <span className={`font-mono ${clr(sdBB)}`}>{fmtBB(sdBB)}</span></div>
            </div>
            {/* NSD Won */}
            <div>
              <div className={`text-sm font-bold font-mono ${clr(nsdUSD)}`}>{fmtUSD(nsdUSD)}</div>
              <div className="text-xs text-text-muted">Non-SD <span className={`font-mono ${clr(nsdBB)}`}>{fmtBB(nsdBB)}</span></div>
            </div>
            {/* Rake */}
            <div>
              <div className="text-sm font-bold font-mono text-text-muted">{fmtUSD(rakeUSD)}</div>
              <div className="text-xs text-text-muted">Rake <span className="font-mono">{rakePerBB.toFixed(1)}/100{jackpotBB > 0 ? ` · BBJ ${fmtUSD(jackpotUSD)}` : ''}</span></div>
            </div>
            {/* 95% CI */}
            <div>
              {variance ? (
                <>
                  <div className={`text-sm font-bold font-mono ${variance.ci_lower_bb100 > 0 ? 'text-green' : variance.ci_upper_bb100 < 0 ? 'text-red' : 'text-text'}`}>
                    {variance.ci_lower_bb100.toFixed(2)} to {variance.ci_upper_bb100.toFixed(2)}
                  </div>
                  <div className="text-xs text-text-muted">95% CI bb/100 <span className="font-mono">σ {variance.sd_bb100.toFixed(1)}</span></div>
                </>
              ) : (
                <div className="text-sm font-mono text-text-muted">—</div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Breakdown Tables — independent loading */}
      {breakdownLoading ? (
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-3 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Breakdown by Stakes */}
          {breakdown && breakdown.by_stakes.length > 0 && (
            <BreakdownTable
              title="Breakdown by Stakes"
              columns={stakeColumns}
              rows={breakdown.by_stakes}
              rowKey={(r: StakeBreakdown) => `${r.game_mode}:${r.stakes}`}
            />
          )}

          {/* Breakdown by Position */}
          {breakdown && breakdown.by_position.length > 0 && (
            <BreakdownTable
              title="Breakdown by Position"
              columns={positionColumns}
              rows={breakdown.by_position}
              rowKey={(r: PositionBreakdown) => r.position}
            />
          )}

          {/* Breakdown by Month */}
          {breakdown && breakdown.by_month.length > 0 && (
            <BreakdownTable
              title="Breakdown by Month"
              columns={monthColumns}
              rows={breakdown.by_month}
              rowKey={(r: MonthBreakdown) => r.month}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Breakdown Table ──────────────────────────────────────────────────

interface Column<T> {
  key: string;
  label: string;
  align?: 'left' | 'right';
  width?: string;
  render: (row: T) => React.ReactNode;
}

function BreakdownTable<T>({
  title,
  columns,
  rows,
  rowKey,
}: {
  title: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}) {
  return (
    <Card className="overflow-hidden gap-0 py-0">
      <CardHeader className="px-3 py-1.5">
        <h2 className="text-xs font-semibold text-text">{title}</h2>
      </CardHeader>
      <div className="overflow-x-auto">
        <Table style={{ tableLayout: 'fixed', width: '100%' }}>
          <colgroup>
            {columns.map(col => (
              <col key={col.key} style={col.width ? { width: col.width } : undefined} />
            ))}
          </colgroup>
          <TableHeader>
            <TableRow>
              {columns.map(col => (
                <TableHead
                  key={col.key}
                  className={`px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                >
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(row => (
              <TableRow key={rowKey(row)} className="hover:bg-surface-hover transition-colors">
                {columns.map(col => (
                  <TableCell
                    key={col.key}
                    className={`px-3 py-1.5 font-mono ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                  >
                    {col.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function renderRake(r: { rake_usd: number }) {
  return <span className="text-red">${r.rake_usd.toFixed(2)}</span>;
}

function colorVal(v: number): string {
  if (v > 0) return 'text-green';
  if (v < 0) return 'text-red';
  return 'text-text-muted';
}

const COL_WIDTHS = { label: '22%', hands: '16%', won: '18%', bb100: '16%', ev_bb100: '16%', rake: '12%' };

const stakeColumns: Column<StakeBreakdown>[] = [
  { key: 'stakes', label: 'Stakes', width: COL_WIDTHS.label, render: (r) => {
    return <span className="text-text">{formatStakes(r.stakes)}{r.game_mode ? <span className="text-text-muted ml-1.5 text-xs">{r.game_mode}</span> : ''}</span>;
  }},
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={colorVal(v)}>{`${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];

const positionColumns: Column<PositionBreakdown>[] = [
  { key: 'position', label: 'Position', width: COL_WIDTHS.label, render: (r) => <span className="text-text font-semibold">{r.position}</span> },
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={colorVal(v)}>{`${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];

const monthColumns: Column<MonthBreakdown>[] = [
  { key: 'month', label: 'Month', width: COL_WIDTHS.label, render: (r) => <span className="text-text">{formatMonth(r.month)}</span> },
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={colorVal(v)}>{`${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];
