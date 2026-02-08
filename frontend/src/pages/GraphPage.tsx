import { useState, useEffect, useMemo } from 'react';
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
import { getGraphData } from '@/lib/api';
import type { GraphPoint } from '@/lib/api';

function formatXTick(value: number) {
  if (value >= 1000) return `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  return String(value);
}

function StatCard({
  label,
  bb,
  usd,
  bbColor,
  usdColor,
  border,
}: {
  label: string;
  bb: string;
  usd: string;
  bbColor?: string;
  usdColor?: string;
  border?: string;
}) {
  return (
    <div
      className="bg-surface rounded-lg border border-border px-4 py-3"
      style={border ? { borderLeftWidth: 3, borderLeftColor: border } : undefined}
    >
      <div className="text-[11px] text-text-muted mb-1.5 uppercase tracking-wide">{label}</div>
      <div className={`text-lg font-bold font-mono leading-tight ${bbColor ?? ''}`}>{bb}</div>
      <div className={`text-sm font-mono leading-tight mt-0.5 ${usdColor ?? 'text-text-muted'}`}>{usd}</div>
    </div>
  );
}

export default function GraphPage() {
  const [data, setData] = useState<GraphPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [unit, setUnit] = useState<'bb' | 'usd'>('bb');
  const [showEV, setShowEV] = useState(true);

  useEffect(() => {
    getGraphData()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const hasEVData = useMemo(() => data.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [data]);

  // Downsample to ~1000 points max for chart performance
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

  if (loading) return <p className="text-text-muted">Loading graph...</p>;
  if (data.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-text-muted text-lg">No hands imported yet.</p>
        <p className="text-text-muted text-sm mt-2">Upload hand histories first.</p>
      </div>
    );
  }

  const last = data[data.length - 1];

  const mainKey = unit === 'bb' ? 'cumulative_bb' : 'cumulative_usd';
  const evKey = unit === 'bb' ? 'cumulative_ev_bb' : 'cumulative_ev_usd';

  // Stat values — always both units
  const n = data.length;
  const wonBB = last.cumulative_bb;
  const wonUSD = last.cumulative_usd;
  const evBB = last.cumulative_ev_bb;
  const evUSD = last.cumulative_ev_usd;
  const rakeBB = last.cumulative_rake_bb;
  const rakeUSD = last.cumulative_rake_usd;
  const rateBB = n > 0 ? (wonBB / n) * 100 : 0;
  const rateUSD = n > 0 ? (wonUSD / n) * 100 : 0;
  const evRateBB = n > 0 ? (evBB / n) * 100 : 0;
  const evRateUSD = n > 0 ? (evUSD / n) * 100 : 0;

  const clr = (v: number) => v >= 0 ? 'text-green' : 'text-red';
  const brd = (v: number) => v >= 0 ? '#22c55e' : '#ef4444';
  const fmtBB = (v: number) => `${v.toFixed(1)} BB`;
  const fmtUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
  const fmtRateBB = (v: number) => `${v.toFixed(2)} bb/100`;
  const fmtRateUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}/100`;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Results Graph</h1>
          <p className="text-sm text-text-muted mt-0.5">
            {data.length.toLocaleString()} hands
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <div className="flex rounded overflow-hidden border border-border">
            <button
              className={`px-3 py-1.5 text-sm transition-colors ${
                unit === 'bb'
                  ? 'bg-primary text-white'
                  : 'bg-surface text-text-muted hover:text-text'
              }`}
              onClick={() => setUnit('bb')}
            >
              BB
            </button>
            <button
              className={`px-3 py-1.5 text-sm transition-colors ${
                unit === 'usd'
                  ? 'bg-primary text-white'
                  : 'bg-surface text-text-muted hover:text-text'
              }`}
              onClick={() => setUnit('usd')}
            >
              $
            </button>
          </div>
          {hasEVData && (
            <button
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                showEV
                  ? 'bg-yellow-600 text-white'
                  : 'bg-surface border border-border text-text-muted hover:text-text'
              }`}
              onClick={() => setShowEV(!showEV)}
            >
              EV Line
            </button>
          )}
        </div>
      </div>

      <div className="bg-surface rounded-lg border border-border p-4">
        {/* In-chart legend */}
        <div className="flex gap-4 mb-2 ml-12 text-xs text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 bg-[#818cf8] rounded" />
            Actual
          </span>
          {showEV && hasEVData && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-4 h-0.5 rounded" style={{ background: '#eab308', opacity: 0.8 }} />
              All-in EV
            </span>
          )}
        </div>
        <ResponsiveContainer width="100%" height={480}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <defs>
              <linearGradient id="gradientMain" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="#1e1e2e" strokeDasharray="none" />
            <XAxis
              dataKey="hand_number"
              stroke="#555570"
              tick={{ fontSize: 11, fill: '#555570' }}
              tickFormatter={formatXTick}
              axisLine={false}
              tickLine={false}
              minTickGap={60}
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
              formatter={(value: number, name: string) => {
                const prefix = unit === 'usd' ? '$' : '';
                const suffix = unit === 'bb' ? ' BB' : '';
                const formatted = `${prefix}${value.toFixed(2)}${suffix}`;
                const label = name.includes('EV') ? 'All-in EV' : 'Actual';
                return [formatted, label];
              }}
              labelFormatter={(label) => `Hand #${Number(label).toLocaleString()}`}
            />
            <ReferenceLine y={0} stroke="#444460" strokeDasharray="4 4" />
            <Area
              type="monotone"
              dataKey={mainKey}
              name="Actual"
              fill="url(#gradientMain)"
              stroke="#818cf8"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
              baseValue={0}
            />
            {showEV && hasEVData && (
              <Line
                type="monotone"
                dataKey={evKey}
                name="All-in EV"
                stroke="#eab308"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                strokeDasharray="6 3"
                opacity={0.8}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className={`grid gap-3 ${hasEVData ? 'grid-cols-5' : 'grid-cols-3'}`}>
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
        {hasEVData && (
          <StatCard
            label="EV Won"
            bb={fmtBB(evBB)}
            usd={fmtUSD(evUSD)}
            bbColor={clr(evBB)}
            usdColor={clr(evUSD)}
            border={brd(evBB)}
          />
        )}
        {hasEVData && (
          <StatCard
            label="EV Winrate"
            bb={fmtRateBB(evRateBB)}
            usd={fmtRateUSD(evRateUSD)}
            bbColor={clr(evRateBB)}
            usdColor={clr(evRateUSD)}
            border={brd(evRateBB)}
          />
        )}
        <StatCard
          label="Rake"
          bb={fmtBB(rakeBB)}
          usd={fmtUSD(rakeUSD)}
          bbColor="text-red"
          usdColor="text-red"
          border="#ef4444"
        />
      </div>
    </div>
  );
}
