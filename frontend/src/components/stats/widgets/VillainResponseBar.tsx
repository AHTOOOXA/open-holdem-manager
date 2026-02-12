import { useQuery } from '@tanstack/react-query';
import { getEvBreakdown } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

const COLORS = ['#6366f1', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6'];

export default function VillainResponseBar({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.evBreakdown(statKey, params),
    queryFn: ({ signal }) => getEvBreakdown(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-12 w-full" />;
  if (!data || data.scenarios.length === 0) return null;

  const total = data.scenarios.reduce((s, sc) => s + sc.hands, 0);
  if (total === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">Villain Response</div>
      <div className="flex h-5 rounded overflow-hidden">
        {data.scenarios.map((sc, i) => {
          const pct = sc.hands / total * 100;
          if (pct < 1) return null;
          return (
            <div
              key={sc.label}
              className="flex items-center justify-center text-[9px] text-white font-medium"
              style={{ width: `${pct}%`, backgroundColor: COLORS[i % COLORS.length] }}
              title={`${sc.label}: ${pct.toFixed(1)}% (${sc.hands})`}
            >
              {pct >= 10 ? `${pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
        {data.scenarios.map((sc, i) => (
          <span key={sc.label} className="text-[10px] flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
            {sc.label}
          </span>
        ))}
      </div>
    </div>
  );
}
