import { useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { RefreshCw, Settings, UserRound, FileJson } from 'lucide-react';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import GeneralGrid from '@/components/general/GeneralGrid';
import GeneralHandList from '@/components/general/GeneralHandList';
import StatPopup from '@/components/general/StatPopup';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { createCheckpoint } from '@/lib/api';
import { getGeneral, generalQueryKey } from '@/lib/api-general';
import type { GeneralCell, GeneralResponse, HandsSelection } from '@/lib/api-general';
import { getPresetDates } from '@/lib/date-presets';
import type { DatePreset } from '@/lib/date-presets';
import { formatHands } from '@/lib/h2n-format';
import { GENERAL_CELLS, H2N_THEME, SUMMARY_CELL_IDS } from '@/lib/h2n-layout';
import { POPUP_THEME } from '@/lib/general-notation';

/** Hands and bb/100 also travel as top-level fields; make sure the grid sees them as cells. */
function cellsWithSummary(res: GeneralResponse): Record<string, GeneralCell> {
  const cells: Record<string, GeneralCell> = { ...res.cells };
  cells[SUMMARY_CELL_IDS.hands] ??= { value: res.hands, sample: null };
  cells[SUMMARY_CELL_IDS.bb100] ??= { value: res.bb100, sample: res.hands };
  return cells;
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Page ────────────────────────────────────────────────────────────

export default function GeneralPage() {
  const { activeWorkspace, activeWorkspaceId, checkpoints, refetchCheckpoints } = useWorkspace();
  const { data: filterOpts } = useFilterOptions();

  const [stakes, setStakes] = useState('');
  const [gameMode, setGameMode] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [activePreset, setActivePreset] = useState<DatePreset>('all');
  const [checkpointId, setCheckpointId] = useState<string | null>(null);
  const [tab, setTab] = useState('general');

  /** Clicked cell on the General page (page 0); an action cell opens the stat popup (page 1). */
  const [selectedCellId, setSelectedCellIdRaw] = useState<string | null>(null);
  /** Category / board / bet size picked in the popup; opens the hands list (page 2). */
  const [handsSelection, setHandsSelection] = useState<HandsSelection | null>(null);

  // Selecting something on page N replaces every page to its right.
  const setSelectedCellId = (id: string | null) => {
    setSelectedCellIdRaw(id);
    setHandsSelection(null);
  };

  const params = useMemo(
    () => ({
      stakes: stakes || undefined,
      game_mode: gameMode || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      workspace_id: activeWorkspaceId,
    }),
    [stakes, gameMode, dateFrom, dateTo, activeWorkspaceId],
  );

  // Keep the previous numbers on screen while a filter change refetches, so
  // the grid does not flash back to "Loading…".
  const { data, isPending, isError, error, refetch, isFetching, isPlaceholderData } = useQuery({
    queryKey: generalQueryKey(params),
    queryFn: () => getGeneral(params),
    placeholderData: keepPreviousData,
  });

  const cells = useMemo(() => (data ? cellsWithSummary(data) : {}), [data]);

  const handlePreset = (preset: DatePreset) => {
    setActivePreset(preset);
    const dates = getPresetDates(preset);
    setDateFrom(dates.date_from ?? '');
    setDateTo(dates.date_to ?? '');
    setCheckpointId(null);
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

  const clearFilters = () => {
    setStakes('');
    setGameMode('');
    handlePreset('all');
  };

  const hasFilters = !!(stakes || gameMode || dateFrom || dateTo);
  const playerName = data?.player || activeWorkspace?.hero_username || 'No hero yet';
  const siteName = data?.site || activeWorkspace?.hero_site || '';
  const selectedMeta = selectedCellId ? GENERAL_CELLS[selectedCellId] : undefined;
  // Expression stats only highlight; action stats open the detail page. The
  // sample-data grid has no backing hands, so it never opens the (real) popup.
  const popupOpen = selectedMeta?.kind === 'action' && !data?.mock;

  return (
    // contain:inline-size keeps the wide pane row from stretching the app shell; the row scrolls instead.
    <div
      className="-m-4 flex h-[calc(100svh-2.5rem)] min-h-0 flex-col [contain:inline-size]"
      style={{ background: H2N_THEME.outerBg }}
    >
      <div className="p-2">
        <FilterBar
          stakes={stakes}
          onStakesChange={setStakes}
          gameMode={gameMode}
          onGameModeChange={setGameMode}
          dateFrom={dateFrom}
          onDateFromChange={(v) => {
            setDateFrom(v);
            setActivePreset('all');
            setCheckpointId(null);
          }}
          dateTo={dateTo}
          onDateToChange={(v) => {
            setDateTo(v);
            setActivePreset('all');
          }}
          activePreset={activePreset}
          onPresetChange={handlePreset}
          filterOptions={filterOpts ?? null}
          checkpointId={checkpointId}
          onCheckpointChange={handleCheckpointChange}
          checkpoints={checkpoints}
          onCreateCheckpoint={async (cp) => {
            await createCheckpoint(activeWorkspaceId, cp);
            await refetchCheckpoints();
          }}
        />
      </div>

      <div className="flex min-h-0 flex-1 overflow-x-auto">
        {/* Page 0: General */}
        <section
          aria-label="General statistics"
          className="flex h-full min-w-[670px] shrink-0 flex-col"
          style={{ background: H2N_THEME.pageBg, fontFamily: H2N_THEME.fontFamily }}
        >
          <header className="flex items-center gap-2 px-4 py-2 text-sm">
            <div className="flex items-center gap-2 px-3 py-2 text-[#D3D3D3]" title="Selected player">
              <UserRound className="size-4 text-white/60" aria-hidden />
              <span className="size-1.5 rounded-full bg-[#F57373]" aria-hidden />
              <span>
                {playerName}
                {siteName && (
                  <>
                    ,<span className="ml-1 text-white/50">{siteName}</span>
                  </>
                )}
              </span>
            </div>
            {data?.mock && (
              <Badge variant="outline" className="border-white/15 text-white/50" title="The stats endpoint is not available yet; showing sample numbers">
                Sample data
              </Badge>
            )}
            <span className="ml-auto flex items-center gap-2 text-white/50">
              {isFetching && !isPending && (
                <RefreshCw className="size-3 animate-spin" aria-label="Updating" role="status" />
              )}
              {data ? `${formatHands(data.hands)} hands` : ''}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="size-8 text-white/60" aria-label="General page menu">
                  <Settings />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => void refetch()} disabled={isFetching}>
                  <RefreshCw /> Refresh
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled={!data} onSelect={() => data && downloadJson(data, 'ohm-general.json')}>
                  <FileJson /> Export As Json…
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>

          <Tabs value={tab} onValueChange={setTab} className="min-h-0 flex-1 gap-0">
            <TabsList variant="line" className="h-auto gap-4 px-4 pb-1">
              <TabsTrigger
                value="general"
                className="flex-none rounded-none px-0 text-sm font-normal tracking-normal data-[state=active]:text-[#D5D5D5]"
              >
                GENERAL
              </TabsTrigger>
              <TabsTrigger
                value="notes"
                className="flex-none rounded-none px-0 text-sm font-normal data-[state=active]:text-[#D5D5D5]"
              >
                Notes
              </TabsTrigger>
            </TabsList>
            <div className="mx-0 h-px bg-white/10" />

            <TabsContent value="general" className="min-h-0">
              <ScrollArea className="h-full">
                <div className="pt-4 pb-4">
                  {isPending ? (
                    <p className="px-4 text-sm text-white/50">Loading…</p>
                  ) : isError && !data ? (
                    <div role="alert" className="flex flex-col items-start gap-3 px-4">
                      <p className="text-sm text-white/70">Could not load statistics.</p>
                      {error instanceof Error && error.message && (
                        <p className="text-sm text-white/50">{error.message}</p>
                      )}
                      <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
                        <RefreshCw className={isFetching ? 'animate-spin' : undefined} /> Retry
                      </Button>
                    </div>
                  ) : !data ? null : data.hands === 0 && !data.mock ? (
                    <EmptyState
                      variant={hasFilters ? 'no-match' : 'no-data'}
                      onClearFilters={hasFilters ? clearFilters : undefined}
                    />
                  ) : (
                    <div
                      className="transition-opacity"
                      style={{ opacity: isPlaceholderData ? 0.6 : 1 }}
                      aria-busy={isPlaceholderData || undefined}
                    >
                      {isError && (
                        <div role="alert" className="mb-3 flex items-center gap-3 px-4 text-sm text-white/60">
                          <span>
                            Could not refresh statistics
                            {error instanceof Error && error.message ? `: ${error.message}` : '.'}
                          </span>
                          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
                            Retry
                          </Button>
                        </div>
                      )}
                      <GeneralGrid
                        cells={cells}
                        playerName={playerName}
                        selectedCellId={selectedCellId}
                        onSelectCell={setSelectedCellId}
                      />
                    </div>
                  )}
                </div>
                <ScrollBar orientation="horizontal" />
              </ScrollArea>
            </TabsContent>
            <TabsContent value="notes" className="px-4 pt-4">
              <p className="text-sm text-white/50">Player notes are not supported yet.</p>
            </TabsContent>
          </Tabs>
        </section>

        {/* Page 1: stat detail */}
        {popupOpen && selectedMeta && selectedCellId ? (
          <StatPopup
            key={selectedCellId}
            cellId={selectedCellId}
            meta={selectedMeta}
            params={params}
            selection={handsSelection}
            onSelect={setHandsSelection}
            onClose={() => setSelectedCellId(null)}
          />
        ) : null}

        {/* Page 2: hands of the popup selection */}
        {popupOpen && selectedCellId && handsSelection ? (
          <section
            aria-label={`Hands: ${handsSelection.label}`}
            className="flex h-full min-w-[420px] flex-1 flex-col border-l border-white/5 pt-1"
            style={{ background: POPUP_THEME.headerBg }}
          >
            <GeneralHandList
              key={`${selectedCellId}|${handsSelection.bucket ?? ''}|${handsSelection.board ?? ''}|${handsSelection.size ?? ''}`}
              cellId={selectedCellId}
              params={params}
              filter={{ bucket: handsSelection.bucket, board: handsSelection.board, size: handsSelection.size }}
              title={handsSelection.label}
              onClose={() => setHandsSelection(null)}
            />
          </section>
        ) : null}
      </div>
    </div>
  );
}
