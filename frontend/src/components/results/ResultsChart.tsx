import { useState, useMemo, useCallback } from 'react';
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
import type { Checkpoint, GraphPoint, SessionMarker, VarianceStats } from '@/lib/api';
import { fixed, formatClockTime, formatDateTime } from '@/lib/format';
import { chartColors, axisTick } from '@/lib/chart-theme';
import { ChartTooltipBox } from '@/components/ChartTooltipBox';

export type LineToggle = 'ev' | 'showdown' | 'rake' | 'ci' | 'sessions';

const LINE_COLORS = chartColors;

function formatXTick(value: number) {
  if (value >= 1000) return `${fixed(value / 1000, value % 1000 === 0 ? 0 : 1)}k`;
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

export function sessionDurationHours(s: SessionMarker): number {
  if (!s.start_time || !s.end_time) return 0;
  return (new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 3600000;
}


interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number | number[]; color: string; payload?: Record<string, unknown> }>;
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
    <ChartTooltipBox>
      <div style={{ marginBottom: 4, color: chartColors.tooltipMuted }}>
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
              <span>{name}: {prefix}{fixed(entry.value[0], 1)}{suffix} to {prefix}{fixed(entry.value[1], 1)}{suffix}</span>
            </div>
          );
        }
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color, display: 'inline-block', flexShrink: 0 }} />
            <span>{name}: {prefix}{fixed(entry.value, 2)}{suffix}</span>
          </div>
        );
      })}
      {activeSession && (() => {
        const hands = activeSession.end_hand - activeSession.start_hand + 1;
        const hrs = sessionDurationHours(activeSession);
        const hph = hrs > 0 ? Math.round(hands / hrs) : 0;
        return (
          <div style={{ marginTop: 6, paddingTop: 6, borderTop: `1px solid ${chartColors.tooltipBorder}`, color: chartColors.tooltipMuted, fontSize: 11 }}>
            Session: {formatClockTime(activeSession.start_time)} – {formatClockTime(activeSession.end_time)}
            <span style={{ marginLeft: 8 }}>({hands} hands{hph > 0 ? ` · ${hph} hands/hr` : ''})</span>
          </div>
        );
      })()}
    </ChartTooltipBox>
  );
}

export interface ResultsChartProps {
  points: GraphPoint[];
  sessions: SessionMarker[];
  variance: VarianceStats | null;
  unit: 'bb' | 'usd';
  lines: ReadonlySet<LineToggle>;
  /** Checkpoints to draw as reference lines (already filtered by the caller's visibility toggle). */
  checkpoints?: Checkpoint[];
  height?: number;
}

/** Cumulative results chart: legend line plus the Recharts chart (Actual, All-in EV, showdown split, rake, CI, sessions). */
export default function ResultsChart({ points: data, sessions, variance, unit, lines, checkpoints = [], height = 400 }: ResultsChartProps) {
  const [activeSession, setActiveSession] = useState<SessionMarker | null>(null);
  const hasEVData = useMemo(() => data.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [data]);

  const handleChartMouseMove = useCallback((e: { activeLabel?: string | number }) => {
    if (!e.activeLabel || !lines.has('sessions')) { setActiveSession(null); return; }
    const hand = Number(e.activeLabel);
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

  // Checkpoint reference lines — map each checkpoint to the nearest graph data point
  const checkpointLines = useMemo(() => {
    if (checkpoints.length === 0 || data.length === 0) return [];
    const firstTime = new Date(data[0].played_at).getTime();
    const lastTime = new Date(data[data.length - 1].played_at).getTime();
    return checkpoints
      .map(cp => {
        const cpTime = new Date(cp.checkpoint_at).getTime();
        // Skip if outside the graph's date range
        if (cpTime < firstTime || cpTime > lastTime) return null;
        // Find nearest data point by timestamp
        let bestIdx = 0;
        let bestDiff = Math.abs(cpTime - new Date(data[0].played_at).getTime());
        for (let i = 1; i < data.length; i++) {
          const diff = Math.abs(cpTime - new Date(data[i].played_at).getTime());
          if (diff < bestDiff) {
            bestDiff = diff;
            bestIdx = i;
          }
        }
        return { handNumber: data[bestIdx].hand_number, name: cp.name, id: cp.id };
      })
      .filter((x): x is { handNumber: number; name: string; id: number } => x !== null);
  }, [checkpoints, data]);

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

  return (
    <>
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
            <span className="inline-block w-4 h-0.5 rounded" style={{ background: LINE_COLORS.session, borderTop: `1px dashed ${chartColors.axis}` }} />
            Sessions
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartDataEnriched} margin={{ top: 4, right: 16, bottom: 4, left: 8 }} onMouseMove={handleChartMouseMove} onMouseLeave={handleChartMouseLeave}>
          <defs>
            <linearGradient id="gradientMain" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={LINE_COLORS.main} stopOpacity={0.25} />
              <stop offset="100%" stopColor={LINE_COLORS.main} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={chartColors.grid} strokeDasharray="none" />
          <XAxis
            dataKey="hand_number"
            type="number"
            domain={[0, 'dataMax']}
            ticks={niceXTicks(data.length)}
            stroke={chartColors.axis}
            tick={axisTick(11)}
            tickFormatter={formatXTick}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            stroke={chartColors.axis}
            tick={axisTick(11)}
            axisLine={false}
            tickLine={false}
            width={50}
            tickFormatter={(v: number) => unit === 'usd' ? `$${v}` : String(v)}
          />
          <Tooltip
            content={<CustomTooltip unit={unit} tooltipNames={tooltipNames} activeSession={activeSession} />}
          />
          <ReferenceLine y={0} stroke={chartColors.zeroLine} strokeDasharray="4 4" />
          {lines.has('sessions') && activeSession && (
            <ReferenceArea
              x1={activeSession.start_hand}
              x2={activeSession.end_hand}
              fill={chartColors.main}
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
                value: formatClockTime(s.start_time),
                position: 'top',
                fill: chartColors.axis,
                fontSize: 9,
              }}
            />
          ))}
          {checkpointLines.map(cp => (
            <ReferenceLine
              key={`checkpoint-${cp.id}`}
              x={cp.handNumber}
              stroke="var(--color-text-muted)"
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{
                value: cp.name,
                position: 'insideTopRight',
                fill: 'var(--color-text-muted)',
                fontSize: 10,
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
    </>
  );
}
