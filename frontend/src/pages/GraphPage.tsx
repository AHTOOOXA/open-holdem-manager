import { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { HEAVY_QUERY } from '@/lib/query-policy';
import {
  getGraphData,
  getResultsBreakdown,
  createCheckpoint,
} from '@/lib/api';
import type {
  SessionMarker,
  StakeBreakdown,
  MonthBreakdown,
  PositionBreakdown,
} from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { queryKeys } from '@/lib/query-keys';
import { getPresetDates } from '@/lib/date-presets';
import type { DatePreset } from '@/lib/date-presets';
import { formatStakes } from '@/lib/utils';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Toggle } from '@/components/ui/toggle';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { fixed, usd, moneyClass, bbUnits } from '@/lib/format';
import { chartColors } from '@/lib/chart-theme';
import ResultsChart, { sessionDurationHours } from '@/components/results/ResultsChart';
import { graphHands } from '@/components/results/graph-hands';
import type { LineToggle } from '@/components/results/ResultsChart';

const LINE_COLORS = chartColors;


function totalSessionHours(sessions: SessionMarker[]): number {
  return sessions.reduce((sum, s) => sum + sessionDurationHours(s), 0);
}

function formatMonth(ym: string): string {
  const [y, m] = ym.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

export default function GraphPage() {
  // Data

  // Filters
  const [stakes, setStakes] = useState<string>('');
  const [gameMode, setGameMode] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [activePreset, setActivePreset] = useState<DatePreset>('all');
  const [lastN, setLastN] = useState<string>('');

  // Checkpoints
  const { checkpoints, activeWorkspaceId, refetchCheckpoints } = useWorkspace();
  const [checkpointId, setCheckpointId] = useState<string | null>(null);
  const [showCheckpoints, setShowCheckpoints] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('ohm_show_checkpoints');
      return stored === null ? true : stored === 'true';
    } catch {
      return true;
    }
  });

  // Display toggles
  const [unit, setUnit] = useState<'bb' | 'usd'>('bb');
  const [lines, setLines] = useState<Set<LineToggle>>(new Set(['ev', 'showdown', 'sessions']));

  const toggle = (line: LineToggle) => {
    setLines(prev => {
      const next = new Set(prev);
      if (next.has(line)) next.delete(line);
      else next.add(line);
      return next;
    });
  };

  // Debounce lastN so typing doesn't trigger a refetch on every keystroke
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

  // Graph data query
  const { data: graphResp, isPending: graphLoading } = useQuery({
    queryKey: queryKeys.graph.data(filterParams),
    queryFn: ({ signal }) => getGraphData(filterParams, signal),
    ...HEAVY_QUERY,
  });

  const data = useMemo(() => graphResp?.points ?? [], [graphResp]);
  const sessions = useMemo(() => graphResp?.sessions ?? [], [graphResp]);
  const variance = graphResp?.variance ?? null;

  // Breakdown query
  const { data: breakdown, isPending: breakdownLoading } = useQuery({
    queryKey: queryKeys.graph.breakdown(filterParams),
    queryFn: ({ signal }) => getResultsBreakdown(filterParams, signal),
    ...HEAVY_QUERY,
  });

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

  const hasEVData = useMemo(() => data.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [data]);


  // Helpers


  // Toggle button helper
  const toggleBtn = (key: LineToggle, label: string, color: string, show = true) =>
    show && (
      <Toggle
        key={key}
        size="sm"
        className="h-7 text-xs data-[state=on]:text-background"
        pressed={lines.has(key)}
        onPressedChange={() => toggle(key)}
        style={lines.has(key) ? { backgroundColor: color } : undefined}
      >
        {label}
      </Toggle>
    );

  const hasFilters = !!(stakes || gameMode || dateFrom || dateTo || lastN);

  // Stat card data from last graph point
  const last = data.length > 0 ? data[data.length - 1] : null;
  const n = graphHands(graphResp);

  const wonBB = last?.cumulative_bb ?? 0;
  const wonUSD = last?.cumulative_usd ?? 0;
  const evBB = last?.cumulative_ev_bb ?? 0;
  const evUSD = last?.cumulative_ev_usd ?? 0;
  const rakeBB = last?.cumulative_rake_bb ?? 0;
  const rakeUSD = last?.cumulative_rake_usd ?? 0;
  const jackpotBB = last?.cumulative_jackpot_bb ?? 0;
  const jackpotUSD = last?.cumulative_jackpot_usd ?? 0;
  const sdBB = last?.cumulative_showdown_bb ?? 0;
  const sdUSD = last?.cumulative_showdown_usd ?? 0;
  const nsdBB = last?.cumulative_nonshowdown_bb ?? 0;
  const nsdUSD = last?.cumulative_nonshowdown_usd ?? 0;

  const rateBB = n > 0 ? (wonBB / n) * 100 : 0;
  const evRateBB = n > 0 ? (evBB / n) * 100 : 0;
  const rakePerBB = n > 0 ? (rakeBB / n) * 100 : 0;
  const sdRateBB = n > 0 ? (sdBB / n) * 100 : 0;
  const nsdRateBB = n > 0 ? (nsdBB / n) * 100 : 0;

  const totalHrs = totalSessionHours(sessions);
  const handsPerHour = totalHrs > 0 ? Math.round(n / totalHrs) : 0;
  const usdPerHour = totalHrs > 0 ? wonUSD / totalHrs : 0;
  const bbPerHour = totalHrs > 0 ? wonBB / totalHrs : 0;

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

  const displayToolbar = (
    <div className="flex items-center gap-2.5 px-2 py-1">
      <ToggleGroup type="single" value={unit} onValueChange={(v) => { if (v) setUnit(v as 'bb' | 'usd'); }}>
        <ToggleGroupItem value="bb" className="h-7 text-xs px-3">BB</ToggleGroupItem>
        <ToggleGroupItem value="usd" className="h-7 text-xs px-3">$</ToggleGroupItem>
      </ToggleGroup>
      {toggleBtn('ev', 'EV', LINE_COLORS.ev, hasEVData)}
      {toggleBtn('showdown', 'SD', LINE_COLORS.showdown)}
      {toggleBtn('rake', 'Rake', LINE_COLORS.rake)}
      {toggleBtn('ci', 'CI', LINE_COLORS.ci, !!variance)}
      {toggleBtn('sessions', 'Sessions', LINE_COLORS.session, sessions.length > 1)}
      {checkpoints.length > 0 && (
        <Toggle
          size="sm"
          pressed={showCheckpoints}
          onPressedChange={(v) => {
            setShowCheckpoints(v);
            localStorage.setItem('ohm_show_checkpoints', String(v));
          }}
          className="h-7 text-xs"
        >
          Checkpoints
        </Toggle>
      )}
    </div>
  );

  // Empty state
  if (!graphLoading && !breakdownLoading && data.length === 0 && !breakdown?.by_stakes.length) {
    return (
      <div className="max-w-6xl mx-auto space-y-1.5">
        {filterBarContent}
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setStakes(''); setGameMode(''); setDateFrom(''); setDateTo(''); setLastN(''); handlePreset('all'); } : undefined}
        />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-1.5">
      {/* Filter Bar */}
      {filterBarContent}

      {/* Graph — skeleton while loading or chart not yet rendered */}
      {graphLoading ? (
        <Card className="gap-0 py-0 p-2">
          <Skeleton className="h-[400px] w-full rounded" />
        </Card>
      ) : data.length > 0 && (
        <Card className="gap-0 py-0 p-2">
          {displayToolbar}
          <ResultsChart
            points={data}
            sessions={sessions}
            variance={variance}
            unit={unit}
            lines={lines}
            checkpoints={showCheckpoints ? checkpoints : []}
          />
        </Card>
      )}

      {/* Stats Panel */}
      {graphLoading ? (
        <Card className="gap-0 py-0 overflow-hidden">
          <div className="px-4 py-2"><Skeleton className="h-4 w-64" /></div>
          <div className="grid grid-cols-2 border-t border-border">
            <div className="px-4 py-3 space-y-2"><Skeleton className="h-6 w-24" /><Skeleton className="h-5 w-20" /><Skeleton className="h-3 w-16" /></div>
            <div className="px-4 py-3 space-y-2 border-l border-border"><Skeleton className="h-6 w-24" /><Skeleton className="h-5 w-20" /><Skeleton className="h-3 w-16" /></div>
          </div>
          <div className="px-4 py-2 border-t border-border"><Skeleton className="h-4 w-full" /></div>
        </Card>
      ) : (
        <Card className="gap-0 py-0 overflow-hidden">
          {/* Context strip */}
          <div className="px-4 py-2 text-xs text-text-muted">
            {n.toLocaleString()} hands · {handsPerHour > 0 ? `${handsPerHour}/hr · ` : ''}{totalHrs > 0 ? `${fixed(totalHrs, 0)}h played · ` : ''}{sessions.length} sessions
          </div>

          {/* Hero pair: Actual vs EV */}
          <div className="grid grid-cols-2 border-t border-border">
            {/* Actual */}
            <div className="px-4 py-3 grid grid-cols-2 gap-x-4">
              <div className={`text-xl font-bold ${moneyClass(wonUSD)}`}>{usd(wonUSD)}</div>
              <div className={`text-xl font-bold ${moneyClass(rateBB)}`}>{fixed(rateBB, 2)}</div>
              <div className={`text-sm ${moneyClass(wonBB, 1)}`}>{bbUnits(wonBB)}</div>
              <div className="text-sm text-text-muted">bb/100</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wide">Won</div>
              <div className="text-[10px] text-text-muted uppercase tracking-wide">Rate</div>
            </div>
            {/* EV */}
            <div className="px-4 py-3 border-l border-border grid grid-cols-2 gap-x-4">
              {hasEVData ? (
                <>
                  <div className={`text-xl font-bold ${moneyClass(evUSD)}`}>{usd(evUSD)}</div>
                  <div className={`text-xl font-bold ${moneyClass(evRateBB)}`}>{fixed(evRateBB, 2)}</div>
                  <div className={`text-sm ${moneyClass(evBB, 1)}`}>{bbUnits(evBB)}</div>
                  <div className="text-sm text-text-muted">EV bb/100</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
                </>
              ) : (
                <>
                  <div className="text-xl font-bold text-text-muted">—</div>
                  <div className="text-xl font-bold text-text-muted">—</div>
                  <div className="text-sm text-text-muted">&nbsp;</div>
                  <div className="text-sm text-text-muted">&nbsp;</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                  <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
                </>
              )}
            </div>
          </div>

          {/* Footer: secondary stats */}
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-x-6 px-4 py-2.5 border-t border-border">
            {/* $/hr */}
            <div>
              <div className={`text-sm font-bold ${totalHrs > 0 ? moneyClass(usdPerHour) : 'text-text-muted'}`}>
                {totalHrs > 0 ? `${usd(usdPerHour)}/hr` : '—'}
              </div>
              <div className="text-xs text-text-muted">$/hr {totalHrs > 0 ? <span className={`${moneyClass(bbPerHour, 1)}`}>{fixed(bbPerHour, 1)} BB</span> : ''}</div>
            </div>
            {/* SD Won */}
            <div>
              <div className={`text-sm font-bold ${moneyClass(sdUSD)}`}>{usd(sdUSD)}</div>
              <div className="text-xs text-text-muted">Showdown <span className={`${moneyClass(sdRateBB, 1)}`}>{fixed(sdRateBB, 1)}/100</span></div>
            </div>
            {/* NSD Won */}
            <div>
              <div className={`text-sm font-bold ${moneyClass(nsdUSD)}`}>{usd(nsdUSD)}</div>
              <div className="text-xs text-text-muted">Non-SD <span className={`${moneyClass(nsdRateBB, 1)}`}>{fixed(nsdRateBB, 1)}/100</span></div>
            </div>
            {/* Rake */}
            <div>
              <div className="text-sm font-bold text-text-muted">{usd(rakeUSD)}</div>
              <div className="text-xs text-text-muted">Rake {fixed(rakePerBB, 1)}/100{jackpotBB > 0 ? ` · BBJ ${usd(jackpotUSD)}` : ''}</div>
            </div>
            {/* 95% CI */}
            <div>
              {variance ? (
                <>
                  <div className={`text-sm font-bold ${variance.ci_lower_bb100 > 0 ? 'text-green' : variance.ci_upper_bb100 < 0 ? 'text-red' : 'text-text'}`}>
                    {fixed(variance.ci_lower_bb100, 2)} to {fixed(variance.ci_upper_bb100, 2)}
                  </div>
                  <div className="text-xs text-text-muted">95% CI bb/100 σ {fixed(variance.sd_bb100, 1)}</div>
                </>
              ) : (
                <div className="text-sm text-text-muted">—</div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Breakdown Tables — independent loading */}
      {breakdownLoading ? (
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-3 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Breakdown by Stakes */}
          {breakdown && breakdown.by_stakes.length > 0 && (
            <BreakdownTable
              title="Breakdown by Stakes"
              columns={stakeColumns}
              rows={breakdown.by_stakes}
              rowKey={(r: StakeBreakdown) => `${r.game_mode}:${r.stakes}`}
            />
          )}

          {/* Breakdown by Position */}
          {breakdown && breakdown.by_position.length > 0 && (
            <BreakdownTable
              title="Breakdown by Position"
              columns={positionColumns}
              rows={breakdown.by_position}
              rowKey={(r: PositionBreakdown) => r.position}
            />
          )}

          {/* Breakdown by Month */}
          {breakdown && breakdown.by_month.length > 0 && (
            <BreakdownTable
              title="Breakdown by Month"
              columns={monthColumns}
              rows={breakdown.by_month}
              rowKey={(r: MonthBreakdown) => r.month}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Breakdown Table ──────────────────────────────────────────────────

interface Column<T> {
  key: string;
  label: string;
  align?: 'left' | 'right';
  width?: string;
  render: (row: T) => React.ReactNode;
}

function BreakdownTable<T>({
  title,
  columns,
  rows,
  rowKey,
}: {
  title: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}) {
  return (
    <Card className="overflow-hidden gap-0 py-0">
      <CardHeader className="px-3 py-1.5">
        <h2 className="text-xs font-semibold text-text">{title}</h2>
      </CardHeader>
      <div className="overflow-x-auto">
        <Table style={{ tableLayout: 'fixed', width: '100%' }}>
          <colgroup>
            {columns.map(col => (
              <col key={col.key} style={col.width ? { width: col.width } : undefined} />
            ))}
          </colgroup>
          <TableHeader>
            <TableRow>
              {columns.map(col => (
                <TableHead
                  key={col.key}
                  className={`px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                >
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(row => (
              <TableRow key={rowKey(row)} className="hover:bg-surface-hover transition-colors">
                {columns.map(col => (
                  <TableCell
                    key={col.key}
                    className={`px-3 py-1.5 ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                  >
                    {col.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}

function renderRake(r: { rake_usd: number }) {
  return <span className="text-red">${fixed(r.rake_usd, 2)}</span>;
}

const COL_WIDTHS = { label: '22%', hands: '16%', won: '18%', bb100: '16%', ev_bb100: '16%', rake: '12%' };

const stakeColumns: Column<StakeBreakdown>[] = [
  { key: 'stakes', label: 'Stakes', width: COL_WIDTHS.label, render: (r) => {
    return <span className="text-text">{formatStakes(r.stakes)}{r.game_mode ? <span className="text-text-muted ml-1.5 text-xs">{r.game_mode}</span> : ''}</span>;
  }},
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={moneyClass(v)}>{usd(v)}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={moneyClass(r.bb_per_100)}>{fixed(r.bb_per_100, 2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={moneyClass(r.ev_bb_per_100)}>{fixed(r.ev_bb_per_100, 2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];

const positionColumns: Column<PositionBreakdown>[] = [
  { key: 'position', label: 'Position', width: COL_WIDTHS.label, render: (r) => <span className="text-text font-semibold">{r.position}</span> },
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={moneyClass(v)}>{usd(v)}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={moneyClass(r.bb_per_100)}>{fixed(r.bb_per_100, 2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={moneyClass(r.ev_bb_per_100)}>{fixed(r.ev_bb_per_100, 2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];

const monthColumns: Column<MonthBreakdown>[] = [
  { key: 'month', label: 'Month', width: COL_WIDTHS.label, render: (r) => <span className="text-text">{formatMonth(r.month)}</span> },
  { key: 'hands', label: 'Hands', align: 'right', width: COL_WIDTHS.hands, render: (r) => <span className="text-text">{r.hands.toLocaleString()}</span> },
  {
    key: 'won',
    label: 'Won',
    align: 'right',
    width: COL_WIDTHS.won,
    render: (r) => {
      const v = r.won_usd;
      return <span className={moneyClass(v)}>{usd(v)}</span>;
    },
  },
  {
    key: 'bb100',
    label: 'bb/100',
    align: 'right',
    width: COL_WIDTHS.bb100,
    render: (r) => <span className={moneyClass(r.bb_per_100)}>{fixed(r.bb_per_100, 2)}</span>,
  },
  {
    key: 'ev_bb100',
    label: 'EV bb/100',
    align: 'right',
    width: COL_WIDTHS.ev_bb100,
    render: (r) => <span className={moneyClass(r.ev_bb_per_100)}>{fixed(r.ev_bb_per_100, 2)}</span>,
  },
  {
    key: 'rake',
    label: 'Rake',
    align: 'right',
    width: COL_WIDTHS.rake,
    render: (r) => renderRake(r),
  },
];
