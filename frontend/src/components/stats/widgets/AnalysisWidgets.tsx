import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getStatTrend, getStatAnalysis } from '@/lib/api';
import type { HeroStats, PositionalStats as PositionalStatsType } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getStatEntry, getWidgetsForStat } from '@/lib/stat-registry';
import PositionalMiniBar from './PositionalMiniBar';
import TrendSparkline from './TrendSparkline';
import ResponseDistribution from './ResponseDistribution';
import RangeHeatmapMini from './RangeHeatmapMini';

interface AnalysisWidgetsProps {
  statKey: string;
  heroStats?: HeroStats;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
  position?: string;
  onPositionChange: (pos: string | undefined) => void;
}

export default function AnalysisWidgets({
  statKey,
  heroStats,
  filterParams,
  position,
  onPositionChange,
}: AnalysisWidgetsProps) {
  const widgets = getWidgetsForStat(statKey);
  const entry = getStatEntry(statKey);

  const showPositionalBar = widgets.includes('positional_bar') && entry?.isPositional;
  const showResponseDist = widgets.includes('response_distribution');
  const showRangeHeatmap = widgets.includes('range_heatmap');
  const showTrend = widgets.includes('trend_sparkline');

  const trendFilterParams = useMemo(() => ({
    position,
    stakes: filterParams.stakes,
    game_mode: filterParams.game_mode,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
  }), [position, filterParams]);

  const { data: trendData, isPending: trendLoading } = useQuery({
    queryKey: queryKeys.stats.trend(statKey, trendFilterParams),
    queryFn: ({ signal }) => getStatTrend(statKey, trendFilterParams, signal),
    enabled: showTrend,
  });

  const { data: analysisData, isPending: analysisLoading } = useQuery({
    queryKey: queryKeys.stats.analysis(statKey, trendFilterParams),
    queryFn: ({ signal }) => getStatAnalysis(statKey, trendFilterParams, signal),
    enabled: showResponseDist,
  });

  // Get positional stats from heroStats (only needed when showing mini-bar)
  const positionalStats = useMemo(() => {
    if (!showPositionalBar || !heroStats || !entry) return null;
    const field = entry.heroStatsField;
    const val = heroStats[field as keyof HeroStats];
    if (val && typeof val === 'object' && 'total' in val) {
      return val as PositionalStatsType;
    }
    return null;
  }, [showPositionalBar, heroStats, entry]);

  const hasAnyWidget = showPositionalBar || showResponseDist || showRangeHeatmap || showTrend;
  if (!hasAnyWidget) return null;

  return (
    <div className="px-3 py-2 border-b border-border shrink-0 space-y-2">
      {showPositionalBar && positionalStats && (
        <PositionalMiniBar
          positionalStats={positionalStats}
          statKey={statKey}
          currentPosition={position}
          onPositionClick={(pos) => onPositionChange(pos === position?.toUpperCase() ? undefined : pos)}
        />
      )}

      {showResponseDist && (
        <ResponseDistribution
          distribution={analysisData?.response_distribution ?? null}
          isLoading={analysisLoading}
        />
      )}

      {showRangeHeatmap && (
        <RangeHeatmapMini
          statKey={statKey}
          filterParams={filterParams}
          position={position}
        />
      )}

      {showTrend && (
        <TrendSparkline
          points={trendData?.points ?? []}
          overallPct={trendData?.overall_pct ?? 0}
          isLoading={trendLoading}
        />
      )}
    </div>
  );
}
