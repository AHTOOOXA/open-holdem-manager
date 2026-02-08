import { useState, useEffect, useCallback, useRef } from 'react';
import { getHands, getTags } from '@/lib/api';
import type { HandListResponse, TagCount } from '@/lib/api';
import HandFilters from '@/components/hands/HandFilters';
import type { FilterState } from '@/components/hands/HandFilters';
import { CardPair, BoardDisplay } from '@/components/hands/CardDisplay';
import TagPill from '@/components/hands/TagPill';
import Pagination from '@/components/hands/Pagination';
import HandDrawer from '@/components/hands/HandDrawer';

function formatStakes(bbAmount: number): string {
  const nl = Math.round(bbAmount * 100);
  return `NL${nl}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const month = d.toLocaleString('en', { month: 'short' });
  const day = d.getDate();
  const hours = String(d.getHours()).padStart(2, '0');
  const mins = String(d.getMinutes()).padStart(2, '0');
  return `${month} ${day} ${hours}:${mins}`;
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

const POS_COLORS: Record<string, string> = {
  BTN: 'text-green',
  CO: 'text-green',
  MP: 'text-yellow',
  EP: 'text-yellow',
  SB: 'text-text-muted',
  BB: 'text-text-muted',
};

export default function HandsPage() {
  const [data, setData] = useState<HandListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [sort, setSort] = useState<string>('played_at');
  const [order, setOrder] = useState<string>('desc');
  const [filters, setFilters] = useState<FilterState>({
    position: [],
    stakes: [],
    result: '',
    tags: [],
    date: '',
    dateFrom: '',
    dateTo: '',
    search: '',
  });
  const [distinctStakes, setDistinctStakes] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<TagCount[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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
    try {
      const tags = await getTags();
      setAllTags(tags);
    } catch { /* ignore */ }
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
      });
      setData(resp);

    } catch (err) {
      console.error('Failed to load hands:', err);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sort, order, filters.position, filters.stakes, filters.result, filters.tags, filters.date, filters.dateFrom, filters.dateTo, debouncedSearch]);

  useEffect(() => {
    loadData();
    loadTags();
  }, [loadData, loadTags]);

  // Load distinct stakes on mount
  useEffect(() => {
    getHands({ per_page: 200, sort: 'played_at', order: 'desc' }).then((resp) => {
      const stakes = [...new Set(resp.hands.map((h) => h.stakes))].sort();
      setDistinctStakes(stakes);
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

  const handleFilterChange = (f: FilterState) => {
    setFilters(f);
    setPage(1);
  };

  const sortArrow = (col: string) => {
    if (sort !== col) return '';
    return order === 'desc' ? ' \u25BC' : ' \u25B2';
  };

  const hands = data?.hands ?? [];
  const selectedIndex = selectedId ? hands.findIndex((h) => h.id === selectedId) : -1;

  const handlePrev = () => {
    if (selectedIndex > 0) setSelectedId(hands[selectedIndex - 1].id);
  };
  const handleNext = () => {
    if (selectedIndex >= 0 && selectedIndex < hands.length - 1) setSelectedId(hands[selectedIndex + 1].id);
  };

  return (
    <div className="max-w-7xl mx-auto px-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-bold text-text">Hand Browser</h1>
        {data && (
          <span className="text-[13px] text-text-muted">
            {data.total.toLocaleString()} hands
          </span>
        )}
      </div>

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
        <div className="text-center py-12">
          <p className="text-text-muted text-lg">
            {data && data.total === 0 && (filters.position.length > 0 || filters.stakes.length > 0 || filters.result || filters.tags.length > 0 || filters.date || debouncedSearch)
              ? 'No hands match your filters.'
              : 'No hands yet. Import hand histories to get started.'}
          </p>
          {data && data.total === 0 && (filters.position.length > 0 || filters.stakes.length > 0 || filters.result || filters.tags.length > 0 || filters.date || debouncedSearch) && (
            <button
              onClick={() => handleFilterChange({ position: [], stakes: [], result: '', tags: [], date: '', dateFrom: '', dateTo: '', search: '' })}
              className="mt-2 text-sm text-primary hover:text-primary-hover"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="border border-border rounded overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-surface border-b border-border text-[11px] text-text-muted uppercase">
                  <th
                    className="py-1.5 px-2 text-left cursor-pointer hover:text-text select-none"
                    onClick={() => handleSort('played_at')}
                  >
                    Date/Time{sortArrow('played_at')}
                  </th>
                  <th
                    className="py-1.5 px-2 text-left cursor-pointer hover:text-text select-none"
                    onClick={() => handleSort('stakes')}
                  >
                    Stakes{sortArrow('stakes')}
                  </th>
                  <th
                    className="py-1.5 px-2 text-left cursor-pointer hover:text-text select-none"
                    onClick={() => handleSort('position')}
                  >
                    Pos{sortArrow('position')}
                  </th>
                  <th className="py-1.5 px-2 text-left">Cards</th>
                  <th className="py-1.5 px-2 text-left">Board</th>
                  <th
                    className="py-1.5 px-2 text-right cursor-pointer hover:text-text select-none"
                    onClick={() => handleSort('won_bb')}
                  >
                    BB Won{sortArrow('won_bb')}
                  </th>
                  <th className="py-1.5 px-2 text-left">Tags</th>
                </tr>
              </thead>
              <tbody>
                {hands.map((h) => (
                  <tr
                    key={h.id}
                    onClick={() => setSelectedId(h.id)}
                    className={`border-b border-border/30 cursor-pointer transition-colors text-[13px] ${
                      selectedId === h.id ? 'bg-primary/10' : 'hover:bg-surface-hover'
                    }`}
                  >
                    <td className="py-1 px-2 font-mono text-text-muted whitespace-nowrap">
                      {formatDate(h.played_at)}
                    </td>
                    <td className="py-1 px-2 font-mono">
                      {formatStakes(h.bb_amount)}
                    </td>
                    <td className={`py-1 px-2 font-mono ${POS_COLORS[h.position] || 'text-text'}`}>
                      {h.position}
                    </td>
                    <td className="py-1 px-2">
                      <CardPair card1={h.card1} card2={h.card2} />
                    </td>
                    <td className="py-1 px-2">
                      <BoardDisplay cards={h.saw_flop ? h.board.slice(0, 3) : []} />
                    </td>
                    <td className={`py-1 px-2 text-right font-mono font-semibold ${
                      h.won_bb > 0 ? 'text-green' : h.won_bb < 0 ? 'text-red' : 'text-text-muted'
                    }`}>
                      {h.won_bb > 0 ? '+' : ''}{h.won_bb.toFixed(1)}
                    </td>
                    <td className="py-1 px-2">
                      <div className="flex items-center gap-1">
                        {h.tags.slice(0, 2).map((t) => (
                          <TagPill key={t} tag={t} />
                        ))}
                        {h.tags.length > 2 && (
                          <span className="text-[10px] text-text-muted">+{h.tags.length - 2}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
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
