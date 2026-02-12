import { useQuery } from '@tanstack/react-query';
import { getByContext } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function ByContextBreakdown({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.byContext(statKey, params),
    queryFn: ({ signal }) => getByContext(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-16 w-full" />;
  if (!data || data.buckets.length === 0) return null;

  const maxPct = Math.max(...data.buckets.map(b => b.pct ?? 0), 1);

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">By {data.dimension.replace(/_/g, ' ')}</div>
      <div className="space-y-1">
        {data.buckets.map((b) => (
          <div key={b.label} className="flex items-center gap-2 text-[11px]">
            <span className="w-8 text-right text-muted-foreground shrink-0">{b.label}</span>
            <div className="flex-1 h-3.5 bg-surface rounded overflow-hidden">
              <div
                className="h-full bg-primary rounded"
                style={{ width: `${((b.pct ?? 0) / maxPct) * 100}%` }}
              />
            </div>
            <span className="w-12 text-right shrink-0">
              {b.pct != null ? `${b.pct.toFixed(1)}%` : '\u2014'}
            </span>
            <span className="w-8 text-right text-muted-foreground shrink-0">({b.opportunities})</span>
          </div>
        ))}
      </div>
    </div>
  );
}
