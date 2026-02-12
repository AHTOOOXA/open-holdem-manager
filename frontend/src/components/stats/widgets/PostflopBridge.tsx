import { useQuery } from '@tanstack/react-query';
import { getPostflopBridge } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function PostflopBridge({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.postflopBridge(statKey, params),
    queryFn: ({ signal }) => getPostflopBridge(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-10 w-full" />;
  if (!data || data.cbet_opp === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">Postflop Bridge</div>
      <div className="flex items-center gap-4 text-[12px]">
        <div>
          <span className="text-muted-foreground">CBet: </span>
          <span className="font-medium text-foreground">
            {data.cbet_pct != null ? `${data.cbet_pct.toFixed(0)}%` : '—'}
          </span>
          <span className="text-muted-foreground text-[10px] ml-1">({data.cbet_count}/{data.cbet_opp})</span>
        </div>
        {data.avg_spr != null && (
          <div>
            <span className="text-muted-foreground">SPR: </span>
            <span className="font-medium text-foreground">~{data.avg_spr}</span>
          </div>
        )}
      </div>
    </div>
  );
}
