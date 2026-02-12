import { useQuery } from '@tanstack/react-query';
import { getFoldEquity } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function FoldEquity({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.foldEquity(statKey, params),
    queryFn: ({ signal }) => getFoldEquity(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-10 w-full" />;
  if (!data || data.total === 0) return null;

  const color = data.fold_pct >= 60 ? 'text-green' : data.fold_pct >= 40 ? 'text-primary' : 'text-red';

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">Fold Equity</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-xl font-bold ${color}`}>{data.fold_pct.toFixed(1)}%</span>
        <span className="text-[10px] text-muted-foreground">({data.fold_count}/{data.total})</span>
      </div>
    </div>
  );
}
