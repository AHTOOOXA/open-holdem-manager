import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getStatDetailHands } from '@/lib/api';
import type { HeroStats } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { queryClient } from '@/lib/query-client';
import { getStatDisplayName, getStatEntry } from '@/lib/stat-registry';
import { formatRelativeDate } from '@/lib/utils';
import AnalysisWidgets from '@/components/stats/widgets/AnalysisWidgets';
import { CardBoxPair, CardBoxRow, CardBox } from '@/components/hands/CardDisplay';
import Actions from '@/components/hands/Actions';
import HandDrawer from '@/components/hands/HandDrawer';
import Pagination from '@/components/hands/Pagination';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const POSITIONS = ['All', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

interface StatDetailPanelProps {
  statKey: string;
  position?: string;
  onPositionChange: (pos: string | undefined) => void;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
  heroStats?: HeroStats;
  page: number;
  perPage: number;
  onPageChange: (p: number) => void;
  onPerPageChange: (pp: number) => void;
}

export default function StatDetailPanel({
  statKey,
  position,
  onPositionChange,
  filterParams,
  heroStats,
  page,
  perPage,
  onPageChange,
  onPerPageChange,
}: StatDetailPanelProps) {
  const entry = getStatEntry(statKey);
  const displayName = getStatDisplayName(statKey);
  const isPositional = entry?.isPositional ?? false;

  const queryParams = {
    position,
    stakes: filterParams.stakes,
    game_mode: filterParams.game_mode,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
    page,
    per_page: perPage,
  };

  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.detail(statKey, { ...queryParams }),
    queryFn: () => getStatDetailHands(statKey, queryParams),
    placeholderData: (prev) => prev,
  });

  const pct = data && data.opportunity_count > 0
    ? ((data.action_count / data.opportunity_count) * 100).toFixed(1)
    : null;

  // Use a reset key to force re-mount of selection state when context changes
  const resetKey = `${statKey}-${position ?? ''}-${page}`;
  const [selectionKey, setSelectionKey] = useState(resetKey);
  const [selectedHandId, setSelectedHandId] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  if (selectionKey !== resetKey) {
    setSelectionKey(resetKey);
    setSelectedHandId(null);
    setSelectedIndex(-1);
  }

  const hands = useMemo(() => data?.hands ?? [], [data?.hands]);

  const openDrawer = useCallback((idx: number) => {
    if (idx >= 0 && idx < hands.length) {
      setSelectedIndex(idx);
      setSelectedHandId(hands[idx].hand_id);
    }
  }, [hands]);

  const closeDrawer = useCallback(() => {
    setSelectedHandId(null);
  }, []);

  // Keyboard navigation
  useEffect(() => {
    if (selectedHandId) return; // Let HandDrawer handle keys when open

    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!hands.length) return;

      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, hands.length - 1));
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < hands.length) {
          openDrawer(selectedIndex);
        }
      }
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [selectedHandId, hands, selectedIndex, openDrawer]);

  const handleDrawerPrev = useCallback(() => {
    if (selectedIndex > 0) {
      const newIdx = selectedIndex - 1;
      setSelectedIndex(newIdx);
      setSelectedHandId(hands[newIdx].hand_id);
    }
  }, [selectedIndex, hands]);

  const handleDrawerNext = useCallback(() => {
    if (selectedIndex < hands.length - 1) {
      const newIdx = selectedIndex + 1;
      setSelectedIndex(newIdx);
      setSelectedHandId(hands[newIdx].hand_id);
    }
  }, [selectedIndex, hands]);

  // Build "Open in Hand Explorer" link
  const handExplorerUrl = `/hands?stat_key=${statKey}${position ? `&position=${position.toUpperCase()}` : ''}`;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-border shrink-0">
        <div className="flex items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold text-text">{displayName}</h3>
            {pct !== null && (
              <span className="text-xs text-text-muted font-mono">
                {pct}% ({data!.action_count}/{data!.opportunity_count})
              </span>
            )}
          </div>
          <Link
            to={handExplorerUrl}
            className="text-[11px] text-primary hover:text-primary/80 whitespace-nowrap"
          >
            Open in Hand Explorer &rarr;
          </Link>
        </div>

        {/* Position tabs */}
        {isPositional && (
          <div className="mt-2">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={position ?? 'All'}
              onValueChange={(val) => {
                onPageChange(1);
                onPositionChange(val === 'All' ? undefined : val);
              }}
            >
              {POSITIONS.map((pos) => (
                <ToggleGroupItem
                  key={pos}
                  value={pos}
                  className="h-6 text-[11px] px-2"
                >
                  {pos}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}
      </div>

      {/* Analysis Widgets */}
      <AnalysisWidgets
        statKey={statKey}
        heroStats={heroStats}
        filterParams={filterParams}
        position={position}
        onPositionChange={onPositionChange}
      />

      {/* Hand list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {isPending && !data ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : data && data.hands.length > 0 ? (
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
                  <TableHead className="py-2 px-2 h-auto text-center w-6">Act</TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right">Won</TableHead>
                  <TableHead className="py-2 px-2 h-auto text-right">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.hands.map((hand, idx) => (
                  <TableRow
                    key={hand.hand_id}
                    onClick={() => openDrawer(idx)}
                    className={`cursor-pointer transition-colors text-[15px] ${
                      idx === selectedIndex
                        ? 'bg-primary/10'
                        : 'hover:bg-surface-hover'
                    }`}
                  >
                    {/* Hole cards */}
                    <TableCell className="py-1.5 px-2">
                      <CardBoxPair card1={hand.card1} card2={hand.card2} />
                    </TableCell>
                    {/* Preflop actions */}
                    <TableCell className="py-1.5 px-2">
                      <Actions items={hand.preflop_actions} trimFolds />
                    </TableCell>
                    {/* Flop cards */}
                    <TableCell className="py-1.5 pl-4 pr-2">
                      <CardBoxRow cards={hand.board_flop} />
                    </TableCell>
                    {/* Flop pot */}
                    <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                      {hand.board_flop.length > 0 ? hand.flop_pot : ''}
                    </TableCell>
                    {/* Flop actions */}
                    <TableCell className="py-1.5 px-2">
                      <Actions items={hand.flop_actions} />
                    </TableCell>
                    {/* Turn card */}
                    <TableCell className="py-1.5 pl-4 pr-2">
                      {hand.board_turn && <CardBox card={hand.board_turn} />}
                    </TableCell>
                    {/* Turn pot */}
                    <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                      {hand.board_turn ? hand.turn_pot : ''}
                    </TableCell>
                    {/* Turn actions */}
                    <TableCell className="py-1.5 px-2">
                      <Actions items={hand.turn_actions} />
                    </TableCell>
                    {/* River card */}
                    <TableCell className="py-1.5 pl-4 pr-2">
                      {hand.board_river && <CardBox card={hand.board_river} />}
                    </TableCell>
                    {/* River pot */}
                    <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                      {hand.board_river ? hand.river_pot : ''}
                    </TableCell>
                    {/* River actions */}
                    <TableCell className="py-1.5 px-2">
                      <Actions items={hand.river_actions} />
                    </TableCell>
                    {/* Action taken */}
                    <TableCell className="py-1.5 px-2 text-center">
                      {hand.action_taken ? (
                        <span className="text-green text-[15px] font-bold">&#10003;</span>
                      ) : (
                        <span className="text-text-muted text-[15px]">&times;</span>
                      )}
                    </TableCell>
                    {/* Result */}
                    <TableCell className={`py-1.5 px-2 text-right font-mono text-[15px] font-semibold ${
                      hand.won_bb > 0.005 ? 'text-green' : hand.won_bb < -0.005 ? 'text-red' : 'text-text-muted'
                    }`}>
                      {Math.abs(hand.won_bb) < 0.005
                        ? '\u2014'
                        : `${hand.won_bb < 0 ? '' : '+'}${hand.won_bb.toFixed(1)}`}
                    </TableCell>
                    {/* Date */}
                    <TableCell className="py-1.5 px-2 text-right text-[14px] text-text-muted whitespace-nowrap">
                      {formatRelativeDate(hand.played_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="p-4 text-center text-text-muted text-sm">
            No hands match this filter
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="border-t border-border shrink-0">
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            perPage={perPage}
            onPageChange={onPageChange}
            onPerPageChange={(pp) => {
              onPerPageChange(pp);
              onPageChange(1);
            }}
          />
        </div>
      )}

      {/* Hand Drawer */}
      {selectedHandId && (
        <HandDrawer
          handId={selectedHandId}
          onClose={closeDrawer}
          onPrev={handleDrawerPrev}
          onNext={handleDrawerNext}
          onTagsChanged={() => { queryClient.invalidateQueries({ queryKey: ['hands'] }); }}
        />
      )}
    </div>
  );
}
