import { useQuery } from '@tanstack/react-query';
import { getEvBreakdown } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';
import type { VillainResponseBenchmark } from '@/lib/benchmarks';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
  benchmarks?: VillainResponseBenchmark;
}

const COLORS = ['#6366f1', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6'];

export default function VillainResponseBar({ statKey, filterParams, position, benchmarks }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.evBreakdown(statKey, params),
    queryFn: ({ signal }) => getEvBreakdown(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-12 w-full" />;
  if (!data || data.scenarios.length === 0) return null;

  const total = data.scenarios.reduce((s, sc) => s + sc.hands, 0);
  if (total === 0) return null;

  // Compute segment percentages and cumulative positions for benchmark markers
  const pcts = data.scenarios.map((sc) => sc.hands / total * 100);
  const segments = data.scenarios.map((sc, i) => ({
    ...sc,
    pct: pcts[i],
    start: pcts.slice(0, i).reduce((a, b) => a + b, 0),
    end: pcts.slice(0, i + 1).reduce((a, b) => a + b, 0),
  }));

  // Calculate benchmark marker positions (cumulative boundaries between segments)
  const benchmarkMarkers: { left: number; label: string; benchPct: number }[] = [];
  if (benchmarks) {
    const allButLast = segments.slice(0, -1);
    allButLast.reduce((cum, seg) => {
      const benchPct = benchmarks[seg.label];
      if (benchPct == null) return cum;
      const left = cum + benchPct;
      benchmarkMarkers.push({ left, label: seg.label, benchPct });
      return left;
    }, 0);
  }

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">Villain Response</div>
      <div className="relative flex h-5 rounded overflow-hidden">
        {segments.map((sc, i) => {
          if (sc.pct < 1) return null;
          return (
            <div
              key={sc.label}
              className="flex items-center justify-center text-[9px] text-white font-medium"
              style={{ width: `${sc.pct}%`, backgroundColor: COLORS[i % COLORS.length] }}
              title={`${sc.label}: ${sc.pct.toFixed(1)}% (${sc.hands})`}
            >
              {sc.pct >= 10 ? `${sc.pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
        {benchmarkMarkers.map((m) => (
          <div
            key={m.label}
            className="absolute top-0 h-full w-0.5 bg-white/80"
            style={{ left: `${m.left}%` }}
            title={`Population avg boundary: ${m.left}%`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
        {segments.map((sc, i) => (
          <span key={sc.label} className="text-[10px] flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
            {sc.label}
          </span>
        ))}
      </div>
    </div>
  );
}
