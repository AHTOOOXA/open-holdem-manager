import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { HeroStats } from '@/lib/api';
import { computeLeaks } from '@/lib/benchmarks';

/** Stats where the value is a ratio, not a percentage */
const RATIO_STATS = new Set(['af_flop', 'af_turn', 'af_river']);

function LeakCard({ leak }: { leak: { statKey: string; displayName: string; value: number; sample: number; benchmark: { low: number; high: number; fix: string }; handFilterUrl: string } }) {
  const isRatio = RATIO_STATS.has(leak.statKey);
  const valueDisplay = isRatio ? leak.value.toFixed(1) : `${Math.round(leak.value)}%`;
  const targetDisplay = isRatio
    ? `target ${leak.benchmark.low}–${leak.benchmark.high}`
    : `target ${leak.benchmark.low}–${leak.benchmark.high}%`;

  return (
    <div className="flex flex-col gap-1 p-2.5 bg-surface rounded border border-border">
      <span className="text-[13px] font-semibold text-text">{leak.displayName}</span>
      <div className="flex items-baseline gap-2 text-[12px]">
        <span className="font-mono text-red font-semibold">{valueDisplay}</span>
        <span className="text-text-muted">{targetDisplay}</span>
        <span className="text-text-muted">({leak.sample.toLocaleString()} hands)</span>
      </div>
      <p className="text-[11px] text-text-muted leading-relaxed">{leak.benchmark.fix}</p>
      <Link
        to={leak.handFilterUrl}
        className="text-[11px] text-primary hover:underline self-start mt-0.5"
      >
        View hands &rarr;
      </Link>
    </div>
  );
}

export default function LeakSummaryPanel({ stats }: { stats: HeroStats }) {
  const [collapsed, setCollapsed] = useState(false);

  const leaks = useMemo(() => computeLeaks(stats), [stats]);

  if (leaks.length === 0) return null;

  return (
    <div className="border border-border rounded overflow-hidden mb-3">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 bg-surface hover:bg-surface-hover transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-bold text-text">Your Top Leaks</span>
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-red/10 text-red">
            {leaks.length} {leaks.length === 1 ? 'leak' : 'leaks'}
          </span>
        </div>
        <span className="text-[11px] text-text-muted">{collapsed ? '\u25B6' : '\u25BC'}</span>
      </button>

      {/* Body */}
      {!collapsed && leaks.length > 0 && (
        <div className="px-3 py-2">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {leaks.map((leak) => (
              <LeakCard key={leak.statKey} leak={leak} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
