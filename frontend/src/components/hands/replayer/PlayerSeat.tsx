import type { PlayerSnapshot } from './useReplayerState';

const ACTION_COLORS: Record<string, string> = {
  Fold: 'text-text-muted',
  Check: 'text-text',
  Call: 'text-green',
  Bet: 'text-yellow-400',
  Raise: 'text-red',
};

function getActionColor(action: string | null): string {
  if (!action) return 'text-text-muted';
  for (const [key, color] of Object.entries(ACTION_COLORS)) {
    if (action.startsWith(key)) return color;
  }
  if (action.startsWith('Won')) return 'text-green';
  return 'text-text';
}

export default function PlayerSeat({
  player,
  isActive,
  isShowdown,
  showBb,
  bbAmount,
}: {
  player: PlayerSnapshot;
  isActive: boolean;
  isShowdown: boolean;
  showBb: boolean;
  bbAmount: number;
}) {
  const isFolded = player.isFolded;
  const isWinner = isShowdown && player.wonBb > 0;
  const hasCards = player.card1 && player.card2;

  const borderClass = isActive
    ? 'ring-2 ring-primary'
    : isWinner
    ? 'ring-2 ring-green'
    : player.isHero
    ? 'border-primary/50'
    : 'border-border/50';

  const opacityClass = isFolded && !isShowdown ? 'opacity-30' : '';

  const stackDisplay = showBb
    ? `${player.stack.toFixed(1)}`
    : `$${(player.stack * bbAmount).toFixed(2)}`;

  return (
    <div className={`flex flex-col items-center gap-0.5 w-[110px] ${opacityClass}`}>
      {/* Cards */}
      <div className="flex gap-[2px] h-[32px] mb-0.5">
        {isFolded && !isShowdown ? null : hasCards ? (
          <>
            <SeatCard card={player.card1!} />
            <SeatCard card={player.card2!} />
          </>
        ) : !isFolded ? (
          <>
            <SeatCardBack />
            <SeatCardBack />
          </>
        ) : null}
      </div>

      {/* Info box */}
      <div className={`rounded-md border px-2 py-1 text-center w-full ${borderClass} bg-surface`}>
        <div className="flex items-center justify-center gap-1">
          <span
            className={`text-[13px] font-medium truncate max-w-[70px] leading-tight ${
              player.isHero ? 'text-primary' : 'text-text'
            }`}
            title={player.username}
          >
            {player.isHero ? 'Hero' : player.username}
          </span>
          <span className="text-[10px] font-mono text-text-muted bg-background/60 rounded px-0.5 leading-tight">
            {player.position}
          </span>
        </div>
        <div className="text-[11px] font-mono text-text-muted leading-tight">
          {stackDisplay}
        </div>
        {player.lastAction && (
          <div className={`text-[11px] font-semibold leading-tight ${getActionColor(player.lastAction)}`}>
            {player.lastAction}
          </div>
        )}
      </div>

      {/* Bet chip */}
      {player.currentBet > 0 && !isShowdown && (
        <div className="text-[11px] font-mono font-bold text-yellow-400 bg-background/80 rounded-full px-1.5 py-0.5 border border-yellow-400/30">
          {showBb ? player.currentBet.toFixed(1) : `$${(player.currentBet * bbAmount).toFixed(2)}`}
        </div>
      )}
    </div>
  );
}

/* Card variants sized for seat view */

const SUIT_BG: Record<string, string> = {
  s: 'oklch(0.268 0.007 34.298)',
  h: '#dc2626',
  d: '#2563eb',
  c: '#16a34a',
};

function SeatCard({ card }: { card: string }) {
  if (!card || card.length < 2) return null;
  const rank = card.slice(0, -1).toUpperCase();
  const suit = card.slice(-1).toLowerCase();
  const bg = SUIT_BG[suit] || 'oklch(0.268 0.007 34.298)';
  return (
    <span
      className="inline-flex items-center justify-center w-[28px] h-[32px] rounded-[3px] text-[16px] font-bold text-white leading-none shrink-0"
      style={{ backgroundColor: bg }}
    >
      {rank}
    </span>
  );
}

function SeatCardBack() {
  return (
    <span
      className="inline-flex items-center justify-center w-[28px] h-[32px] rounded-[3px] shrink-0 border border-border/60"
      style={{ backgroundColor: 'oklch(0.22 0.005 260)' }}
    >
      <span className="text-[9px] text-text-muted/40 font-bold select-none">?</span>
    </span>
  );
}
