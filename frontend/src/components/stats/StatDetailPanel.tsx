import { useQuery } from '@tanstack/react-query';
import { getStatDetailHands } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getStatDisplayName } from '@/lib/stat-registry';
import HandExplorer from '@/components/hands/HandExplorer';

interface StatDetailPanelProps {
  statKey: string;
  position?: string;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
}

export default function StatDetailPanel({
  statKey,
  position,
  filterParams,
}: StatDetailPanelProps) {
  const displayName = getStatDisplayName(statKey);
  const posLabel = position ? ` ${position.toUpperCase()}` : '';

  // Lightweight query just for action_count / opportunity_count in the header
  const { data: statData } = useQuery({
    queryKey: queryKeys.stats.detail(statKey, {
      position,
      stakes: filterParams.stakes,
      game_mode: filterParams.game_mode,
      date_from: filterParams.date_from,
      date_to: filterParams.date_to,
      page: 1,
      per_page: 1,
    }),
    queryFn: () => getStatDetailHands(statKey, {
      position,
      stakes: filterParams.stakes,
      game_mode: filterParams.game_mode,
      date_from: filterParams.date_from,
      date_to: filterParams.date_to,
      page: 1,
      per_page: 1,
    }),
  });

  const pct = statData && statData.opportunity_count > 0
    ? ((statData.action_count / statData.opportunity_count) * 100).toFixed(1)
    : null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-border shrink-0">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold text-text">{displayName}{posLabel}</h3>
          {pct !== null && (
            <span className="text-xs text-text-muted font-mono">
              {pct}% ({statData!.action_count}/{statData!.opportunity_count})
            </span>
          )}
        </div>
      </div>

      {/* Hand list */}
      <HandExplorer
        key={`${statKey}-${position ?? ''}`}
        fixedParams={{
          stat_key: statKey,
          position: position,
          stakes: filterParams.stakes,
          date_from: filterParams.date_from,
          date_to: filterParams.date_to,
        }}
        defaultPerPage={25}
        className="flex-1 min-h-0"
      />
    </div>
  );
}
