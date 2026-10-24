import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getHands } from '@/lib/api';
import { chainParam } from '@/lib/reports/api';
import type { Step } from '@/lib/reports/types';
import type { HandListParams, HandSummary } from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { queryKeys } from '@/lib/query-keys';
import { queryClient } from '@/lib/query-client';
import { cn, formatStakes, formatRelativeDate } from '@/lib/utils';
import { formatLocalDate } from '@/lib/date';
import EmptyState from '@/components/EmptyState';
import HandFilters from '@/components/hands/HandFilters';
import type { FilterState } from '@/components/hands/HandFilters';
import { QUICK_FILTERS_MAP } from '@/components/hands/HandFilters';
import { CardBoxPair, CardBoxRow, CardBox } from '@/components/hands/CardDisplay';
import { RitBadge, CashoutBadge } from '@/components/hands/HandTypeBadge';
import Actions, { actionTitle, formatBb } from '@/components/hands/Actions';
import TagChip from '@/components/marked/TagChip';
import MarkMenuItems from '@/components/marked/MarkMenuItems';
import TagPickerPopover from '@/components/marked/TagPickerPopover';
import { markedListParams } from '@/lib/marked/logic';
import Pagination from '@/components/hands/Pagination';
import HandDrawer from '@/components/hands/HandDrawer';
import { DataGrid, createDataGridColumns, type DataGridHandle, type GridSorting } from '@/components/ui/data-grid';
import { fixed } from '@/lib/format';

function getDateRange(preset: string, dateFrom: string, dateTo: string): { from?: string; to?: string } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  switch (preset) {
    case 'today':
      return { from: formatLocalDate(today) };
    case 'week': {
      const d = new Date(today);
      d.setDate(d.getDate() - d.getDay());
      return { from: formatLocalDate(d) };
    }
    case 'month':
      return { from: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01` };
    case 'custom':
      return { from: dateFrom || undefined, to: dateTo || undefined };
    default:
      return {};
  }
}

/** Signed dollars with the trailing "$" the hands list has always used; an em dash for zero. */
function dollars(v: number): string {
  return Math.abs(v) < 0.005 ? '\u2014' : `${v < 0 ? '-' : ''}${fixed(Math.abs(v), 2)}$`;
}

const handId = (h: HandSummary) => h.id;
const NO_HANDS: HandSummary[] = [];
const col = createDataGridColumns<HandSummary>();

function StreetActions({ items, precision, trimFolds }: { items: HandSummary['preflop_actions']; precision: 0 | 1; trimFolds?: boolean }) {
  return (
    <div className="truncate pb-1" title={actionTitle(items, precision, trimFolds)}>
      <Actions items={items} trimFolds={trimFolds} precision={precision} />
    </div>
  );
}

/** Hand list columns. Sortable ones (stakes, won_usd, played_at) use the API's sort keys as ids; display columns never sort. */
function handColumns(precision: 0 | 1, openTag: (id: number) => void) {
  const potCell = (has: (h: HandSummary) => boolean, pot: (h: HandSummary) => number) =>
    function PotCell({ row }: { row: { original: HandSummary } }) {
      return has(row.original) ? formatBb(pot(row.original), precision) : '';
    };
  const potMeta = (street: string) => ({ align: 'center' as const, title: `${street} pot (bb)`, className: 'px-1 text-sm text-muted-foreground' });
  return col.columns([
    col.accessor('tags', {
      header: 'Tags',
      size: 120,
      enableSorting: false,
      meta: { title: 'Marked hand tags' },
      cell: (i) => (
        <div className="flex flex-col items-start gap-0.5 py-0.5">
          {i.getValue().map((t) => (
            <TagChip key={t.id} tag={t} onClick={(e) => { e.stopPropagation(); openTag(t.id); }} />
          ))}
        </div>
      ),
    }),
    col.display({
      id: 'preflop',
      header: 'Preflop',
      size: 100,
      meta: { title: 'Hole cards' },
      cell: ({ row: { original: h } }) => (
        <div className="flex flex-col gap-0.5">
          <CardBoxPair card1={h.card1} card2={h.card2} />
          {(h.rit_boards > 1 || h.is_cashout) && (
            <div className="flex items-center gap-0.5">
              {h.rit_boards > 1 && <RitBadge boards={h.rit_boards} />}
              {h.is_cashout && <CashoutBadge />}
            </div>
          )}
        </div>
      ),
    }),
    col.display({
      id: 'preflop_actions',
      header: 'Actions',
      size: 150,
      meta: { title: 'Preflop actions' },
      cell: ({ row }) => <StreetActions items={row.original.preflop_actions} precision={precision} trimFolds />,
    }),
    col.display({
      id: 'flop',
      header: 'Flop',
      size: 128,
      meta: { title: 'Flop cards', className: 'pl-4' },
      cell: ({ row }) => <CardBoxRow cards={row.original.flop_cards} />,
    }),
    col.display({ id: 'flop_pot', header: 'Pot', size: 52, meta: potMeta('Flop'), cell: potCell((h) => h.flop_cards.length > 0, (h) => h.flop_pot) }),
    col.display({
      id: 'flop_actions',
      header: 'Actions',
      size: 120,
      meta: { title: 'Flop actions' },
      cell: ({ row }) => <StreetActions items={row.original.flop_actions} precision={precision} />,
    }),
    col.display({
      id: 'turn',
      header: 'Turn',
      size: 60,
      meta: { title: 'Turn card', className: 'pl-4' },
      cell: ({ row }) => (row.original.turn_card ? <CardBox card={row.original.turn_card} /> : null),
    }),
    col.display({ id: 'turn_pot', header: 'Pot', size: 52, meta: potMeta('Turn'), cell: potCell((h) => !!h.turn_card, (h) => h.turn_pot) }),
    col.display({
      id: 'turn_actions',
      header: 'Actions',
      size: 120,
      meta: { title: 'Turn actions' },
      cell: ({ row }) => <StreetActions items={row.original.turn_actions} precision={precision} />,
    }),
    col.display({
      id: 'river',
      header: 'River',
      size: 60,
      meta: { title: 'River card', className: 'pl-4' },
      cell: ({ row }) => (row.original.river_card ? <CardBox card={row.original.river_card} /> : null),
    }),
    col.display({ id: 'river_pot', header: 'Pot', size: 52, meta: potMeta('River'), cell: potCell((h) => !!h.river_card, (h) => h.river_pot) }),
    col.display({
      id: 'river_actions',
      header: 'Actions',
      size: 120,
      meta: { title: 'River actions' },
      cell: ({ row }) => <StreetActions items={row.original.river_actions} precision={precision} />,
    }),
    col.accessor('stakes', {
      header: 'Stakes',
      size: 80,
      meta: { sortDescFirst: true, className: 'pl-4 text-sm text-muted-foreground' },
      cell: (i) => formatStakes(i.getValue()),
    }),
    col.accessor((h) => h.won_bb * h.bb_amount, {
      id: 'won_usd',
      header: 'Won',
      size: 84,
      meta: { numeric: true, tone: 'money', className: 'text-sm font-semibold' },
      cell: (i) => dollars(i.getValue()),
    }),
    col.accessor((h) => (h.all_in_ev_bb - h.won_bb) * h.bb_amount, {
      id: 'ev_diff',
      header: 'EV Diff.',
      size: 84,
      enableSorting: false,
      meta: { numeric: true, tone: 'money', title: 'All-in EV minus won ($)', className: 'text-sm' },
      cell: (i) => dollars(i.getValue()),
    }),
    col.accessor('played_at', {
      header: 'Date',
      size: 80,
      meta: { align: 'right', sortDescFirst: true, className: 'text-sm text-muted-foreground' },
      cell: (i) => formatRelativeDate(i.getValue()),
    }),
  ]);
}

/** Columns the narrow landing showcase hides by default (low-value ones, so the rest fits ~1100px). */
export const COMPACT_HIDDEN_COLUMNS: readonly string[] = ['flop_pot', 'turn_pot', 'river_pot', 'ev_diff', 'stakes', 'river_actions'];

const DEFAULT_GRID_MAX_HEIGHT = 'max(18rem, calc(100dvh - 17rem))';

export interface HandExplorerProps {
  /** Params always applied to API call, not user-editable */
  fixedParams?: Partial<HandListParams>;
  /** Pre-populate filter state */
  initialFilters?: Partial<FilterState>;
  /** Default items per page (50 for HandsPage, 25 for embedded) */
  defaultPerPage?: number;
  /** Optional header above the filters */
  header?: React.ReactNode;
  /** CSS class for root container */
  className?: string;
  /** Message for the empty state when the list is empty and the user has set no filters */
  emptyMessage?: string;
  /** Height cap of the hands grid's scroll area (its header stays put while it scrolls) */
  gridMaxHeight?: number | string;
  /** Column ids hidden until the user stores their own column choice (stored prefs win) */
  defaultHiddenColumns?: readonly string[];
  /** Reports filter chain, applied on top of the user filters; a new chain returns to page 1 */
  chain?: Step[];
  /** Hide the built-in filter bar (the page provides its own filters). */
  hideFilters?: boolean;
  /** Page-owned filter row, shown where the built-in filter bar would be. */
  filterRow?: React.ReactNode;
}

export default function HandExplorer({
  fixedParams,
  initialFilters,
  defaultPerPage = 50,
  header,
  className,
  emptyMessage,
  gridMaxHeight = DEFAULT_GRID_MAX_HEIGHT,
  defaultHiddenColumns,
  chain,
  hideFilters = false,
  filterRow,
}: HandExplorerProps) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(defaultPerPage);
  const [sort, setSort] = useState<string>('played_at');
  const [order, setOrder] = useState<string>('desc');

  const [filters, setFilters] = useState<FilterState>({
    position: initialFilters?.position ?? [],
    stakes: initialFilters?.stakes ?? [],
    result: initialFilters?.result ?? '',
    marked: initialFilters?.marked ?? '',
    tagIds: initialFilters?.tagIds ?? [],
    date: initialFilters?.date ?? '',
    dateFrom: initialFilters?.dateFrom ?? '',
    dateTo: initialFilters?.dateTo ?? '',
    search: initialFilters?.search ?? '',
    statFlags: initialFilters?.statFlags ?? [],
    quickFilters: initialFilters?.quickFilters ?? [],
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [bbPrecision, setBbPrecision] = useState<0 | 1>(1);

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(filters.search);
      setPage(1);
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [filters.search]);

  // Shared filter options (for distinct stakes)
  const { data: filterOptsData } = useFilterOptions();
  const distinctStakes = filterOptsData?.stakes ?? [];

  // Build query params — merge user filters + fixedParams
  const dateRange = getDateRange(filters.date, filters.dateFrom, filters.dateTo);

  // Expand quick filters into stat_flag values
  const allStatFlags = [...filters.statFlags];
  for (const qfKey of filters.quickFilters) {
    const def = QUICK_FILTERS_MAP[qfKey];
    if (def) {
      for (const flag of def.flags) {
        if (!allStatFlags.includes(flag)) allStatFlags.push(flag);
      }
    }
  }

  const userParams: HandListParams = {
    page,
    per_page: perPage,
    sort,
    order,
    position: filters.position.length > 0 ? filters.position.join(',') : undefined,
    stakes: filters.stakes.length > 0 ? filters.stakes.join(',') : undefined,
    result: filters.result || undefined,
    ...markedListParams({ mode: filters.marked, tagIds: filters.tagIds }),
    date_from: dateRange.from,
    date_to: dateRange.to,
    search: debouncedSearch || undefined,
    stat_flag: allStatFlags.length > 0 ? allStatFlags : undefined,
    // An explicit empty chain is sent as well (backend applies the hand validity rule); no chain = unchanged
    chain,
  };

  // Merge fixedParams — they override user params for the same key
  const handsQueryParams: HandListParams = { ...userParams, ...fixedParams };
  // For position, merge: if fixedParams has position AND user selected positions, use fixed
  // (fixedParams takes precedence since it's applied via spread after userParams)

  // Hands list query
  // Previous page stays on screen (with a progress line) while the next sort/page/filter loads
  const { data, isPending: loading, isPlaceholderData, isError, error } = useQuery({
    queryKey: queryKeys.hands.list(handsQueryParams),
    queryFn: () => getHands(handsQueryParams),
    placeholderData: keepPreviousData,
  });

  const sorting = useMemo<GridSorting>(() => [{ id: sort, desc: order === 'desc' }], [sort, order]);
  const handleSortingChange = useCallback((next: GridSorting) => {
    const head = next[0];
    if (!head) return;
    setSort(head.id);
    setOrder(head.desc ? 'desc' : 'asc');
    setPage(1);
  }, []);

  // A new chain is a new result set: back to page 1 (adjusting state during render, keyed on the chain)
  const chainKey = chain ? chainParam(chain) : '';
  const [seenChainKey, setSeenChainKey] = useState(chainKey);
  if (seenChainKey !== chainKey) {
    setSeenChainKey(chainKey);
    setPage(1);
  }

  const handleFilterChange = (f: FilterState) => { setFilters(f); setPage(1); };

  const navigate = useNavigate();
  const columns = useMemo(() => handColumns(bbPrecision, (id) => navigate(`/marked?tag=${id}`)), [bbPrecision, navigate]);
  // Right-click menu + tag picker (anchored where the menu was opened)
  const [picker, setPicker] = useState<{ handId: string; playerId?: number; x: number; y: number } | null>(null);
  const lastPointer = useRef({ x: 0, y: 0 });
  // The row menu's FocusScope would hand focus back to the row on close, and the (non-modal) picker dismisses
  // on focus-outside; while the picker is opening, keep focus where the picker puts it.
  const pickerOpening = useRef(false);
  const fixedPlayerId = fixedParams?.player_id;
  const renderRowMenu = useCallback(
    (h: HandSummary) => {
      const playerId = h.player_id ?? fixedPlayerId;
      return (
        <MarkMenuItems
          handId={h.id}
          playerId={playerId}
          marked={h.marked}
          onPickTags={(id) => {
            pickerOpening.current = true;
            setPicker({ handId: id, playerId, ...lastPointer.current });
          }}
        />
      );
    },
    [setPicker, fixedPlayerId],
  );
  const handleRowMenuCloseAutoFocus = useCallback((e: Event) => {
    if (pickerOpening.current) {
      pickerOpening.current = false;
      e.preventDefault();
    }
  }, []);
  const selectedRowIds = useMemo(() => (selectedId ? [selectedId] : []), [selectedId]);
  const gridRef = useRef<DataGridHandle>(null);
  const openDrawer = useCallback((id: string) => { setSelectedId(id); setDrawerOpen(true); }, []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  // Radix would restore focus to the row that opened the drawer; the user may have paged through other hands since,
  // so take over and focus (revealing it if off-screen) the last viewed hand's row instead
  const lastViewedId = useRef<string | null>(null);
  useEffect(() => { if (selectedId) lastViewedId.current = selectedId; }, [selectedId]);
  const handleCloseAutoFocus = useCallback((e: Event) => {
    e.preventDefault();
    const id = lastViewedId.current;
    if (id) gridRef.current?.focusRow(id);
  }, []);
  const handleSelectionChange = useCallback((ids: string[]) => setSelectedId(ids[0] ?? null), []);
  const handleRowClick = useCallback((h: HandSummary) => openDrawer(h.id), [openDrawer]);

  // A sticky header lets you re-sort / re-filter while scrolled down: start the new result at the top
  const queryKeyJson = JSON.stringify(handsQueryParams);
  useEffect(() => { gridRef.current?.scrollToTop(); }, [queryKeyJson]);

  const hands = data?.hands ?? NO_HANDS;
  const selectedIndex = selectedId ? hands.findIndex((h) => h.id === selectedId) : -1;

  const handlePrev = () => {
    if (selectedIndex > 0) setSelectedId(hands[selectedIndex - 1].id);
  };
  const handleNext = () => {
    if (selectedIndex >= 0 && selectedIndex < hands.length - 1) setSelectedId(hands[selectedIndex + 1].id);
  };

  const hasUserFilters = filters.position.length > 0 || filters.stakes.length > 0 ||
    filters.result !== '' || filters.marked !== '' || filters.tagIds.length > 0 || filters.date !== '' || debouncedSearch !== '' ||
    filters.statFlags.length > 0 || filters.quickFilters.length > 0;
  const hasFixedFilters = !!(fixedParams?.stat_key || fixedParams?.stat_flag?.length || fixedParams?.position || fixedParams?.stakes);
  const hasFilters = hasUserFilters || hasFixedFilters || !!emptyMessage;

  // Compute locked stat flags from fixedParams
  const lockedStatFlags: string[] = [];
  if (fixedParams?.stat_key) lockedStatFlags.push(fixedParams.stat_key);
  if (fixedParams?.stat_flag) {
    for (const f of fixedParams.stat_flag) {
      if (!lockedStatFlags.includes(f)) lockedStatFlags.push(f);
    }
  }

  return (
    <div className={cn('flex w-full flex-col', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          {header}
        </div>
        {data && (
          <span className="text-[15px] text-text-muted">
            {data.total.toLocaleString()} hands
          </span>
        )}
      </div>

      <div className="mb-2 flex items-center justify-end gap-2">
          <button
            onClick={() => setShowLegend(!showLegend)}
            className="text-[12px] text-text-muted hover:text-text w-[18px] h-[18px] rounded-full border border-border flex items-center justify-center"
            title="Action legend"
          >
            ?
          </button>
          <button
            onClick={() => setBbPrecision(p => p === 0 ? 1 : 0)}
            className={`text-[11px] px-1.5 h-[18px] rounded border flex items-center justify-center ${
              bbPrecision === 1 ? 'border-primary text-primary' : 'border-border text-text-muted hover:text-text'
            }`}
            title={`BB precision: ${bbPrecision === 0 ? 'rounded' : '1 decimal'}. Click to toggle.`}
          >
            .0
          </button>
      </div>

      {/* Legend tooltip */}
      {showLegend && (
        <div className="mb-2 px-3 py-2 bg-surface rounded border border-border text-[14px] flex items-center gap-5">
          <span><span className="text-yellow font-bold">R</span> Raise</span>
          <span><span className="text-blue font-bold">B</span> Bet</span>
          <span><span className="font-bold text-text">C</span> Call</span>
          <span className="text-text-muted">X Check</span>
          <span className="text-text-muted">F Fold</span>
          <span className="text-text-muted/40">|</span>
          <span className="text-text-muted"><span className="border-b-2 border-dashed border-text-muted pb-[1px]">dashed underline</span> = hero action</span>
        </div>
      )}

      {filterRow}

      {/* Filters (hidden where the page owns filtering, e.g. a Reports page's chips) */}
      {!hideFilters && <div className="mb-3">
        <HandFilters
          filters={filters}
          onChange={handleFilterChange}
          distinctStakes={distinctStakes}
          lockedStatFlags={lockedStatFlags.length > 0 ? lockedStatFlags : undefined}
        />
      </div>}

      {/* Table */}
      {isError ? (
        <p className="text-money-neg text-sm py-8 text-center">
          Failed to load hands{error instanceof Error ? `: ${error.message}` : ''}
        </p>
      ) : data && data.total === 0 ? (
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          message={!hasUserFilters ? emptyMessage : undefined}
          onClearFilters={hasUserFilters ? () => handleFilterChange({ position: [], stakes: [], result: '', marked: '', tagIds: [], date: '', dateFrom: '', dateTo: '', search: '', statFlags: [], quickFilters: [] }) : undefined}
        />
      ) : (
        <>
          <div onContextMenuCapture={(e) => { lastPointer.current = { x: e.clientX, y: e.clientY }; }} className="contents">
          <DataGrid
            handleRef={gridRef}
            ariaLabel="Hands"
            columns={columns}
            data={hands}
            getRowId={handId}
            density="compact"
            rowLines
            estimateRowHeight={43}
            sorting={sorting}
            onSortingChange={handleSortingChange}
            manualSorting
            selectedRowIds={selectedRowIds}
            onSelectionChange={handleSelectionChange}
            onRowClick={handleRowClick}
            onRowActivate={handleRowClick}
            renderRowMenu={renderRowMenu}
            onRowMenuCloseAutoFocus={handleRowMenuCloseAutoFocus}
            defaultHiddenColumns={defaultHiddenColumns}
            loading={loading || isPlaceholderData}
            persistKey="hands"
            stickyFirstColumn
            maxHeight={gridMaxHeight}
            className="min-h-0 flex-1"
          />
          </div>

          {data && (
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              perPage={perPage}
              onPageChange={setPage}
              onPerPageChange={(pp) => { setPerPage(pp); setPage(1); }}
            />
          )}
        </>
      )}

      {picker && (
        <TagPickerPopover
          key={picker.handId}
          handId={picker.handId}
          playerId={picker.playerId}
          initialTags={hands.find((h) => h.id === picker.handId)?.tags ?? []}
          point={picker}
          onClose={() => setPicker(null)}
        />
      )}

      {/* Drawer */}
      {selectedId && drawerOpen && (
        <HandDrawer
          handId={selectedId}
          playerId={hands.find((h) => h.id === selectedId)?.player_id ?? fixedPlayerId}
          onClose={closeDrawer}
          onCloseAutoFocus={handleCloseAutoFocus}
          onPrev={handlePrev}
          onNext={handleNext}
          onTagsChanged={() => { queryClient.invalidateQueries({ queryKey: ['hands'] }); }}
        />
      )}
    </div>
  );
}
