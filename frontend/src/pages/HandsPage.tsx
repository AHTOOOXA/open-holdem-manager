import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getHands, getTags, getFilterOptions } from '@/lib/api';
import type { HandListResponse, TagCount, ActionItem } from '@/lib/api';
import EmptyState from '@/components/EmptyState';
import HandFilters from '@/components/hands/HandFilters';
import type { FilterState } from '@/components/hands/HandFilters';
import { CardBoxPair, CardBoxRow, CardBox } from '@/components/hands/CardDisplay';
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

// ── Action display (H2N style) ──────────────────────────────────────

const ACTION_COLORS: Record<string, string> = {
  R: 'text-yellow',
  B: 'text-blue',
  C: 'text-text',
  X: 'text-text-muted',
  F: 'text-text-muted',
};

function Actions({ items, trimFolds }: { items: ActionItem[]; trimFolds?: boolean }) {
  if (!items || items.length === 0) return null;
  let display = items;
  if (trimFolds) {
    const firstNonFold = items.findIndex((a) => a.a !== 'F');
    if (firstNonFold > 0) display = items.slice(firstNonFold);
  }
  if (display.length === 0) return null;
  return (
    <span className="font-mono text-[15px] whitespace-nowrap">
      {display.map((a, i) => (
        <span key={i}>
          {i > 0 && ' '}
          <span
            className={`${ACTION_COLORS[a.a] || 'text-text'} ${a.h ? 'border-b-2 border-dashed border-current pb-[1px]' : ''}`}
          >
            {a.a}{a.v != null ? a.v : ''}
          </span>
        </span>
      ))}
    </span>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatStakes(bbAmount: number): string {
  const nl = Math.round(bbAmount * 100);
  return `NL${nl}`;
}

function formatDate(iso: string): string {
  const now = new Date();
  const d = new Date(iso);
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const sameYear = d.getFullYear() === now.getFullYear();
  if (sameYear) {
    return `${months[d.getMonth()]} ${d.getDate()}`;
  }
  return `${months[d.getMonth()]} ${d.getDate()} '${String(d.getFullYear()).slice(-2)}`;
}

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

// ── Main component ──────────────────────────────────────────────────

export default function HandsPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<HandListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [sort, setSort] = useState<string>('played_at');
  const [order, setOrder] = useState<string>('desc');

  // Read stat_flag from URL on mount
  const initialStatFlags = searchParams.getAll('stat_flag');

  const [filters, setFilters] = useState<FilterState>({
    position: [],
    stakes: [],
    result: '',
    tags: [],
    date: '',
    dateFrom: '',
    dateTo: '',
    search: '',
    statFlags: initialStatFlags,
  });
  const [distinctStakes, setDistinctStakes] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<TagCount[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showLegend, setShowLegend] = useState(false);

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

  const loadTags = useCallback(async () => {
    try { setAllTags(await getTags()); } catch { /* ignore */ }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const dateRange = getDateRange(filters.date, filters.dateFrom, filters.dateTo);
      const resp = await getHands({
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
        stat_flag: filters.statFlags.length > 0 ? filters.statFlags : undefined,
      });
      setData(resp);
    } catch (err) {
      console.error('Failed to load hands:', err);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sort, order, filters.position, filters.stakes, filters.result, filters.tags, filters.date, filters.dateFrom, filters.dateTo, debouncedSearch, filters.statFlags]);

  useEffect(() => { loadData(); loadTags(); }, [loadData, loadTags]);

  // Load distinct stakes on mount
  useEffect(() => {
    getFilterOptions().then((fo) => {
      setDistinctStakes(fo.stakes);
    }).catch(() => {});
  }, []);

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

  const hasFilters = filters.position.length > 0 || filters.stakes.length > 0 ||
    filters.result !== '' || filters.tags.length > 0 || filters.date !== '' || debouncedSearch !== '' ||
    filters.statFlags.length > 0;

  return (
    <div className="max-w-[1600px] mx-auto px-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <h1 className="text-[20px] font-bold text-text">Hands</h1>
          <button
            onClick={() => setShowLegend(!showLegend)}
            className="text-[12px] text-text-muted hover:text-text w-[18px] h-[18px] rounded-full border border-border flex items-center justify-center"
            title="Action legend"
          >
            ?
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
        />
      </div>

      {/* Table */}
      {loading && !data ? (
        <p className="text-text-muted text-sm py-8 text-center">Loading hands...</p>
      ) : !data || data.total === 0 ? (
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => handleFilterChange({ position: [], stakes: [], result: '', tags: [], date: '', dateFrom: '', dateTo: '', search: '', statFlags: [] }) : undefined}
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
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('won_bb')}>
                    Won{sortArrow('won_bb')}
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
                        <Actions items={h.preflop_actions} trimFolds />
                      </TableCell>
                      {/* Flop cards */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        <CardBoxRow cards={h.flop_cards} />
                      </TableCell>
                      {/* Flop pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.flop_cards.length > 0 ? h.flop_pot : ''}
                      </TableCell>
                      {/* Flop actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.flop_actions} />
                      </TableCell>
                      {/* Turn card */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        {h.turn_card && <CardBox card={h.turn_card} />}
                      </TableCell>
                      {/* Turn pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.turn_card ? h.turn_pot : ''}
                      </TableCell>
                      {/* Turn actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.turn_actions} />
                      </TableCell>
                      {/* River card */}
                      <TableCell className="py-1.5 pl-4 pr-2">
                        {h.river_card && <CardBox card={h.river_card} />}
                      </TableCell>
                      {/* River pot */}
                      <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                        {h.river_card ? h.river_pot : ''}
                      </TableCell>
                      {/* River actions */}
                      <TableCell className="py-1.5 px-2">
                        <Actions items={h.river_actions} />
                      </TableCell>
                      {/* Stakes */}
                      <TableCell className="py-1.5 pl-4 pr-2 font-mono text-[15px] text-text-muted">
                        {formatStakes(h.bb_amount)}
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
                        {formatDate(h.played_at)}
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
          onTagsChanged={() => { loadData(); loadTags(); }}
        />
      )}
    </div>
  );
}
