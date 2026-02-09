import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { HeroStats } from '@/lib/api';
import { computeLeaks, computeOnTrack } from '@/lib/benchmarks';
import type { Leak, OnTrackStat } from '@/lib/benchmarks';

function LeakCard({ leak }: { leak: Leak }) {
  const costPerHundred = (Math.abs(leak.value - (leak.benchmark.low + leak.benchmark.high) / 2) * leak.benchmark.weight / 100).toFixed(1);

  return (
    <div className="flex flex-col gap-1 p-2.5 bg-surface rounded border border-border">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-text">{leak.displayName}</span>
        <span className="text-[11px] px-1.5 py-0.5 rounded bg-red/15 text-red font-mono">
          ~{costPerHundred} bb/100
        </span>
      </div>
      <div className="flex items-baseline gap-2 text-[12px]">
        <span className="font-mono text-red font-semibold">{Math.round(leak.value)}%</span>
        <span className="text-text-muted">
          target {leak.benchmark.low}–{leak.benchmark.high}%
        </span>
        <span className="text-text-muted">({leak.sample} hands)</span>
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

function OnTrackItem({ stat }: { stat: OnTrackStat }) {
  return (
    <div className="flex items-baseline gap-1.5 text-[12px]">
      <span className="text-green">&#10003;</span>
      <span className="text-text-muted">{stat.displayName}</span>
      <span className="font-mono text-green">{Math.round(stat.value)}%</span>
      <span className="text-text-muted/60">({stat.low}–{stat.high})</span>
    </div>
  );
}

export default function LeakSummaryPanel({ stats }: { stats: HeroStats }) {
  const [collapsed, setCollapsed] = useState(false);

  const leaks = useMemo(() => computeLeaks(stats), [stats]);
  const onTrack = useMemo(() => computeOnTrack(stats), [stats]);

  if (leaks.length === 0 && onTrack.length === 0) return null;

  return (
    <div className="border border-border rounded overflow-hidden mb-3">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 bg-surface hover:bg-surface-hover transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-bold text-text">
            {leaks.length > 0 ? 'Your Top Leaks' : 'Stats Overview'}
          </span>
          {leaks.length > 0 && (
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-red/10 text-red">
              {leaks.length} {leaks.length === 1 ? 'leak' : 'leaks'}
            </span>
          )}
          {onTrack.length > 0 && (
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-green/10 text-green">
              {onTrack.length} on track
            </span>
          )}
        </div>
        <span className="text-[11px] text-text-muted">{collapsed ? '&#9654;' : '&#9660;'}</span>
      </button>

      {/* Body */}
      {!collapsed && (
        <div className="px-3 py-2 space-y-3">
          {/* Leaks */}
          {leaks.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {leaks.map((leak) => (
                <LeakCard key={leak.statKey} leak={leak} />
              ))}
            </div>
          )}

          {/* On Track */}
          {onTrack.length > 0 && (
            <div>
              {leaks.length > 0 && (
                <div className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">
                  On Track
                </div>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                {onTrack.map((s) => (
                  <OnTrackItem key={s.statKey} stat={s} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
