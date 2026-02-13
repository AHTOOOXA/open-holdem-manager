import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { getSizing } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

export default function SizingHistogram({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.sizing(statKey, params),
    queryFn: ({ signal }) => getSizing(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-24 w-full" />;
  if (!data || data.buckets.length === 0) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">
        Raise Sizing
        {data.avg_size_bb != null && (
          <span className="ml-2 text-foreground">(avg: {data.avg_size_bb} BB)</span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={80}>
        <BarChart data={data.buckets} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
          <XAxis dataKey="size_bb" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ fontSize: 11, background: '#1e1e2e', border: '1px solid #333', borderRadius: 6 }}
            formatter={(v: number | undefined) => [`${v ?? 0}%`, 'Pct']}
            labelFormatter={(l) => `${l} BB`}
          />
          <Bar dataKey="pct" fill="#6366f1" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
