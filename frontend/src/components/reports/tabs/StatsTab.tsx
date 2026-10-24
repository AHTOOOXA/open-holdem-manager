import { useQuery } from '@tanstack/react-query';
import { getSpot } from '@/lib/reports/api';
import { queryKeyOf } from '@/lib/reports/api';
import type { ReportQuery, SpotStat, Step } from '@/lib/reports/types';
import { formatSpotValue, spotTone } from '@/lib/reports/format';
import { StatValue, type StatValueFormat } from '@/components/ui/stat-value';
import { Skeleton } from '@/components/ui/skeleton';
import { count, toneClass } from '@/lib/format';
import { cn } from '@/lib/utils';

interface StatsTabProps {
  query: ReportQuery;
  onOpenStat: (step: Step, title: string) => void;
}

const STAT_VALUE_FORMAT: Partial<Record<SpotStat['format'], StatValueFormat>> = {
  pct: 'pct',
  count: 'number',
  bb100: 'bb100',
};

export function StatNumber({ stat }: { stat: SpotStat }) {
  const tone = spotTone(stat.value, stat.winnings, stat.format);
  const svFormat = STAT_VALUE_FORMAT[stat.format];
  if (svFormat && !tone) return <StatValue value={stat.value} sample={stat.sample} format={svFormat} />;
  if (svFormat && tone) return <StatValue value={stat.value} sample={stat.sample} format={svFormat} tone={tone} />;
  return (
    <span className={cn('tabular-nums', tone && toneClass(tone))}>{formatSpotValue(stat.value, stat.format, stat.sample)}</span>
  );
}

/** Stats upper tab: the spot's stats as a dense two-column list; stats with a filter open the next page. */
export default function StatsTab({ query, onOpenStat }: StatsTabProps) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['reports', 'spot', queryKeyOf(query)],
    queryFn: ({ signal }) => getSpot(query, signal),
  });

  if (isPending) {
    return (
      <div className="grid grid-cols-1 gap-x-6 gap-y-1 p-3 md:grid-cols-2" aria-busy>
        {Array.from({ length: 12 }, (_, i) => (
          <Skeleton key={i} className="h-row-dense w-full" />
        ))}
      </div>
    );
  }
  if (isError) {
    return (
      <p role="alert" className="p-4 text-sm text-money-neg">
        Failed to load stats{error instanceof Error ? `: ${error.message}` : ''}
      </p>
    );
  }
  if (data.hands === 0 || data.stats.length === 0) {
    return <p className="p-4 text-sm text-muted-foreground">No hands match this page.</p>;
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-2 border-b border-border px-3 py-2 text-sm">
        {data.hit_label && <span className="font-medium text-foreground">{data.hit_label}</span>}
        <span className="text-muted-foreground">{count(data.hands)} hands</span>
      </div>
      <ul className="grid grid-cols-1 gap-x-6 px-2 py-2 md:grid-cols-2">
        {data.stats.map((stat) => {
          const row = (
            <>
              <span className="truncate text-muted-foreground">{stat.caption}</span>
              <span className="shrink-0 text-foreground">
                <StatNumber stat={stat} />
              </span>
            </>
          );
          const rowClass = 'flex h-row-dense w-full items-center justify-between gap-3 rounded-control px-2 text-cell';
          return (
            <li key={stat.id}>
              {stat.filter ? (
                <button
                  type="button"
                  title={`Open ${stat.caption}`}
                  onClick={() => onOpenStat(stat.filter as Step, stat.caption)}
                  className={cn(
                    rowClass,
                    'cursor-pointer text-left outline-none hover:bg-overlay-hover focus-visible:ring-2 focus-visible:ring-primary',
                  )}
                >
                  {row}
                </button>
              ) : (
                <div className={rowClass}>{row}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
