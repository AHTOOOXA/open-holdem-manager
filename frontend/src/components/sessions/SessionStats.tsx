/**
 * Stats block of a Sessions page: two anchor groups, a dashed separator, then the grid. Recipe
 * stats are never clickable (sessions.md §5.2).
 */
import { useQuery } from '@tanstack/react-query';
import { HEAVY_QUERY } from '@/lib/query-policy';
import { getSpot, queryKeyOf } from '@/lib/reports/api';
import type { ReportQuery, SpotRecipe, SpotStat } from '@/lib/reports/types';
import { Skeleton } from '@/components/ui/skeleton';
import { StatNumber } from '@/components/reports/tabs/StatsTab';

function Anchor({ stat }: { stat: SpotStat }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="truncate text-xl font-semibold text-foreground">
        <StatNumber stat={stat} />
      </span>
      <span className="truncate text-label text-muted-foreground">{stat.caption}</span>
    </div>
  );
}

function GridStat({ stat }: { stat: SpotStat }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="truncate text-label text-muted-foreground">{stat.caption}</span>
      <span className="truncate text-sm text-foreground">
        <StatNumber stat={stat} />
      </span>
    </div>
  );
}

export default function SessionStats({ query, recipe }: { query: ReportQuery; recipe: SpotRecipe }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['reports', 'spot', recipe, queryKeyOf(query)],
    queryFn: ({ signal }) => getSpot({ ...query, recipe }, signal),
    ...HEAVY_QUERY,
  });

  if (isPending) {
    return (
      <div className="flex flex-col gap-3" aria-busy>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-money-neg">
        Failed to load stats{error instanceof Error ? `: ${error.message}` : ''}
      </p>
    );
  }
  if (data.stats.length === 0) return <p className="text-sm text-muted-foreground">No results yet</p>;

  const group = (g: SpotStat['group']) => data.stats.filter((s) => s.group === g);
  const anchors1 = group('anchor1');
  const anchors2 = group('anchor2');
  // A response without groups (should not happen for a recipe) still shows everything in the grid
  const grid = data.stats.filter((s) => s.group === 'grid' || s.group === undefined);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start gap-x-8 gap-y-2">
        {anchors1.length > 0 && (
          <div className="flex gap-6">{anchors1.map((s) => <Anchor key={s.id} stat={s} />)}</div>
        )}
        {anchors2.length > 0 && (
          <div className="flex gap-6">{anchors2.map((s) => <Anchor key={s.id} stat={s} />)}</div>
        )}
      </div>
      {grid.length > 0 && (
        <>
          <div role="separator" className="border-t border-dashed border-border" />
          <div className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-x-4 gap-y-2">
            {grid.map((s) => <GridStat key={s.id} stat={s} />)}
          </div>
        </>
      )}
    </div>
  );
}
