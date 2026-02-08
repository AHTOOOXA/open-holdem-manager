import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
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
} from 'recharts';
import {
  getGraphData,
  getFilterOptions,
  getResultsBreakdown,
} from '@/lib/api';
import type {
  GraphPoint,
  VarianceStats,
  FilterOptions,
  ResultsBreakdown,
  StakeBreakdown,
  MonthBreakdown,
  PositionBreakdown,
} from '@/lib/api';

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

function StatCard({
  label,
  bb,
  usd,
  bbColor,
  usdColor,
  border,
  detail,
}: {
  label: string;
  bb: string;
  usd: string;
  bbColor?: string;
  usdColor?: string;
  border?: string;
  detail?: string;
}) {
  return (
    <div
      className="bg-surface rounded-lg border border-border px-4 py-3"
      style={border ? { borderLeftWidth: 3, borderLeftColor: border } : undefined}
    >
      <div className="text-[11px] text-text-muted mb-1.5 uppercase tracking-wide">{label}</div>
      <div className={`text-lg font-bold font-mono leading-tight ${bbColor ?? ''}`}>{bb}</div>
      <div className={`text-sm font-mono leading-tight mt-0.5 ${usdColor ?? 'text-text-muted'}`}>{usd}</div>
      {detail && <div className="text-[11px] font-mono text-text-muted mt-1">{detail}</div>}
    </div>
  );
}

type LineToggle = 'ev' | 'showdown' | 'rake' | 'ci' | 'sessions';
type DatePreset = 'today' | 'week' | 'month' | 'all';

const LINE_COLORS = {
  main: '#818cf8',
  ev: '#eab308',
  showdown: '#22c55e',
  nonshowdown: '#ef4444',
  rake: '#f97316',
  ci: '#818cf8',
  session: '#555570',
} as const;

function getPresetDates(preset: DatePreset): { date_from?: string; date_to?: string } {
  if (preset === 'all') return {};
  const now = new Date();
  if (preset === 'today') {
    return { date_from: now.toISOString().slice(0, 10) };
  }
  if (preset === 'week') {
    const day = now.getDay();
    const diff = day === 0 ? 6 : day - 1; // Monday = 0
    const monday = new Date(now);
    monday.setDate(now.getDate() - diff);
    return { date_from: monday.toISOString().slice(0, 10) };
  }
  // month
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { date_from: first.toISOString().slice(0, 10) };
}

function formatMonth(ym: string): string {
  const [y, m] = ym.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

export default function GraphPage() {
  // Data
  const [data, setData] = useState<GraphPoint[]>([]);
  const [sessionStarts, setSessionStarts] = useState<number[]>([]);
  const [variance, setVariance] = useState<VarianceStats | null>(null);
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [breakdown, setBreakdown] = useState<ResultsBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [stakes, setStakes] = useState<string>('');
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
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    last_n: lastNParsed && lastNParsed > 0 ? lastNParsed : undefined,
  }), [stakes, dateFrom, dateTo, lastNParsed]);

  // Load filter options once
  useEffect(() => {
    getFilterOptions().then(setFilterOpts);
  }, []);

  // Load graph + breakdown when filters change
  const fetchData = useCallback(() => {
    setLoading(true);
    Promise.all([
      getGraphData(filterParams),
      getResultsBreakdown(filterParams),
    ]).then(([graphResp, breakdownData]) => {
      setData(graphResp.points);
      setSessionStarts(graphResp.session_starts);
      setVariance(graphResp.variance);
      setBreakdown(breakdownData);
    }).finally(() => setLoading(false));
  }, [filterParams]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
  const brd = (v: number) => v >= 0 ? '#22c55e' : '#ef4444';
  const fmtBB = (v: number) => `${v.toFixed(1)} BB`;
  const fmtUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
  const fmtRateBB = (v: number) => `${v.toFixed(2)} bb/100`;
  const fmtRateUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}/100`;

  // Toggle button helper
  const toggleBtn = (key: LineToggle, label: string, color: string, show = true) =>
    show && (
      <button
        key={key}
        className={`px-3 py-1.5 text-xs rounded transition-colors ${
          lines.has(key)
            ? 'text-white'
            : 'bg-surface border border-border text-text-muted hover:text-text'
        }`}
        style={lines.has(key) ? { backgroundColor: color } : undefined}
        onClick={() => toggle(key)}
      >
        {label}
      </button>
    );

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

  // Empty state
  if (!loading && data.length === 0 && !breakdown?.by_stakes.length) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        {filterBarJSX}
        <div className="text-center py-12">
          <p className="text-text-muted text-lg">No hands match the selected filters.</p>
          <p className="text-text-muted text-sm mt-2">Try adjusting your filters or import more hand histories.</p>
        </div>
      </div>
    );
  }

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
  const rateUSD = n > 0 ? (wonUSD / n) * 100 : 0;
  const evRateBB = n > 0 ? (evBB / n) * 100 : 0;
  const evRateUSD = n > 0 ? (evUSD / n) * 100 : 0;
  const rakePerBB = n > 0 ? (rakeBB / n) * 100 : 0;
  const rakePerUSD = n > 0 ? (rakeUSD / n) * 100 : 0;

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

  const filterBarJSX = (
    <div className="bg-surface rounded-lg border border-border px-4 py-3 flex flex-wrap items-center gap-3">
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
        onChange={(e) => handleDateFromChange(e.target.value)}
        className="bg-background border border-border rounded px-3 py-1.5 text-sm text-text focus:outline-none focus:border-primary"
        placeholder="From"
      />
      <input
        type="date"
        value={dateTo}
        onChange={(e) => handleDateToChange(e.target.value)}
        className="bg-background border border-border rounded px-3 py-1.5 text-sm text-text focus:outline-none focus:border-primary"
        placeholder="To"
      />

      {/* Date presets */}
      <div className="flex gap-1.5">
        {presetBtn('today', 'Today')}
        {presetBtn('week', 'Week')}
        {presetBtn('month', 'Month')}
        {presetBtn('all', 'All')}
      </div>

      {/* Last N hands */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-muted">Last</span>
        <input
          type="number"
          value={lastN}
          onChange={(e) => setLastN(e.target.value)}
          placeholder="All"
          min={1}
          className="bg-background border border-border rounded px-2 py-1.5 text-sm text-text w-20 focus:outline-none focus:border-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        />
        <span className="text-xs text-text-muted">hands</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Unit toggle + line toggles */}
      <div className="flex gap-1.5 items-center">
        <div className="flex rounded overflow-hidden border border-border">
          <button
            className={`px-3 py-1.5 text-xs transition-colors ${
              unit === 'bb' ? 'bg-primary text-white' : 'bg-surface text-text-muted hover:text-text'
            }`}
            onClick={() => setUnit('bb')}
          >
            BB
          </button>
          <button
            className={`px-3 py-1.5 text-xs transition-colors ${
              unit === 'usd' ? 'bg-primary text-white' : 'bg-surface text-text-muted hover:text-text'
            }`}
            onClick={() => setUnit('usd')}
          >
            $
          </button>
        </div>
        {toggleBtn('ev', 'EV', LINE_COLORS.ev, hasEVData)}
        {toggleBtn('showdown', 'SD', LINE_COLORS.showdown)}
        {toggleBtn('rake', 'Rake', LINE_COLORS.rake)}
        {toggleBtn('ci', 'CI', LINE_COLORS.ci, !!variance)}
        {toggleBtn('sessions', 'Sessions', LINE_COLORS.session, sessionStarts.length > 1)}
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Filter Bar */}
      {filterBarJSX}

      {loading ? (
        <p className="text-text-muted py-8 text-center">Loading...</p>
      ) : (
        <>
          {/* Graph */}
          {data.length > 0 && (
            <div className="bg-surface rounded-lg border border-border p-4">
              <div className="flex gap-4 mb-2 ml-12 text-xs text-text-muted">
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
                {lines.has('sessions') && sessionStarts.length > 1 && (
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.session, borderTop: '1px dashed #555570' }} />
                    Sessions
                  </span>
                )}
              </div>
              <ResponsiveContainer width="100%" height={400}>
                <ComposedChart data={chartDataEnriched} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <defs>
                    <linearGradient id="gradientMain" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={LINE_COLORS.main} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={LINE_COLORS.main} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="#1e1e2e" strokeDasharray="none" />
                  <XAxis
                    dataKey="hand_number"
                    type="number"
                    domain={[0, 'dataMax']}
                    ticks={niceXTicks(data.length)}
                    stroke="#555570"
                    tick={{ fontSize: 11, fill: '#555570' }}
                    tickFormatter={formatXTick}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#555570"
                    tick={{ fontSize: 11, fill: '#555570' }}
                    axisLine={false}
                    tickLine={false}
                    width={50}
                    tickFormatter={(v: number) => unit === 'usd' ? `$${v}` : String(v)}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #2a2a3a',
                      borderRadius: '8px',
                      color: '#e4e4ef',
                      padding: '8px 12px',
                      fontSize: '13px',
                    }}
                    formatter={(value: number | number[], name: string) => {
                      if (Array.isArray(value)) {
                        const prefix = unit === 'usd' ? '$' : '';
                        const suffix = unit === 'bb' ? ' BB' : '';
                        return [`${prefix}${value[0].toFixed(1)}${suffix} to ${prefix}${value[1].toFixed(1)}${suffix}`, tooltipNames[name] ?? name];
                      }
                      const prefix = unit === 'usd' ? '$' : '';
                      const suffix = unit === 'bb' ? ' BB' : '';
                      const formatted = `${prefix}${value.toFixed(2)}${suffix}`;
                      return [formatted, tooltipNames[name] ?? name];
                    }}
                    labelFormatter={(label) => `Hand #${Number(label).toLocaleString()}`}
                  />
                  <ReferenceLine y={0} stroke="#444460" strokeDasharray="4 4" />
                  {lines.has('sessions') && sessionStarts.slice(1).map(handNum => (
                    <ReferenceLine
                      key={`session-${handNum}`}
                      x={handNum}
                      stroke={LINE_COLORS.session}
                      strokeDasharray="4 4"
                      strokeWidth={1}
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
            </div>
          )}

          {/* Stat Cards - Row 1 */}
          <div className="grid gap-3 grid-cols-5">
            <StatCard
              label="Hands"
              bb={n.toLocaleString()}
              usd=""
              bbColor="text-text"
            />
            <StatCard
              label="Won"
              bb={fmtBB(wonBB)}
              usd={fmtUSD(wonUSD)}
              bbColor={clr(wonBB)}
              usdColor={clr(wonUSD)}
              border={brd(wonBB)}
            />
            <StatCard
              label="Winrate"
              bb={fmtRateBB(rateBB)}
              usd={fmtRateUSD(rateUSD)}
              bbColor={clr(rateBB)}
              usdColor={clr(rateUSD)}
              border={brd(rateBB)}
            />
            {hasEVData ? (
              <StatCard
                label="EV Won"
                bb={fmtBB(evBB)}
                usd={fmtUSD(evUSD)}
                bbColor={clr(evBB)}
                usdColor={clr(evUSD)}
                border={brd(evBB)}
              />
            ) : (
              <StatCard label="EV Won" bb="—" usd="" bbColor="text-text-muted" />
            )}
            {hasEVData ? (
              <StatCard
                label="EV Winrate"
                bb={fmtRateBB(evRateBB)}
                usd={fmtRateUSD(evRateUSD)}
                bbColor={clr(evRateBB)}
                usdColor={clr(evRateUSD)}
                border={brd(evRateBB)}
              />
            ) : (
              <StatCard label="EV Winrate" bb="—" usd="" bbColor="text-text-muted" />
            )}
          </div>

          {/* Stat Cards - Row 2 */}
          <div className="grid gap-3 grid-cols-4">
            <StatCard
              label="Rake"
              bb={fmtBB(rakeBB)}
              usd={fmtUSD(rakeUSD)}
              bbColor="text-red"
              usdColor="text-red"
              border="#ef4444"
              detail={jackpotBB ? `(BBJ: ${fmtBB(jackpotBB)} / ${fmtUSD(jackpotUSD)})` : undefined}
            />
            <StatCard
              label="Rake/100"
              bb={fmtRateBB(rakePerBB)}
              usd={fmtRateUSD(rakePerUSD)}
              bbColor="text-red"
              usdColor="text-red"
              border="#ef4444"
            />
            <StatCard
              label="SD Won"
              bb={fmtBB(sdBB)}
              usd={fmtUSD(sdUSD)}
              bbColor={clr(sdBB)}
              usdColor={clr(sdUSD)}
              border={brd(sdBB)}
            />
            <StatCard
              label="NSD Won"
              bb={fmtBB(nsdBB)}
              usd={fmtUSD(nsdUSD)}
              bbColor={clr(nsdBB)}
              usdColor={clr(nsdUSD)}
              border={brd(nsdBB)}
            />
          </div>

          {/* Variance Stats */}
          {variance && (
            <div className="grid gap-3 grid-cols-4">
              <StatCard
                label="Std Dev bb/100"
                bb={variance.sd_bb100.toFixed(1)}
                usd=""
                bbColor="text-text"
              />
              <StatCard
                label="95% CI"
                bb={`${variance.ci_lower_bb100.toFixed(2)} to ${variance.ci_upper_bb100.toFixed(2)} bb/100`}
                usd=""
                bbColor={variance.ci_lower_bb100 > 0 ? 'text-green' : variance.ci_upper_bb100 < 0 ? 'text-red' : 'text-text-muted'}
              />
              <StatCard
                label="Sessions"
                bb={String(sessionStarts.length)}
                usd={sessionStarts.length > 0 ? `~${Math.round(n / sessionStarts.length)} hands/session` : ''}
                bbColor="text-text"
              />
              <StatCard
                label="Std Dev per hand"
                bb={`${variance.sd_bb.toFixed(2)} BB`}
                usd=""
                bbColor="text-text"
              />
            </div>
          )}

          {/* Breakdown by Stakes */}
          {breakdown && breakdown.by_stakes.length > 1 && !stakes && (
            <BreakdownTable
              title="Breakdown by Stakes"
              columns={stakeColumns}
              rows={breakdown.by_stakes}
              rowKey={(r: StakeBreakdown) => r.stakes}
              unit={unit}
            />
          )}

          {/* Breakdown by Position */}
          {breakdown && breakdown.by_position.length > 0 && (
            <BreakdownTable
              title="Breakdown by Position"
              columns={positionColumns}
              rows={breakdown.by_position}
              rowKey={(r: PositionBreakdown) => r.position}
              unit={unit}
            />
          )}

          {/* Breakdown by Month */}
          {breakdown && breakdown.by_month.length > 0 && (
            <BreakdownTable
              title="Breakdown by Month"
              columns={monthColumns}
              rows={breakdown.by_month}
              rowKey={(r: MonthBreakdown) => r.month}
              unit={unit}
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
  render: (row: T, unit: 'bb' | 'usd') => React.ReactNode;
}

function BreakdownTable<T>({
  title,
  columns,
  rows,
  rowKey,
  unit,
}: {
  title: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  unit: 'bb' | 'usd';
}) {
  return (
    <div className="bg-surface rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-muted font-medium ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={rowKey(row)} className="border-b border-border last:border-0 hover:bg-surface-hover transition-colors">
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={`px-4 py-2.5 font-mono ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                  >
                    {col.render(row, unit)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function renderRake(r: { rake_bb: number; rake_usd: number }, u: 'bb' | 'usd') {
  const v = u === 'bb' ? r.rake_bb : r.rake_usd;
  const fmt = u === 'bb' ? `${v.toFixed(1)} BB` : `$${v.toFixed(2)}`;
  return <span className="text-red">{fmt}</span>;
}

function colorVal(v: number): string {
  if (v > 0) return 'text-green';
  if (v < 0) return 'text-red';
  return 'text-text-muted';
}

const stakeColumns: Column<StakeBreakdown>[] = [
  { key: 'stakes', label: 'Stakes', render: (r) => <span className="text-text">{r.stakes}</span> },
  { key: 'hands', label: 'Hands', align: 'right', render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    render: (r, u) => {
      const v = u === 'bb' ? r.won_bb : r.won_usd;
      const fmt = u === 'bb' ? `${v.toFixed(1)} BB` : `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
      return <span className={colorVal(v)}>{fmt}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    render: (r, u) => renderRake(r, u),
  },
];

const positionColumns: Column<PositionBreakdown>[] = [
  { key: 'position', label: 'Position', render: (r) => <span className="text-text font-semibold">{r.position}</span> },
  { key: 'hands', label: 'Hands', align: 'right', render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    render: (r, u) => {
      const v = u === 'bb' ? r.won_bb : r.won_usd;
      const fmt = u === 'bb' ? `${v.toFixed(1)} BB` : `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
      return <span className={colorVal(v)}>{fmt}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    render: (r, u) => renderRake(r, u),
  },
];

const monthColumns: Column<MonthBreakdown>[] = [
  { key: 'month', label: 'Month', render: (r) => <span className="text-text">{formatMonth(r.month)}</span> },
  { key: 'hands', label: 'Hands', align: 'right', render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    render: (r, u) => {
      const v = u === 'bb' ? r.won_bb : r.won_usd;
      const fmt = u === 'bb' ? `${v.toFixed(1)} BB` : `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
      return <span className={colorVal(v)}>{fmt}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.bb_per_100)}>{r.bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    render: (r) => <span className={colorVal(r.ev_bb_per_100)}>{r.ev_bb_per_100.toFixed(2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    render: (r, u) => renderRake(r, u),
  },
];
