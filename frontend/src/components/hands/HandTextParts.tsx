import type { HandPlayerDetail } from '@/lib/api';
import { CardPair } from '@/components/hands/CardDisplay';
import PlayerTypeBadge from '@/components/PlayerTypeBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { fixed, toneClass } from '@/lib/format';
import { plotResult } from '@/lib/hands/hand-plot';

/** Players of a hand, position first: position, name, stack (bb), hole cards when known. Shared by the drawer's Text view and the hand panel. */
export function HandPlayersTable({ players, dense = false }: { players: HandPlayerDetail[]; dense?: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="text-sm">
          <TableHead className="h-auto w-15 px-2 py-1.5">Pos</TableHead>
          <TableHead className="h-auto px-2 py-1.5">Player</TableHead>
          <TableHead className="h-auto px-2 py-1.5 text-right">Stack</TableHead>
          <TableHead className="h-auto px-2 py-1.5">Cards</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {players.map((p) => (
          <TableRow key={p.seat} className={cn('text-sm', p.is_hero && 'bg-selection')}>
            <TableCell className={cn('px-2', dense ? 'py-1' : 'py-1.5')}>
              <span className="rounded-control bg-overlay-hover px-2 py-0.5 text-xs font-semibold text-foreground">
                {p.position}
              </span>
            </TableCell>
            <TableCell className={cn('px-2', dense ? 'py-1' : 'py-1.5', p.is_hero ? 'font-semibold text-primary' : 'text-muted-foreground')}>
              <span className="flex items-center gap-1.5">
                <span className="truncate">{p.username}</span>
                {!p.is_hero && p.player_type && p.player_type !== 'UNK' && <PlayerTypeBadge type={p.player_type} />}
              </span>
            </TableCell>
            <TableCell className={cn('px-2 text-right', dense ? 'py-1' : 'py-1.5')}>{fixed(p.stack_bb, 1)}</TableCell>
            <TableCell className={cn('px-2', dense ? 'py-1' : 'py-1.5')}>
              <CardPair card1={p.card1} card2={p.card2} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** "Won 12.5 bb" with the all-in EV beside it when it differs. */
export function HandResultLine({ wonBb, evBb, isCashout }: { wonBb: number; evBb?: number | null; isCashout?: boolean }) {
  const r = plotResult(wonBb, evBb);
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 text-sm font-semibold">
      <span className={toneClass(r.tone)}>
        {r.label}
        {isCashout && <span className="ml-1 text-muted-foreground">(EV cashout)</span>}
      </span>
      {r.ev && <span className="font-normal text-muted-foreground">{r.ev}</span>}
    </div>
  );
}
