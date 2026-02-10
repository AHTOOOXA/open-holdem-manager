import { useQuery } from '@tanstack/react-query';
import { getStatDetailHands } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { getStatDisplayName, getStatEntry } from '@/lib/stat-registry';
import { CardPair } from '@/components/hands/CardDisplay';
import Pagination from '@/components/hands/Pagination';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-border shrink-0">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold text-text">{displayName}</h3>
          {pct !== null && (
            <span className="text-xs text-text-muted font-mono">
              {pct}% ({data!.action_count}/{data!.opportunity_count})
            </span>
          )}
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

      {/* Hand list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {isPending && !data ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : data && data.hands.length > 0 ? (
          <table className="w-full">
            <thead className="sticky top-0 bg-background z-10">
              <tr className="border-b border-border">
                <th className="py-1 px-2 text-left text-[10px] font-medium text-text-muted uppercase">Hand</th>
                <th className="py-1 px-2 text-center text-[10px] font-medium text-text-muted uppercase">Pos</th>
                <th className="py-1 px-2 text-center text-[10px] font-medium text-text-muted uppercase">Cards</th>
                <th className="py-1 px-2 text-center text-[10px] font-medium text-text-muted uppercase">Action</th>
                <th className="py-1 px-2 text-right text-[10px] font-medium text-text-muted uppercase">Result</th>
                <th className="py-1 px-2 text-right text-[10px] font-medium text-text-muted uppercase">Stakes</th>
              </tr>
            </thead>
            <tbody>
              {data.hands.map((hand) => (
                <tr key={hand.hand_id} className="border-b border-border/30 hover:bg-surface-hover">
                  <td className="py-1 px-2 text-[11px] text-text-muted font-mono">
                    {hand.hand_id.replace(/^RC/, '')}
                  </td>
                  <td className="py-1 px-2 text-center text-[11px] text-text-muted">
                    {hand.position}
                  </td>
                  <td className="py-1 px-2 text-center text-[12px]">
                    <CardPair card1={hand.card1} card2={hand.card2} />
                  </td>
                  <td className="py-1 px-2 text-center">
                    {hand.action_taken ? (
                      <span className="text-green text-[12px] font-bold">&check;</span>
                    ) : (
                      <span className="text-text-muted text-[12px]">&times;</span>
                    )}
                  </td>
                  <td className={`py-1 px-2 text-right text-[12px] font-mono ${hand.won_bb >= 0 ? 'text-green' : 'text-red'}`}>
                    {hand.won_bb >= 0 ? '+' : ''}{hand.won_bb.toFixed(1)}
                  </td>
                  <td className="py-1 px-2 text-right text-[11px] text-text-muted">
                    {hand.stakes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
    </div>
  );
}
