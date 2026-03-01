/**
 * Shared stat display components extracted from StatsPage.
 * Used by StatsPage, CompareTable, and other stat displays.
 */
import type { PositionalStats, StatValue, DriftStat } from '@/lib/api';
import { isDrillable } from '@/lib/stat-registry';
import {
  getBenchmarkForPosition,
  getStatHealth,
  STAT_DISPLAY_NAMES,
} from '@/lib/benchmarks';
import type { BenchmarkRange, StatHealth } from '@/lib/benchmarks';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ── Types ────────────────────────────────────────────────────────────

export type ColorClass = 'text-green' | 'text-red' | 'text-yellow' | 'text-blue' | 'text-text' | 'text-text-muted';

export interface CellDef {
  sv: StatValue | undefined;
  statKey?: string;
  /** The stat key to use for drill-down (overrides statKey if provided) */
  drillKey?: string;
  position?: string;
  decimals?: number;
  colorFn?: (v: number) => ColorClass;
  /** Delta vs compare stats (e.g. population - hero). Rendered as (+X) / (-X) */
  delta?: number | null;
}

// ── Constants ────────────────────────────────────────────────────────

export const HEALTH_COLORS: Record<string, ColorClass> = {
  green: 'text-green',
  yellow: 'text-yellow',
  red: 'text-red',
  neutral: 'text-text',
};

/** Map stat display keys to drift backend keys */
export const STAT_TO_DRIFT_KEY: Record<string, string> = {
  vpip: 'vpip',
  pfr: 'pfr',
  three_bet: 'three_bet',
  fold_to_3bet: 'fold_to_3bet',
  cbet_flop: 'cbet_flop',
  fold_to_cbet_flop: 'fold_to_cbet_flop',
  wtsd: 'went_to_showdown',
  wsd: 'won_at_showdown',
  wwsf: 'wwsf',
  steal: 'steal',
  vs_steal_fold: 'fold_to_steal',
};

// ── Helpers ──────────────────────────────────────────────────────────

export function healthToColor(health: StatHealth): ColorClass {
  return HEALTH_COLORS[health.status] || 'text-text';
}

/** Format a StatValue for display. Returns {text, color, subscript?} */
export function fmtStat(
  sv: StatValue | undefined,
  statKey?: string,
  position?: string,
  decimals: number = 1,
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

// ── Delta Badge ─────────────────────────────────────────────────────

function DeltaBadge({ delta, decimals = 0 }: { delta: number; decimals?: number }) {
  const sign = delta > 0 ? '+' : '';
  const formatted = decimals > 0 ? delta.toFixed(decimals) : Math.round(delta).toString();
  return (
    <span className="ml-1 text-[10px] text-text-muted font-normal">
      ({sign}{formatted})
    </span>
  );
}

// ── Drift Arrow ──────────────────────────────────────────────────────

export function DriftArrow({ drift, statKey }: { drift: DriftStat; statKey?: string }) {
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
          <div className="text-text-muted">
            CI: {drift.ci_lower.toFixed(1)}–{drift.ci_upper.toFixed(1)}%
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

// ── Stat Cell ────────────────────────────────────────────────────────

/** Render a stat cell with optional tooltip, drift arrow, and click handler */
export function StatCell({
  sv,
  statKey,
  drillKey,
  position,
  decimals,
  delta,
  defaultDecimals = 1,
  colorFn,
  driftMap,
  onStatClick,
}: CellDef & {
  defaultDecimals?: number;
  driftMap?: Map<string, DriftStat>;
  onStatClick?: (key: string, position?: string) => void;
}) {
  const effectiveDecimals = decimals ?? defaultDecimals;
  const { text, color, sub, health, benchmark } = fmtStat(sv, statKey, position, effectiveDecimals, colorFn);

  const driftKey = statKey ? STAT_TO_DRIFT_KEY[statKey] : undefined;
  const drift = driftKey && driftMap?.get(driftKey);

  const effectiveDrillKey = drillKey ?? statKey;
  const clickable = isDrillable(effectiveDrillKey) && sv?.sample != null && sv.sample > 0;

  const hasTooltip = benchmark && health && sv?.value != null && health.status !== 'neutral';
  const displayName = statKey ? (STAT_DISPLAY_NAMES[statKey] || statKey) : '';

  const handleClick = () => {
    if (clickable && effectiveDrillKey && onStatClick) {
      onStatClick(effectiveDrillKey, position && position !== 'total' ? position : undefined);
    }
  };

  const inner = (
    <span className={color}>
      {text}
      {sub && <sub className="text-[9px] ml-0.5 text-text-muted select-none">{sub}</sub>}
      {drift && <DriftArrow drift={drift} statKey={statKey} />}
      {delta != null && <DeltaBadge delta={delta} decimals={effectiveDecimals} />}
    </span>
  );

  const cellClass = [
    'py-1 px-1.5 text-center font-mono text-[13px] leading-snug',
    clickable ? 'cursor-pointer hover:bg-primary/10 transition-colors' : '',
  ].join(' ');

  if (!hasTooltip) {
    return (
      <td className={cellClass} onClick={handleClick}>
        {inner}
      </td>
    );
  }

  const tip = health.direction === 'low' ? benchmark.tipLow : health.direction === 'high' ? benchmark.tipHigh : undefined;

  return (
    <td className={cellClass} onClick={handleClick}>
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

/** Positional table: Stat | Total | pos columns */
export function PosTable({
  headers,
  rows,
  defaultDecimals,
  driftMap,
  onStatClick,
}: {
  headers: string[];
  rows: { label: string; cells: CellDef[]; groupEnd?: boolean }[];
  defaultDecimals?: number;
  driftMap?: Map<string, DriftStat>;
  onStatClick?: (key: string, position?: string) => void;
}) {
  return (
    <table className="w-full">
      {headers.length > 0 && (
        <thead>
          <tr className="border-b border-border">
            <th className="py-1 px-1.5 text-left text-[11px] font-semibold text-text-muted uppercase w-28">
              Stat
            </th>
            {headers.map((h) => (
              <th key={h} className="py-1 px-1.5 text-center text-[11px] font-semibold text-text-muted uppercase">
                {h}
              </th>
            ))}
          </tr>
        </thead>
      )}
      <tbody>
        {rows.map((row) => (
          <tr key={row.label} className={`hover:bg-surface-hover ${row.groupEnd ? 'border-b border-border/50' : 'border-b border-border/20'}`}>
            <td className="py-1 px-1.5 text-[12px] text-text-muted whitespace-nowrap">{row.label}</td>
            {row.cells.map((cell, i) => (
              <StatCell
                key={i}
                {...cell}
                defaultDecimals={defaultDecimals}
                driftMap={driftMap}
                onStatClick={onStatClick}
              />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Key-value grid: two columns of label + value pairs */
export function KVGrid({
  items,
  defaultDecimals,
  driftMap,
  onStatClick,
}: {
  items: (CellDef & { label: string })[];
  defaultDecimals?: number;
  driftMap?: Map<string, DriftStat>;
  onStatClick?: (key: string, position?: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 p-2">
      {items.map((item) => {
        const effectiveDecimals = item.decimals ?? defaultDecimals;
        const { text, color, sub, health, benchmark } = fmtStat(item.sv, item.statKey, item.position, effectiveDecimals, item.colorFn);
        const displayName = item.statKey ? (STAT_DISPLAY_NAMES[item.statKey] || item.statKey) : item.label;

        // Drift arrow for KV items
        const driftKey = item.statKey ? STAT_TO_DRIFT_KEY[item.statKey] : undefined;
        const drift = driftKey && driftMap?.get(driftKey);

        const effectiveDrillKey = item.drillKey ?? item.statKey;
        const clickable = isDrillable(effectiveDrillKey) && item.sv?.sample != null && item.sv.sample > 0;

        const hasTooltip = benchmark && health && item.sv?.value != null && health.status !== 'neutral';
        const tip = health?.direction === 'low' ? benchmark?.tipLow : health?.direction === 'high' ? benchmark?.tipHigh : undefined;

        const handleClick = () => {
          if (clickable && effectiveDrillKey && onStatClick) {
            onStatClick(effectiveDrillKey);
          }
        };

        const valueSpan = (
          <span className={`font-mono text-[13px] ${color}`}>
            {text}
            {sub && <sub className="text-[9px] ml-0.5 text-text-muted select-none">{sub}</sub>}
            {drift && <DriftArrow drift={drift} statKey={item.statKey} />}
          </span>
        );

        return (
          <div
            key={item.label}
            className={[
              'flex items-baseline justify-between py-0.5 px-1 rounded-sm',
              clickable ? 'cursor-pointer hover:bg-primary/10 transition-colors' : '',
            ].join(' ')}
            onClick={handleClick}
          >
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

/** Compute delta between two StatValues (a - b). Returns null if either is missing. */
export function svDelta(a: StatValue | undefined, b: StatValue | undefined): number | null {
  if (a?.value == null || b?.value == null) return null;
  return Math.round((a.value - b.value) * 10) / 10;
}

/** Build positional row from PositionalStats */
export function posRow(
  label: string,
  ps: PositionalStats | undefined,
  statKey?: string,
  positions: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'],
  drillKey?: string,
  groupEnd?: boolean,
  comparePs?: PositionalStats,
) {
  if (!ps) {
    return {
      label,
      cells: positions.map(() => ({ sv: undefined as StatValue | undefined, statKey, drillKey })),
      groupEnd,
    };
  }
  return {
    label,
    cells: positions.map((p) => ({
      sv: ps[p], statKey, position: p, drillKey,
      delta: comparePs ? svDelta(ps[p], comparePs[p]) : undefined,
    })),
    groupEnd,
  };
}

/** Inline stat value for the missed-cbet / showdown sections */
export function InlineStat({ sv, statKey, drillKey, position, delta, defaultDecimals = 1, driftMap, onStatClick }: {
  sv: StatValue | undefined;
  statKey?: string;
  drillKey?: string;
  position?: string;
  delta?: number | null;
  defaultDecimals?: number;
  driftMap?: Map<string, DriftStat>;
  onStatClick?: (key: string, position?: string) => void;
}) {
  const { text, color, sub, health, benchmark } = fmtStat(sv, statKey, position, defaultDecimals);
  const displayName = statKey ? (STAT_DISPLAY_NAMES[statKey] || statKey) : '';

  const driftKeyVal = statKey ? STAT_TO_DRIFT_KEY[statKey] : undefined;
  const drift = driftKeyVal && driftMap?.get(driftKeyVal);

  const effectiveDrillKey = drillKey ?? statKey;
  const clickable = isDrillable(effectiveDrillKey) && sv?.sample != null && sv.sample > 0;

  const hasTooltip = benchmark && health && sv?.value != null && health.status !== 'neutral';
  const tip = health?.direction === 'low' ? benchmark?.tipLow : health?.direction === 'high' ? benchmark?.tipHigh : undefined;

  const handleClick = () => {
    if (clickable && effectiveDrillKey && onStatClick) {
      onStatClick(effectiveDrillKey);
    }
  };

  const inner = (
    <span className={`font-mono text-[13px] ${color}`}>
      {text}
      {sub && <sub className="text-[9px] ml-0.5 text-text-muted select-none">{sub}</sub>}
      {drift && <DriftArrow drift={drift} statKey={statKey} />}
      {delta != null && <DeltaBadge delta={delta} decimals={defaultDecimals} />}
    </span>
  );

  const wrapperClass = [
    'inline-block px-1 rounded-sm',
    clickable ? 'cursor-pointer hover:bg-primary/10 transition-colors' : '',
  ].join(' ');

  if (!hasTooltip) {
    return <span className={wrapperClass} onClick={handleClick}>{inner}</span>;
  }

  return (
    <span className={wrapperClass} onClick={handleClick}>
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
    </span>
  );
}
