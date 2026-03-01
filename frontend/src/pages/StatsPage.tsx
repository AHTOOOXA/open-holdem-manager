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
import { PosTable, InlineStat, posRow } from '@/components/stats/StatDisplay';

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

  const fullPosHeaders = ['Tot', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
  const fullPosKeys: ('total' | 'ep' | 'mp' | 'co' | 'btn' | 'sb' | 'bb')[] = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'];

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
        <Card className="gap-0 py-0 overflow-hidden">

          {/* ── PRE-FLOP ── */}
          <div className="px-3 py-1.5 border-b border-border">
            <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Pre-Flop</div>
          </div>
          <div className="flex flex-col lg:flex-row">
            {/* Left: Positional table */}
            <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
              <PosTable
                headers={fullPosHeaders}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  // Group: Entry
                  posRow('VPIP',          stats.vpip,            'vpip',         fullPosKeys),
                  posRow('PFR',           stats.pfr,             'pfr',          fullPosKeys),
                  posRow('Open Raise',    stats.open_raise,      'open_raise',   fullPosKeys),
                  posRow('Limp',          stats.limp,            'limp',         fullPosKeys, undefined, true),
                  // Group: vs Open
                  posRow('Call Open',     stats.call_open_raise, undefined,      fullPosKeys, 'call_open_raise'),
                  posRow('3-Bet',         stats.three_bet,       'three_bet',    fullPosKeys, undefined, true),
                  // Group: vs 3-Bet
                  posRow('Fold to 3-Bet', stats.fold_to_3bet,    'fold_to_3bet', fullPosKeys),
                  posRow('4-Bet',         stats.four_bet,        'four_bet',     fullPosKeys, undefined, true),
                  // Group: vs 4-Bet
                  posRow('Fold to 4-Bet', stats.fold_to_4bet,    'fold_to_4bet', fullPosKeys),
                ]}
              />
            </div>

            {/* Right: Preflop extras */}
            <div className="w-full lg:w-40 lg:shrink-0">
              <PosTable
                headers={[]}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  { label: 'Squeeze', cells: [{ sv: stats.squeeze, drillKey: 'squeeze' }] },
                  { label: '5-Bet', cells: [{ sv: stats.five_bet, drillKey: 'five_bet' }] },
                  { label: 'Call 4-Bet', cells: [{ sv: stats.call_4bet, drillKey: 'call_4bet' }] },
                  { label: 'Limp-Fold', cells: [{ sv: stats.limp_fold, drillKey: 'limp_fold' }] },
                  { label: '4-Bet-Fold', cells: [{ sv: stats.four_bet_fold, drillKey: 'four_bet_fold' }] },
                ]}
              />
            </div>
          </div>

          {/* ── STEAL ── */}
          <div className="px-3 py-1.5 border-y border-border">
            <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Steal</div>
          </div>
          <div className="flex flex-col lg:flex-row">
            {/* Left: Steal table (Total, BTN, SB) */}
            <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
              <PosTable
                headers={['Tot', 'BTN', 'SB']}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  {
                    label: 'Steal',
                    cells: [
                      { sv: stats.steal.total, statKey: 'steal', drillKey: 'steal', position: 'total' },
                      { sv: stats.steal.btn, statKey: 'steal', drillKey: 'steal', position: 'btn' },
                      { sv: stats.steal.sb, statKey: 'steal', drillKey: 'steal', position: 'sb' },
                    ],
                  },
                  {
                    label: 'Fold to 3Bet',
                    cells: [
                      { sv: stats.fold_to_3bet_steal.total, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'total' },
                      { sv: stats.fold_to_3bet_steal.btn, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'btn' },
                      { sv: stats.fold_to_3bet_steal.sb, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'sb' },
                    ],
                  },
                  {
                    label: '4-Bet',
                    cells: [
                      { sv: stats.four_bet_steal.total, statKey: 'four_bet', drillKey: 'four_bet', position: 'total' },
                      { sv: stats.four_bet_steal.btn, statKey: 'four_bet', drillKey: 'four_bet', position: 'btn' },
                      { sv: stats.four_bet_steal.sb, statKey: 'four_bet', drillKey: 'four_bet', position: 'sb' },
                    ],
                  },
                  {
                    label: '4-Bet-Fold',
                    cells: [
                      { sv: stats.four_bet_fold_steal.total, drillKey: 'four_bet_fold_steal', position: 'total' },
                      { sv: stats.four_bet_fold_steal.btn, drillKey: 'four_bet_fold_steal', position: 'btn' },
                      { sv: stats.four_bet_fold_steal.sb, drillKey: 'four_bet_fold_steal', position: 'sb' },
                    ],
                  },
                ]}
              />
            </div>

            {/* Right: vs Steal (SB, BB) */}
            <div className="flex-1 min-w-0 overflow-x-auto">
              <div className="px-3 py-1 text-[10px] text-text-muted uppercase tracking-widest font-semibold border-b border-border/30">
                vs. Steal
              </div>
              <PosTable
                headers={['SB', 'BB']}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  {
                    label: 'Fold',
                    cells: [
                      { sv: stats.vs_steal_fold.sb, statKey: 'vs_steal_fold', drillKey: 'fold_to_steal', position: 'sb' },
                      { sv: stats.vs_steal_fold.bb, statKey: 'vs_steal_fold', drillKey: 'fold_to_steal', position: 'bb' },
                    ],
                  },
                  {
                    label: 'Call',
                    cells: [
                      { sv: stats.vs_steal_call.sb, drillKey: 'call_steal', position: 'sb' },
                      { sv: stats.vs_steal_call.bb, drillKey: 'call_steal', position: 'bb' },
                    ],
                  },
                  {
                    label: '3-Bet',
                    cells: [
                      { sv: stats.vs_steal_3bet.sb, drillKey: 'three_bet_vs_steal', position: 'sb' },
                      { sv: stats.vs_steal_3bet.bb, drillKey: 'three_bet_vs_steal', position: 'bb' },
                    ],
                  },
                ]}
              />
            </div>
          </div>

          {/* ── POSTFLOP ── */}
          <div className="px-3 py-1.5 border-y border-border">
            <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Postflop</div>
          </div>
          <div className="flex flex-col lg:flex-row">
            {/* Left: Postflop stats by street */}
            <div className="flex-1 min-w-0 overflow-x-auto lg:border-r border-border">
              <PosTable
                headers={['Flop', 'Turn', 'River']}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  {
                    label: 'C-Bet',
                    cells: [
                      { sv: stats.cbet_flop.total, statKey: 'cbet_flop', drillKey: 'cbet_flop', position: 'total' },
                      { sv: stats.cbet_turn.total, statKey: 'cbet_turn', drillKey: 'cbet_turn', position: 'total' },
                      { sv: stats.cbet_river.total, statKey: 'cbet_river', drillKey: 'cbet_river', position: 'total' },
                    ],
                  },
                  {
                    label: 'Fold to CBet',
                    cells: [
                      { sv: stats.fold_to_cbet_flop.total, statKey: 'fold_to_cbet_flop', drillKey: 'fold_to_cbet_flop', position: 'total' },
                      { sv: stats.fold_to_cbet_turn.total, statKey: 'fold_to_cbet_turn', drillKey: 'fold_to_cbet_turn', position: 'total' },
                      { sv: stats.fold_to_cbet_river.total, drillKey: 'fold_to_cbet_river', position: 'total' },
                    ],
                  },
                  {
                    label: 'Aggression',
                    cells: [
                      { sv: stats.af_flop, statKey: 'af_flop', drillKey: 'af_flop', decimals: 1 },
                      { sv: stats.af_turn, statKey: 'af_turn', drillKey: 'af_turn', decimals: 1 },
                      { sv: stats.af_river, statKey: 'af_river', drillKey: 'af_river', decimals: 1 },
                    ],
                  },
                  {
                    label: 'Agg Freq',
                    cells: [
                      { sv: stats.afq_flop, drillKey: 'afq_flop' },
                      { sv: stats.afq_turn, drillKey: 'afq_turn' },
                      { sv: stats.afq_river, drillKey: 'afq_river' },
                    ],
                  },
                  {
                    label: 'Donk Bet',
                    cells: [
                      { sv: stats.donk_bet_flop, drillKey: 'donk_bet_flop' },
                      { sv: stats.donk_bet_turn, drillKey: 'donk_bet_turn' },
                      { sv: stats.donk_bet_river, drillKey: 'donk_bet_river' },
                    ],
                  },
                ]}
              />
            </div>

            {/* Right: vs CBet Flop (Fold/Call/Raise) */}
            <div className="flex-1 min-w-0 overflow-x-auto">
              <div className="px-3 py-1 text-[10px] text-text-muted uppercase tracking-widest font-semibold border-b border-border/30">
                vs. C-Bet Flop
              </div>
              <PosTable
                headers={['Fold', 'Call', 'Raise']}
                defaultDecimals={decimals}
                driftMap={driftMap}
                onStatClick={handleStatClick}
                rows={[
                  {
                    label: 'Raised Pot',
                    cells: [
                      { sv: stats.fold_cbet_flop_raised, drillKey: 'fold_cbet_flop_raised' },
                      { sv: stats.call_cbet_flop_raised, drillKey: 'call_cbet_flop_raised' },
                      { sv: stats.raise_cbet_flop_raised, drillKey: 'raise_cbet_flop_raised' },
                    ],
                  },
                  {
                    label: '3-Bet Pot',
                    cells: [
                      { sv: stats.fold_cbet_flop_3bet, drillKey: 'fold_cbet_flop_3bet' },
                      { sv: stats.call_cbet_flop_3bet, drillKey: 'call_cbet_flop_3bet' },
                      { sv: stats.raise_cbet_flop_3bet, drillKey: 'raise_cbet_flop_3bet' },
                    ],
                  },
                ]}
              />
            </div>
          </div>

          {/* ── MISSED C-BET ── */}
          <div className="px-3 py-1.5 border-y border-border">
            <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Missed C-Bet</div>
          </div>
          <div className="flex gap-0">
            {/* Left: Missed CBet breakdown */}
            <div className="flex-1 min-w-0 p-2 border-r border-border">
              <div className="space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-[13px] text-text font-medium">Missed C-Bet</span>
                  <InlineStat sv={stats.missed_cbet_flop} drillKey="missed_cbet_flop" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                </div>
                <div className="pl-4 border-l-2 border-border/30 ml-1 space-y-0.5">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">In Position</span>
                    <InlineStat sv={stats.missed_cbet_flop_ip} drillKey="missed_cbet_flop_ip" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                    <InlineStat sv={stats.missed_cbet_fold_ip} drillKey="missed_cbet_fold_ip" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">Out of Position</span>
                    <InlineStat sv={stats.missed_cbet_flop_oop} drillKey="missed_cbet_flop_oop" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">&rarr; Fold</span>
                    <InlineStat sv={stats.missed_cbet_fold_oop} drillKey="missed_cbet_fold_oop" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                </div>
              </div>
            </div>

            {/* Right: vs Missed CBet */}
            <div className="flex-1 min-w-0 p-2">
              <div className="space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-[13px] text-text font-medium">vs. Missed C-Bet</span>
                  <InlineStat sv={stats.vs_missed_cbet} drillKey="vs_missed_cbet" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                </div>
                <div className="pl-4 border-l-2 border-border/30 ml-1 space-y-0.5">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">Bet In Position</span>
                    <InlineStat sv={stats.vs_missed_cbet_bet_ip} drillKey="vs_missed_cbet_bet_ip" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">Check | Fold</span>
                    <InlineStat sv={stats.vs_missed_cbet_check_fold_ip} drillKey="vs_missed_cbet_check_fold_ip" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">Bet OOP Turn</span>
                    <InlineStat sv={stats.vs_missed_cbet_bet_oop_turn} drillKey="vs_missed_cbet_bet_oop_turn" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-text-muted">Check-Fold</span>
                    <InlineStat sv={stats.vs_missed_cbet_check_fold_oop} drillKey="vs_missed_cbet_check_fold_oop" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── SHOWDOWN ── */}
          <div className="px-3 py-1.5 border-y border-border">
            <div className="text-[11px] font-bold uppercase tracking-wider text-primary">Showdown</div>
          </div>
          <div className="grid grid-cols-3 divide-x divide-border">
            <div className="px-4 py-2 text-center">
              <div className="text-[12px] text-text-muted mb-1">WTSD</div>
              <InlineStat sv={stats.wtsd} statKey="wtsd" drillKey="went_to_showdown" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
            </div>
            <div className="px-4 py-2 text-center">
              <div className="text-[12px] text-text-muted mb-1">W$SD</div>
              <InlineStat sv={stats.wsd} statKey="wsd" drillKey="won_at_showdown" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
            </div>
            <div className="px-4 py-2 text-center">
              <div className="text-[12px] text-text-muted mb-1">WWSF</div>
              <InlineStat sv={stats.wwsf} statKey="wwsf" drillKey="wwsf" defaultDecimals={decimals} driftMap={driftMap} onStatClick={handleStatClick} />
            </div>
          </div>
        </Card>

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
