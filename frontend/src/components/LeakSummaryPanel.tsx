import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { HeroStats } from '@/lib/api';
import { computeLeaks } from '@/lib/benchmarks';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

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
    <Card className="gap-0 py-0 overflow-hidden">
      {/* Header */}
      <CardHeader
        className="px-3 py-2 border-b border-border cursor-pointer hover:bg-surface-hover transition-colors"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-[13px] font-bold text-text">Your Top Leaks</CardTitle>
            <Badge variant="destructive" className="text-[11px]">
              {leaks.length} {leaks.length === 1 ? 'leak' : 'leaks'}
            </Badge>
          </div>
          <span className="text-[11px] text-text-muted">{collapsed ? '\u25B6' : '\u25BC'}</span>
        </div>
      </CardHeader>

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
    </Card>
  );
}
