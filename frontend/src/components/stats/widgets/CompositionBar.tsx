import { useQuery } from '@tanstack/react-query';
import { getComposition } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function CompositionBar({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.composition(statKey, params),
    queryFn: ({ signal }) => getComposition(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-12 w-full" />;
  if (!data || data.total === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">Composition ({data.total})</div>
      <div className="flex h-5 rounded overflow-hidden">
        {data.slices.map((sl, i) => {
          if (sl.pct < 1) return null;
          return (
            <div
              key={sl.label}
              className="flex items-center justify-center text-[9px] text-white font-medium"
              style={{ width: `${sl.pct}%`, backgroundColor: COLORS[i % COLORS.length] }}
              title={`${sl.label}: ${sl.pct.toFixed(1)}% (${sl.count})`}
            >
              {sl.pct >= 10 ? `${sl.pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
        {data.slices.map((sl, i) => (
          <span key={sl.label} className="text-[10px] flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
            {sl.label} ({sl.pct.toFixed(0)}%)
          </span>
        ))}
      </div>
    </div>
  );
}
