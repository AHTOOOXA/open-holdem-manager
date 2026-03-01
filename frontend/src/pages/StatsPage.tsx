import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { getHeroStats, createCheckpoint } from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { queryKeys } from '@/lib/query-keys';
import { getPresetDates } from '@/lib/date-presets';
import type { DatePreset } from '@/lib/date-presets';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import LeakSummaryPanel from '@/components/LeakSummaryPanel';
import DriftPanel from '@/components/DriftPanel';
import StatDetailPanel from '@/components/stats/StatDetailPanel';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { useDrift } from '@/hooks/useDrift';
import {
  TooltipProvider,
} from '@/components/ui/tooltip';
import StatsCard from '@/components/stats/StatsCard';

// ── Detail View ─────────────────────────────────────────────────────

function StatsDetailView({ statKey }: { statKey: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);

  const position = searchParams.get('pos') ?? undefined;

  const filterParams = useMemo(() => ({
    stakes: searchParams.get('stakes') ?? undefined,
    game_mode: searchParams.get('game_mode') ?? undefined,
    date_from: searchParams.get('date_from') ?? undefined,
    date_to: searchParams.get('date_to') ?? undefined,
  }), [searchParams]);

  const statsQueryParams = useMemo(() => ({
    ...filterParams,
    last_n: searchParams.get('last_n') ? parseInt(searchParams.get('last_n')!, 10) : undefined,
  }), [filterParams, searchParams]);

  const { data: heroStats } = useQuery({
    queryKey: queryKeys.stats.hero(statsQueryParams),
    queryFn: () => getHeroStats(statsQueryParams),
  });

  const handlePositionChange = useCallback((pos: string | undefined) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (pos) {
        next.set('pos', pos);
      } else {
        next.delete('pos');
      }
      return next;
    }, { replace: true });
    setPage(1);
  }, [setSearchParams]);

  return (
    <div className="h-[calc(100vh-6rem)]">
      <StatDetailPanel
        statKey={statKey}
        position={position}
        onPositionChange={handlePositionChange}
        filterParams={filterParams}
        heroStats={heroStats}
        page={page}
        perPage={perPage}
        onPageChange={setPage}
        onPerPageChange={setPerPage}
      />
    </div>
  );
}

// ── List View ───────────────────────────────────────────────────────

function StatsListView() {
  const navigate = useNavigate();

  // Decimal precision toggle: 0 = integers, 1 = one decimal
  const [decimals, setDecimals] = useState<0 | 1>(0);

  // Filters
  const [stakes, setStakes] = useState<string>('');
  const [gameMode, setGameMode] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [activePreset, setActivePreset] = useState<DatePreset>('all');
  const [lastN, setLastN] = useState<string>('');
  const [checkpointId, setCheckpointId] = useState<string | null>(null);
  const { checkpoints, activeWorkspaceId, refetchCheckpoints } = useWorkspace();

  // Debounce lastN
  const [debouncedLastN, setDebouncedLastN] = useState<string>('');
  const lastNTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    lastNTimer.current = setTimeout(() => setDebouncedLastN(lastN), 500);
    return () => clearTimeout(lastNTimer.current);
  }, [lastN]);

  const lastNParsed = debouncedLastN ? parseInt(debouncedLastN, 10) : undefined;
  const filterParams = useMemo(() => ({
    stakes: stakes || undefined,
    game_mode: gameMode || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    last_n: lastNParsed && lastNParsed > 0 ? lastNParsed : undefined,
  }), [stakes, gameMode, dateFrom, dateTo, lastNParsed]);

  // Shared filter options
  const { data: filterOpts } = useFilterOptions();

  // Stats query
  const { data: stats, isPending: loading } = useQuery({
    queryKey: queryKeys.stats.hero(filterParams),
    queryFn: () => getHeroStats(filterParams),
  });

  // Drift detection
  const { driftMap, stats: driftStats, totalHands: driftTotalHands } = useDrift({
    stakes: filterParams.stakes,
    game_mode: filterParams.game_mode,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
    enabled: (stats?.hands ?? 0) >= 20000,
  });

  const handleStatClick = useCallback((key: string, position?: string) => {
    const params = new URLSearchParams();
    if (position) params.set('pos', position);
    if (stakes) params.set('stakes', stakes);
    if (gameMode) params.set('game_mode', gameMode);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (debouncedLastN) params.set('last_n', debouncedLastN);
    const qs = params.toString();
    navigate(`/stats/${key}${qs ? `?${qs}` : ''}`);
  }, [navigate, stakes, gameMode, dateFrom, dateTo, debouncedLastN]);

  const handlePreset = (preset: DatePreset) => {
    setActivePreset(preset);
    const dates = getPresetDates(preset);
    setDateFrom(dates.date_from ?? '');
    setDateTo(dates.date_to ?? '');
    setCheckpointId(null);
  };

  const handleDateFromChange = (v: string) => {
    setDateFrom(v);
    setActivePreset('all');
    setCheckpointId(null);
  };

  const handleDateToChange = (v: string) => {
    setDateTo(v);
    setActivePreset('all');
  };

  const handleCheckpointChange = (id: string | null) => {
    setCheckpointId(id);
    if (id) {
      const cp = checkpoints.find((c) => String(c.id) === id);
      if (cp) {
        setDateFrom(cp.checkpoint_at.slice(0, 19));
        setActivePreset('all');
      }
    } else {
      setDateFrom('');
    }
  };

  const handleCreateCheckpoint = async (data: { name: string; checkpoint_at: string; note?: string }) => {
    await createCheckpoint(activeWorkspaceId, data);
    await refetchCheckpoints();
  };

  const hasFilters = !!(stakes || gameMode || dateFrom || dateTo || lastN);

  const filterBarContent = (
    <FilterBar
      stakes={stakes}
      onStakesChange={setStakes}
      gameMode={gameMode}
      onGameModeChange={setGameMode}
      dateFrom={dateFrom}
      onDateFromChange={handleDateFromChange}
      dateTo={dateTo}
      onDateToChange={handleDateToChange}
      activePreset={activePreset}
      onPresetChange={handlePreset}
      filterOptions={filterOpts ?? null}
      checkpointId={checkpointId}
      onCheckpointChange={handleCheckpointChange}
      checkpoints={checkpoints}
      onCreateCheckpoint={handleCreateCheckpoint}
    >
      {/* Last N hands */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-muted">Last</span>
        <Input
          type="number"
          value={lastN}
          onChange={(e) => setLastN(e.target.value)}
          placeholder="All"
          min={1}
          className="w-20 h-8 text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        />
        <span className="text-xs text-text-muted">hands</span>
      </div>
    </FilterBar>
  );

  if (loading) return (
    <div className="max-w-6xl mx-auto space-y-2">
      {filterBarContent}
      <p className="text-text-muted p-4 text-center">Loading stats...</p>
    </div>
  );
  if (!stats || stats.hands === 0) {
    return (
      <div className="max-w-6xl mx-auto space-y-2">
        {filterBarContent}
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setStakes(''); setGameMode(''); setDateFrom(''); setDateTo(''); setLastN(''); handlePreset('all'); } : undefined}
        />
      </div>
    );
  }

  const wr = stats.win_rate_bb100;
  const wrEv = stats.win_rate_ev_bb100;

  const wrColor = wr !== null ? (wr >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';
  const wrEvColor = wrEv !== null ? (wrEv >= 0 ? 'text-green' : 'text-red') : 'text-text-muted';

  return (
    <TooltipProvider delayDuration={200}>
      <div className="max-w-6xl mx-auto space-y-2">
        {/* ── Filter Bar ── */}
        {filterBarContent}

        {/* ── Context Bar ── */}
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-1.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-text-muted">{stats.hands.toLocaleString()} hands</span>
              <span className={`text-sm font-bold font-mono ${wrColor}`}>
                {wr !== null ? `${wr >= 0 ? '+' : ''}${wr.toFixed(2)} bb/100` : '\u2014'}
              </span>
              <span className={`text-sm font-bold font-mono ${wrEvColor}`}>
                EV {wrEv !== null ? `${wrEv >= 0 ? '+' : ''}${wrEv.toFixed(2)}` : '\u2014'}
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

        {/* ── Stats Card (all sections) ── */}
        <StatsCard stats={stats} decimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />

        {/* ── Leak Summary Panel ── */}
        {stats.hands >= 200 && <LeakSummaryPanel stats={stats} />}

        {/* ── Drift Panel ── */}
        <DriftPanel stats={driftStats} totalHands={driftTotalHands} />
      </div>
    </TooltipProvider>
  );
}

// ── Router ───────────────────────────────────────────────────────────

export default function StatsPage() {
  const { statKey } = useParams<{ statKey?: string }>();
  if (statKey) return <StatsDetailView statKey={statKey} />;
  return <StatsListView />;
}
