import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHands, getTags } from '@/lib/api';
import type { HandListParams, TagCount } from '@/lib/api';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { queryKeys } from '@/lib/query-keys';
import { queryClient } from '@/lib/query-client';
import { formatStakes, formatRelativeDate } from '@/lib/utils';
import EmptyState from '@/components/EmptyState';
import HandFilters from '@/components/hands/HandFilters';
import type { FilterState } from '@/components/hands/HandFilters';
import { QUICK_FILTERS_MAP } from '@/components/hands/HandFilters';
import { CardBoxPair, CardBoxRow, CardBox } from '@/components/hands/CardDisplay';
import Actions from '@/components/hands/Actions';
import TagPill from '@/components/hands/TagPill';
import Pagination from '@/components/hands/Pagination';
import HandDrawer from '@/components/hands/HandDrawer';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function getDateRange(preset: string, dateFrom: string, dateTo: string): { from?: string; to?: string } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  switch (preset) {
    case 'today':
      return { from: today.toISOString().slice(0, 10) };
    case 'week': {
      const d = new Date(today);
      d.setDate(d.getDate() - d.getDay());
      return { from: d.toISOString().slice(0, 10) };
    }
    case 'month':
      return { from: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01` };
    case 'custom':
      return { from: dateFrom || undefined, to: dateTo || undefined };
    default:
      return {};
  }
}

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
}

export default function HandExplorer({
  fixedParams,
  initialFilters,
  defaultPerPage = 50,
  header,
  className,
}: HandExplorerProps) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(defaultPerPage);
  const [sort, setSort] = useState<string>('played_at');
  const [order, setOrder] = useState<string>('desc');

  const [filters, setFilters] = useState<FilterState>({
    position: initialFilters?.position ?? [],
    stakes: initialFilters?.stakes ?? [],
    result: initialFilters?.result ?? '',
    tags: initialFilters?.tags ?? [],
    date: initialFilters?.date ?? '',
    dateFrom: initialFilters?.dateFrom ?? '',
    dateTo: initialFilters?.dateTo ?? '',
    search: initialFilters?.search ?? '',
    statFlags: initialFilters?.statFlags ?? [],
    quickFilters: initialFilters?.quickFilters ?? [],
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showLegend, setShowLegend] = useState(false);
  const [bbPrecision, setBbPrecision] = useState<0 | 1>(0);

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
    tags: filters.tags.length > 0 ? filters.tags.join(',') : undefined,
    date_from: dateRange.from,
    date_to: dateRange.to,
    search: debouncedSearch || undefined,
    stat_flag: allStatFlags.length > 0 ? allStatFlags : undefined,
  };

  // Merge fixedParams — they override user params for the same key
  const handsQueryParams: HandListParams = { ...userParams, ...fixedParams };
  // For position, merge: if fixedParams has position AND user selected positions, use fixed
  // (fixedParams takes precedence since it's applied via spread after userParams)

  // Hands list query
  const { data, isPending: loading, isError, error } = useQuery({
    queryKey: queryKeys.hands.list(handsQueryParams),
    queryFn: () => getHands(handsQueryParams),
  });

  // Tags query
  const { data: allTags = [] } = useQuery<TagCount[]>({
    queryKey: queryKeys.hands.tags,
    queryFn: getTags,
  });

  const handleSort = (col: string) => {
    if (sort === col) {
      setOrder(order === 'desc' ? 'asc' : 'desc');
    } else {
      setSort(col);
      setOrder('desc');
    }
    setPage(1);
  };

  const handleFilterChange = (f: FilterState) => { setFilters(f); setPage(1); };

  const sortArrow = (col: string) => {
    if (sort !== col) return '';
    return order === 'desc' ? ' \u2193' : ' \u2191';
  };

  const hands = data?.hands ?? [];
  const selectedIndex = selectedId ? hands.findIndex((h) => h.id === selectedId) : -1;

  const handlePrev = () => {
    if (selectedIndex > 0) setSelectedId(hands[selectedIndex - 1].id);
  };
  const handleNext = () => {
    if (selectedIndex >= 0 && selectedIndex < hands.length - 1) setSelectedId(hands[selectedIndex + 1].id);
  };

  const hasUserFilters = filters.position.length > 0 || filters.stakes.length > 0 ||
    filters.result !== '' || filters.tags.length > 0 || filters.date !== '' || debouncedSearch !== '' ||
    filters.statFlags.length > 0 || filters.quickFilters.length > 0;
  const hasFixedFilters = !!(fixedParams?.stat_key || fixedParams?.stat_flag?.length || fixedParams?.position || fixedParams?.stakes);
  const hasFilters = hasUserFilters || hasFixedFilters;

  // Compute locked stat flags from fixedParams
  const lockedStatFlags: string[] = [];
  if (fixedParams?.stat_key) lockedStatFlags.push(fixedParams.stat_key);
  if (fixedParams?.stat_flag) {
    for (const f of fixedParams.stat_flag) {
      if (!lockedStatFlags.includes(f)) lockedStatFlags.push(f);
    }
  }

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          {header}
          <button
            onClick={() => setShowLegend(!showLegend)}
            className="text-[12px] text-text-muted hover:text-text w-[18px] h-[18px] rounded-full border border-border flex items-center justify-center"
            title="Action legend"
          >
            ?
          </button>
          <button
            onClick={() => setBbPrecision(p => p === 0 ? 1 : 0)}
            className={`text-[11px] font-mono px-1.5 h-[18px] rounded border flex items-center justify-center ${
              bbPrecision === 1 ? 'border-primary text-primary' : 'border-border text-text-muted hover:text-text'
            }`}
            title={`BB precision: ${bbPrecision === 0 ? 'rounded' : '1 decimal'}. Click to toggle.`}
          >
            .0
          </button>
        </div>
        {data && (
          <span className="text-[15px] text-text-muted">
            {data.total.toLocaleString()} hands
          </span>
        )}
      </div>

      {/* Legend tooltip */}
      {showLegend && (
        <div className="mb-2 px-3 py-2 bg-surface rounded border border-border text-[14px] font-mono flex items-center gap-5">
          <span><span className="text-yellow font-bold">R</span> Raise</span>
          <span><span className="text-blue font-bold">B</span> Bet</span>
          <span><span className="font-bold text-text">C</span> Call</span>
          <span className="text-text-muted">X Check</span>
          <span className="text-text-muted">F Fold</span>
          <span className="text-text-muted/40">|</span>
          <span className="text-text-muted"><span className="border-b-2 border-dashed border-text-muted pb-[1px]">dashed underline</span> = hero action</span>
        </div>
      )}

      {/* Filters */}
      <div className="mb-3">
        <HandFilters
          filters={filters}
          onChange={handleFilterChange}
          distinctStakes={distinctStakes}
          allTags={allTags}
          lockedStatFlags={lockedStatFlags.length > 0 ? lockedStatFlags : undefined}
        />
      </div>

      {/* Table */}
      {isError ? (
        <p className="text-red text-sm py-8 text-center">
          Failed to load hands{error instanceof Error ? `: ${error.message}` : ''}
        </p>
      ) : loading && !data ? (
        <p className="text-text-muted text-sm py-8 text-center">Loading hands...</p>
      ) : !data || data.total === 0 ? (
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasUserFilters ? () => handleFilterChange({ position: [], stakes: [], result: '', tags: [], date: '', dateFrom: '', dateTo: '', search: '', statFlags: [], quickFilters: [] }) : undefined}
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="text-[13px] uppercase tracking-wide">
                  <TableHead className="py-2 px-2 h-auto">Preflop</TableHead>
                  <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                  <TableHead className="py-2 pl-4 pr-2 h-auto">Flop</TableHead>
                  <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                  <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                  <TableHead className="py-2 pl-4 pr-2 h-auto">Turn</TableHead>
                  <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                  <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                  <TableHead className="py-2 pl-4 pr-2 h-auto">River</TableHead>
                  <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                  <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                  <TableHead className="py-2 pl-4 pr-2 h-auto cursor-pointer hover:text-text select-none" onClick={() => handleSort('stakes')}>
                    Stakes{sortArrow('stakes')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('won_usd')}>
                    Won{sortArrow('won_usd')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right">EV Diff.</TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('played_at')}>
                    Date{sortArrow('played_at')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto">Tags</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hands.map((h) => {
                  const wonUsd = h.won_bb * h.bb_amount;
                  const evDiffBb = h.all_in_ev_bb - h.won_bb;
                  const evDiffUsd = evDiffBb * h.bb_amount;
                  return (
                    <TableRow
                      key={h.id}
                      onClick={() => setSelectedId(h.id)}
                      className={`cursor-pointer transition-colors text-[15px] ${
                        selectedId === h.id ? 'bg-primary/10' : 'hover:bg-surface-hover'
                      }`}
                    >
                      {/* Preflop cards */}
                      <TableCell className="py-1.5 px-2">
                        <CardBoxPair card1={h.card1} card2={h.card2} />
                      </TableCell>
                      {/* Preflop actions — trim leading folds */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.preflop_actions} trimFolds precision={bbPrecision} />
                      </TableCell>
                      {/* Flop cards */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        <CardBoxRow cards={h.flop_cards} />
                      </TableCell>
                      {/* Flop pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.flop_cards.length > 0 ? (bbPrecision === 0 ? Math.round(h.flop_pot) : h.flop_pot.toFixed(1).replace(/\.0$/, '')) : ''}
                      </TableCell>
                      {/* Flop actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.flop_actions} precision={bbPrecision} />
                      </TableCell>
                      {/* Turn card */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        {h.turn_card && <CardBox card={h.turn_card} />}
                      </TableCell>
                      {/* Turn pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.turn_card ? (bbPrecision === 0 ? Math.round(h.turn_pot) : h.turn_pot.toFixed(1).replace(/\.0$/, '')) : ''}
                      </TableCell>
                      {/* Turn actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.turn_actions} precision={bbPrecision} />
                      </TableCell>
                      {/* River card */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        {h.river_card && <CardBox card={h.river_card} />}
                      </TableCell>
                      {/* River pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.river_card ? (bbPrecision === 0 ? Math.round(h.river_pot) : h.river_pot.toFixed(1).replace(/\.0$/, '')) : ''}
                      </TableCell>
                      {/* River actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.river_actions} precision={bbPrecision} />
                      </TableCell>
                      {/* Stakes */}
                      <TableCell className="py-1.5 pl-4 pr-2 font-mono text-[15px] text-text-muted">
                        {formatStakes(h.stakes)}
                      </TableCell>
                      {/* Won (USD) */}
                      <TableCell className={`py-1.5 px-2 text-right font-mono text-[15px] font-semibold ${
                        wonUsd > 0.005 ? 'text-green' : wonUsd < -0.005 ? 'text-red' : 'text-text-muted'
                      }`}>
                        {Math.abs(wonUsd) < 0.005
                          ? '\u2014'
                          : `${wonUsd < 0 ? '-' : ''}${Math.abs(wonUsd).toFixed(2)}$`}
                      </TableCell>
                      {/* EV Diff */}
                      <TableCell className={`py-1.5 px-2 text-right font-mono text-[15px] ${
                        Math.abs(evDiffUsd) < 0.005 ? 'text-text-muted/40' :
                        evDiffUsd > 0 ? 'text-green' : 'text-red'
                      }`}>
                        {Math.abs(evDiffUsd) < 0.005
                          ? '\u2014'
                          : `${evDiffUsd < 0 ? '-' : ''}${Math.abs(evDiffUsd).toFixed(2)}$`}
                      </TableCell>
                      {/* Date */}
                      <TableCell className="py-1.5 px-2 text-right text-[14px] text-text-muted whitespace-nowrap">
                        {formatRelativeDate(h.played_at)}
                      </TableCell>
                      {/* Tags */}
                      <TableCell className="py-1.5 px-2">
                        <div className="flex items-center gap-0.5">
                          {h.tags.slice(0, 2).map((t) => (
                            <TagPill key={t} tag={t} />
                          ))}
                          {h.tags.length > 2 && (
                            <span className="text-[11px] text-text-muted">+{h.tags.length - 2}</span>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            perPage={perPage}
            onPageChange={setPage}
            onPerPageChange={(pp) => { setPerPage(pp); setPage(1); }}
          />
        </>
      )}

      {/* Drawer */}
      {selectedId && (
        <HandDrawer
          handId={selectedId}
          onClose={() => setSelectedId(null)}
          onPrev={handlePrev}
          onNext={handleNext}
          onTagsChanged={() => { queryClient.invalidateQueries({ queryKey: ['hands'] }); }}
        />
      )}
    </div>
  );
}
