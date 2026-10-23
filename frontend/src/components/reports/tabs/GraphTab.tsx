import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getGraphData } from '@/lib/api';
import { queryKeyOf } from '@/lib/reports/api';
import type { ReportQuery } from '@/lib/reports/types';
import ResultsChart, { type LineToggle } from '@/components/results/ResultsChart';
import { Skeleton } from '@/components/ui/skeleton';
import { count, fixed, moneyClass, signedBb } from '@/lib/format';

const LINES: ReadonlySet<LineToggle> = new Set<LineToggle>(['ev', 'showdown']);

/** Graph upper tab: the cumulative results chart for the page's chain, with a compact summary line. */
export default function GraphTab({ query }: { query: ReportQuery }) {
  const chain = query.chain;
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['reports', 'graph', queryKeyOf(query)],
    queryFn: () => getGraphData({ chain, player_id: query.player_id }),
  });

  const summary = useMemo(() => {
    const points = data?.points ?? [];
    const last = points.length ? points[points.length - 1] : null;
    if (!last) return null;
    const n = points.length;
    return {
      hands: n,
      won: last.cumulative_bb,
      rate: (last.cumulative_bb / n) * 100,
      evRate: (last.cumulative_ev_bb / n) * 100,
      hasEv: last.cumulative_ev_bb !== last.cumulative_bb,
    };
  }, [data]);

  if (isPending) return <Skeleton className="m-2 h-[320px] w-auto rounded" aria-busy />;
  if (isError) {
    return (
      <p role="alert" className="p-4 text-sm text-money-neg">
        Failed to load graph{error instanceof Error ? `: ${error.message}` : ''}
      </p>
    );
  }
  if (!summary) return <p className="p-4 text-sm text-muted-foreground">No hands match this page.</p>;

  return (
    <div className="flex flex-col gap-1 p-2">
      <ResultsChart points={data.points} sessions={data.sessions} variance={data.variance} unit="bb" lines={LINES} height={320} />
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 px-2 text-xs text-muted-foreground">
        <span>{count(summary.hands)} hands</span>
        <span>
          Won <span className={moneyClass(summary.won, 1)}>{signedBb(summary.won)} BB</span>
        </span>
        <span>
          <span className={moneyClass(summary.rate)}>{fixed(summary.rate, 2)}</span> bb/100
        </span>
        {summary.hasEv && (
          <span>
            <span className={moneyClass(summary.evRate)}>{fixed(summary.evRate, 2)}</span> EV bb/100
          </span>
        )}
      </div>
    </div>
  );
}
