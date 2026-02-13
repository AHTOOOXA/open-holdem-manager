import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getStatTrend, getStatAnalysis } from '@/lib/api';
import type { HeroStats, PositionalStats as PositionalStatsType } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getStatEntry, getWidgetsForStat, type WidgetType } from '@/lib/stat-registry';
import PositionalMiniBar from './PositionalMiniBar';
import TrendSparkline from './TrendSparkline';
import ResponseDistribution from './ResponseDistribution';
import RangeHeatmapMini from './RangeHeatmapMini';
import VillainResponseBar from './VillainResponseBar';
import EvBreakdown from './EvBreakdown';
import SizingHistogram from './SizingHistogram';
import FoldEquity from './FoldEquity';
import ByContextBreakdown from './ByContextBreakdown';
import CompositionBar from './CompositionBar';
import MoneyBurned from './MoneyBurned';
import ContinuingRangeHeatmap from './ContinuingRangeHeatmap';
import GapIndicator from './GapIndicator';
import PostflopBridge from './PostflopBridge';
import OpportunityContext from './OpportunityContext';
import RangeComparison from './RangeComparison';
import { VILLAIN_RESPONSE_BENCHMARKS, type VillainResponseBenchmark } from '@/lib/benchmarks';

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

  const hasResponseDist = widgets.includes('response_distribution');
  const hasTrend = widgets.includes('trend_sparkline');

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
    enabled: hasTrend,
  });

  const { data: analysisData, isPending: analysisLoading } = useQuery({
    queryKey: queryKeys.stats.analysis(statKey, trendFilterParams),
    queryFn: ({ signal }) => getStatAnalysis(statKey, trendFilterParams, signal),
    enabled: hasResponseDist,
  });

  const positionalStats = useMemo(() => {
    if (!heroStats || !entry || !entry.isPositional) return null;
    const field = entry.heroStatsField;
    const val = heroStats[field as keyof HeroStats];
    if (val && typeof val === 'object' && 'total' in val) {
      return val as PositionalStatsType;
    }
    return null;
  }, [heroStats, entry]);

  if (widgets.length === 0) return null;

  const stdProps = { statKey, filterParams, position };

  function renderWidget(type: WidgetType) {
    switch (type) {
      case 'positional_bar':
        return positionalStats ? (
          <PositionalMiniBar
            positionalStats={positionalStats}
            statKey={statKey}
            currentPosition={position}
            onPositionClick={(pos) => onPositionChange(pos === position?.toUpperCase() ? undefined : pos)}
          />
        ) : null;
      case 'response_distribution':
        return (
          <ResponseDistribution
            distribution={analysisData?.response_distribution ?? null}
            isLoading={analysisLoading}
          />
        );
      case 'range_heatmap':
        return <RangeHeatmapMini {...stdProps} />;
      case 'trend_sparkline':
        return (
          <TrendSparkline
            points={trendData?.points ?? []}
            overallPct={trendData?.overall_pct ?? 0}
            isLoading={trendLoading}
          />
        );
      case 'villain_response': {
        const posKey = position?.toUpperCase();
        const benchmarks: VillainResponseBenchmark | undefined =
          posKey ? VILLAIN_RESPONSE_BENCHMARKS[statKey]?.[posKey] : undefined;
        return <VillainResponseBar {...stdProps} benchmarks={benchmarks} />;
      }
      case 'ev_breakdown':
        return <EvBreakdown {...stdProps} />;
      case 'sizing_histogram':
        return <SizingHistogram {...stdProps} />;
      case 'fold_equity':
        return <FoldEquity {...stdProps} />;
      case 'by_context':
        return <ByContextBreakdown {...stdProps} />;
      case 'composition':
        return <CompositionBar {...stdProps} />;
      case 'money_burned':
        return <MoneyBurned {...stdProps} />;
      case 'continuing_range':
        return <ContinuingRangeHeatmap {...stdProps} />;
      case 'gap_indicator':
        return <GapIndicator heroStats={heroStats} />;
      case 'postflop_bridge':
        return <PostflopBridge {...stdProps} />;
      case 'opportunity_context':
        return <OpportunityContext statKey={statKey} heroStats={heroStats} />;
      case 'range_comparison':
        return <RangeComparison statKey={statKey} filterParams={filterParams} />;
      case 'contextual_rate':
        return null; // Requires explicit label/value/sample — used standalone, not via registry
      default:
        return null;
    }
  }

  return (
    <div className="px-3 py-2 border-b border-border shrink-0 space-y-2">
      {widgets.map((type) => {
        const node = renderWidget(type);
        return node ? <div key={type}>{node}</div> : null;
      })}
    </div>
  );
}
