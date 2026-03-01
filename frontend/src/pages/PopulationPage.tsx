import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getPopulationOverview,
  getPopulationFullStats,
  getHeroStats,
  getIdentities,
} from '@/lib/api';
import type { PopulationFilterParams } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import EmptyState from '@/components/EmptyState';
import StatsCard from '@/components/stats/StatsCard';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent } from '@/components/ui/card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Shield } from 'lucide-react';
import {
  TooltipProvider,
} from '@/components/ui/tooltip';

const WELL_KNOWN_TAGS = ['me', 'student', 'reg', 'fish', 'coach'] as const;
const TAG_COLORS: Record<string, string> = {
  me: 'bg-primary/20 text-primary border-primary/30',
  student: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  reg: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  fish: 'bg-green/20 text-green border-green/30',
  coach: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

export default function PopulationPage() {
  const [excludeHero, setExcludeHero] = useState(true);
  const [excludeTags, setExcludeTags] = useState<Set<string>>(new Set());
  const [decimals, setDecimals] = useState<0 | 1>(0);

  const { data: identities } = useQuery({
    queryKey: queryKeys.identities.list,
    queryFn: getIdentities,
  });

  const toggleExcludeTag = (tag: string) => {
    setExcludeTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  };

  const filterParams: PopulationFilterParams = {
    min_hands: 0,
    exclude_hero: excludeHero,
    exclude_tags: excludeTags.size > 0 ? Array.from(excludeTags).join(',') : undefined,
  };

  const { data: overview, isPending: overviewLoading } = useQuery({
    queryKey: queryKeys.population.overview(filterParams),
    queryFn: () => getPopulationOverview(filterParams),
  });

  const { data: stats, isPending: statsLoading } = useQuery({
    queryKey: queryKeys.population.fullStats(filterParams),
    queryFn: () => getPopulationFullStats(filterParams),
    enabled: !!overview && overview.player_count > 0,
  });

  const { data: heroStats } = useQuery({
    queryKey: queryKeys.stats.hero({}),
    queryFn: () => getHeroStats(),
  });

  if (overviewLoading) {
    return <p className="text-text-muted text-sm py-8 text-center">Loading population data...</p>;
  }

  if (!overview || overview.player_count === 0) {
    return <EmptyState variant="no-data" />;
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="max-w-6xl mx-auto space-y-2">
        {/* ── Filters ── */}
        <div className="flex items-center gap-4 flex-wrap">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={excludeHero}
              onCheckedChange={(checked) => setExcludeHero(checked === true)}
            />
            <span className="text-[12px] text-text-muted">Exclude Hero</span>
          </label>
        </div>

        {/* ── Exclusion bar ── */}
        {identities && identities.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-[12px] text-text-muted">
              <Shield className="w-3.5 h-3.5" />
              <span>Exclude:</span>
            </div>
            {WELL_KNOWN_TAGS.map((tag) => {
              const hasIdentities = identities.some((id) => id.tags.includes(tag));
              if (!hasIdentities) return null;
              const isActive = excludeTags.has(tag);
              return (
                <button
                  key={tag}
                  onClick={() => toggleExcludeTag(tag)}
                  className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                    isActive
                      ? TAG_COLORS[tag] || 'bg-surface-hover border-border'
                      : 'border-border text-text-muted hover:text-text hover:border-text-muted'
                  }`}
                >
                  {tag}
                  {isActive && (
                    <span className="ml-1 text-[10px]">{identities.filter((id) => id.tags.includes(tag)).reduce((s, id) => s + id.aliases.length, 0)}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {/* ── Context Bar ── */}
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-1.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-text-muted">
                Pool: <span className="font-mono text-text">{overview.player_count.toLocaleString()}</span> players
              </span>
              <span className="text-sm text-text-muted">
                Observations: <span className="font-mono text-text">{overview.observation_count.toLocaleString()}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Precision</span>
              <ToggleGroup
                type="single"
                value={String(decimals)}
                onValueChange={(v) => { if (v) setDecimals(Number(v) as 0 | 1); }}
                className="h-8"
              >
                <ToggleGroupItem value="0" className="h-7 px-2 text-xs font-mono">0</ToggleGroupItem>
                <ToggleGroupItem value="1" className="h-7 px-2 text-xs font-mono">0.0</ToggleGroupItem>
              </ToggleGroup>
            </div>
          </CardContent>
        </Card>

        {/* ── Stats Card ── */}
        {statsLoading && (
          <p className="text-text-muted p-4 text-center">Loading stats...</p>
        )}
        {stats && stats.hands > 0 && (
          <StatsCard stats={stats} decimals={decimals} compareStats={heroStats} />
        )}
      </div>
    </TooltipProvider>
  );
}
