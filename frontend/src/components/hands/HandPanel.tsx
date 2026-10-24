import { useQuery } from '@tanstack/react-query';
import { Copy, Play, X } from 'lucide-react';
import { getHandDetail } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { formatStakes } from '@/lib/utils';
import { formatDateTime } from '@/lib/format';
import { plotPlayers, rowPlayer } from '@/lib/hands/hand-plot';
import HandActionsDisplay from '@/components/hands/HandActions';
import { HandPlayersTable, HandResultLine } from '@/components/hands/HandTextParts';
import { RitBadge, CashoutBadge } from '@/components/hands/HandTypeBadge';
import { copyHandHistory } from '@/components/hands/handListActions';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

/**
 * The hand plot: a compact, docked read-out of one hand (players, board and actions per street, result).
 * Built from the same detail data and text-mode pieces as the drawer's Text view.
 */
export default function HandPanel({
  handId,
  playerId,
  evBb,
  onClose,
  onReplay,
}: {
  handId: string;
  playerId?: number;
  /** The list row's all-in EV (bb) when known. */
  evBb?: number | null;
  onClose: () => void;
  onReplay: () => void;
}) {
  const { data: hand, isError } = useQuery({
    queryKey: [...queryKeys.hands.detail(handId), playerId ?? null],
    queryFn: () => getHandDetail(handId, playerId),
    staleTime: 30_000,
  });
  const owner = hand ? rowPlayer(hand.players, playerId) : undefined;

  return (
    <aside aria-label="Hand details" className="flex min-h-0 w-125 shrink-0 flex-col border-l border-border bg-card">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-xs text-muted-foreground" title={handId}>{handId}</div>
          {hand && (
            <div className="flex items-center gap-2 text-sm text-foreground">
              <span className="font-semibold">{formatStakes(hand.stakes)}</span>
              <span className="truncate text-muted-foreground">{formatDateTime(hand.played_at)}</span>
              {hand.rit_boards > 1 && <RitBadge boards={hand.rit_boards} />}
              {hand.is_cashout && <CashoutBadge />}
            </div>
          )}
        </div>
        <Button type="button" size="sm" onClick={onReplay}>
          <Play className="fill-current" />
          Replay
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => void copyHandHistory(handId, playerId)}>
          <Copy />
          Copy
        </Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Close hand details" onClick={onClose}>
          <X />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {isError ? (
          <p className="text-sm text-muted-foreground">Could not load the hand.</p>
        ) : !hand ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <>
            <div className="mb-3">
              <HandPlayersTable players={plotPlayers(hand, playerId)} dense />
            </div>
            <HandActionsDisplay actions={hand.actions} board={hand.board} extraBoards={hand.extra_boards} />
            <HandResultLine wonBb={owner?.won_bb ?? 0} evBb={evBb} isCashout={hand.is_cashout} />
          </>
        )}
      </div>
    </aside>
  );
}
