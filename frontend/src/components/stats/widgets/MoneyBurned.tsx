import { useQuery } from '@tanstack/react-query';
import { getMoney } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function MoneyBurned({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.money(statKey, params),
    queryFn: ({ signal }) => getMoney(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-10 w-full" />;
  if (!data || data.hands === 0) return null;

  const color = data.total_bb >= 0 ? 'text-green' : 'text-red';

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-0.5">Total Impact</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-xl font-bold ${color}`}>
          {data.total_bb >= 0 ? '+' : ''}{data.total_bb.toFixed(1)} bb
        </span>
        <span className="text-[10px] text-muted-foreground">
          ({data.bb_per_100 >= 0 ? '+' : ''}{data.bb_per_100.toFixed(1)} bb/100, {data.hands} hands)
        </span>
      </div>
    </div>
  );
}
