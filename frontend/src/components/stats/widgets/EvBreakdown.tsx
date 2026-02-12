import { useQuery } from '@tanstack/react-query';
import { getEvBreakdown } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function EvBreakdown({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.evBreakdown(statKey, params),
    queryFn: ({ signal }) => getEvBreakdown(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-16 w-full" />;
  if (!data || data.scenarios.length === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">EV by Outcome</div>
      <div className="space-y-0.5">
        {data.scenarios.map((sc) => (
          <div key={sc.label} className="flex items-center justify-between text-[11px]">
            <span className="text-foreground/80">{sc.label}</span>
            <span className="flex items-center gap-1.5">
              <span className={sc.bb_per_100 >= 0 ? 'text-green' : 'text-red'}>
                {sc.bb_per_100 >= 0 ? '+' : ''}{sc.bb_per_100.toFixed(1)} bb/100
              </span>
              <span className="text-muted-foreground">({sc.hands})</span>
            </span>
          </div>
        ))}
      </div>
      {data.overall_hands > 0 && (
        <div className="flex items-center justify-between text-[11px] mt-1 pt-1 border-t border-border">
          <span className="font-medium">Overall</span>
          <span className={data.overall_bb_per_100 >= 0 ? 'text-green font-medium' : 'text-red font-medium'}>
            {data.overall_bb_per_100 >= 0 ? '+' : ''}{data.overall_bb_per_100.toFixed(1)} bb/100
          </span>
        </div>
      )}
    </div>
  );
}
