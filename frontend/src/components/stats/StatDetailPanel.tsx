import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getStatDetailHands } from '@/lib/api';
import type { HeroStats } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getStatDisplayName, getStatEntry } from '@/lib/stat-registry';
import AnalysisWidgets from '@/components/stats/widgets/AnalysisWidgets';
import HandExplorer from '@/components/hands/HandExplorer';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

const POSITIONS = ['All', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

interface StatDetailPanelProps {
  statKey: string;
  position?: string;
  onPositionChange: (pos: string | undefined) => void;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
  heroStats?: HeroStats;
  page: number;
  perPage: number;
  onPageChange: (p: number) => void;
  onPerPageChange: (pp: number) => void;
}

export default function StatDetailPanel({
  statKey,
  position,
  onPositionChange,
  filterParams,
  heroStats,
  page,
  perPage,
  onPageChange,
  onPerPageChange,
}: StatDetailPanelProps) {
  const entry = getStatEntry(statKey);
  const displayName = getStatDisplayName(statKey);
  const isPositional = entry?.isPositional ?? false;

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

  // Build "Open in Hand Explorer" link
  const handExplorerUrl = `/hands?stat_key=${statKey}${position ? `&position=${position.toUpperCase()}` : ''}`;

  // Suppress lint warnings for props used by parent for external state management
  void page; void perPage; void onPageChange; void onPerPageChange;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-border shrink-0">
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold text-text">{displayName}</h3>
            {pct !== null && (
              <span className="text-xs text-text-muted font-mono">
                {pct}% ({statData!.action_count}/{statData!.opportunity_count})
              </span>
            )}
          </div>
          <Link
            to={handExplorerUrl}
            className="text-[11px] text-primary hover:text-primary/80 whitespace-nowrap"
          >
            Open in Hand Explorer &rarr;
          </Link>
        </div>

        {/* Position tabs */}
        {isPositional && (
          <div className="mt-2">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={position ?? 'All'}
              onValueChange={(val) => {
                onPositionChange(val === 'All' ? undefined : val);
              }}
            >
              {POSITIONS.map((pos) => (
                <ToggleGroupItem
                  key={pos}
                  value={pos}
                  className="h-6 text-[11px] px-2"
                >
                  {pos}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}
      </div>

      {/* Analysis Widgets */}
      <AnalysisWidgets
        statKey={statKey}
        heroStats={heroStats}
        filterParams={filterParams}
        position={position}
        onPositionChange={onPositionChange}
      />

      {/* Hand list via HandExplorer */}
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
