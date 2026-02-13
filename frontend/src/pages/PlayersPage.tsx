import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getPlayers } from '@/lib/api';
import type { PlayerListParams } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { formatRelativeDate } from '@/lib/utils';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import EmptyState from '@/components/EmptyState';
import Pagination from '@/components/hands/Pagination';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const PLAYER_TYPES = ['All', 'NIT', 'TAG', 'LAG', 'REC', 'MAN', 'UNK'] as const;

export default function PlayersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [minHands, setMinHands] = useState(20);
  const [sortBy, setSortBy] = useState('hands');
  const [sortDir, setSortDir] = useState('desc');

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [search]);

  const queryParams: PlayerListParams = {
    page,
    per_page: perPage,
    search: debouncedSearch || undefined,
    player_type: typeFilter !== 'All' ? typeFilter : undefined,
    min_hands: minHands,
    sort_by: sortBy,
    sort_dir: sortDir,
  };

  const { data, isPending, isError } = useQuery({
    queryKey: queryKeys.players.list(queryParams),
    queryFn: () => getPlayers(queryParams),
  });

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
    setPage(1);
  };

  const sortArrow = (col: string) => {
    if (sortBy !== col) return '';
    return sortDir === 'desc' ? ' \u2193' : ' \u2191';
  };

  const hasFilters = debouncedSearch !== '' || typeFilter !== 'All' || minHands !== 20;

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <Input
          placeholder="Search players..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-56 h-8 text-[13px]"
        />
        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
          <SelectTrigger className="w-28 h-8 text-[13px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PLAYER_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t === 'All' ? 'All Types' : t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] text-text-muted">Min hands:</span>
          <Input
            type="number"
            min={0}
            value={minHands}
            onChange={(e) => { setMinHands(Number(e.target.value) || 0); setPage(1); }}
            className="w-20 h-8 text-[13px]"
          />
        </div>
        {data && (
          <span className="text-[13px] text-text-muted ml-auto">
            {data.total.toLocaleString()} players
          </span>
        )}
      </div>

      {/* Table */}
      {isPending && !data ? (
        <p className="text-text-muted text-sm py-8 text-center">Loading players...</p>
      ) : isError ? (
        <p className="text-red text-sm py-8 text-center">Failed to load players</p>
      ) : !data || data.total === 0 ? (
        <EmptyState
          variant={hasFilters ? 'no-match' : 'no-data'}
          onClearFilters={hasFilters ? () => { setSearch(''); setTypeFilter('All'); setMinHands(20); setPage(1); } : undefined}
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="text-[13px] uppercase tracking-wide">
                  <TableHead className="py-2 px-2 h-auto cursor-pointer hover:text-text select-none" onClick={() => handleSort('username')}>
                    Player{sortArrow('username')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto">Type</TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('hands')}>
                    Hands{sortArrow('hands')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('vpip')}>
                    VPIP{sortArrow('vpip')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('pfr')}>
                    PFR{sortArrow('pfr')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('three_bet')}>
                    3-Bet{sortArrow('three_bet')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('af')}>
                    AF{sortArrow('af')}
                  </TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right cursor-pointer hover:text-text select-none" onClick={() => handleSort('last_seen')}>
                    Last Seen{sortArrow('last_seen')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.players.map((p) => (
                  <TableRow
                    key={p.id}
                    onClick={() => navigate(`/players/${p.id}`)}
                    className="cursor-pointer transition-colors text-[14px] hover:bg-surface-hover"
                  >
                    <TableCell className="py-1.5 px-2 font-medium">{p.username}</TableCell>
                    <TableCell className="py-1.5 px-2">
                      <PlayerTypeBadge type={p.player_type} />
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right font-mono text-text-muted">
                      {p.hands.toLocaleString()}
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right font-mono">
                      {p.vpip !== null ? p.vpip.toFixed(1) : '\u2014'}
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right font-mono">
                      {p.pfr !== null ? p.pfr.toFixed(1) : '\u2014'}
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right font-mono">
                      {p.three_bet !== null ? p.three_bet.toFixed(1) : '\u2014'}
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right font-mono">
                      {p.af !== null ? p.af.toFixed(2) : '\u2014'}
                    </TableCell>
                    <TableCell className="py-1.5 px-2 text-right text-text-muted text-[13px]">
                      {p.last_seen ? formatRelativeDate(p.last_seen) : '\u2014'}
                    </TableCell>
                  </TableRow>
                ))}
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
    </div>
  );
}
